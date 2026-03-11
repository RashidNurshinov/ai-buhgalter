"""
OCR-пайплайн для распознавания бухгалтерских документов.

Полный цикл: предобработка изображения → OCR (Tesseract/EasyOCR) → LLM-структуризация → валидация.

Пункты плана: 1.8.1–1.8.8
"""

import io
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np
from PIL import Image

from app.constants.enums import DocumentType, FileType
from app.prompts.document_recognition import (
    DOCUMENT_RECOGNITION_PROMPT,
    DOCUMENT_RECOGNITION_USER_PROMPT,
)
from app.services.openrouter_client import LLMResponse, OpenRouterClient
from app.utils.validators import validate_inn, validate_kpp, validate_amounts_consistency

logger = logging.getLogger(__name__)


# ─── Dataclasses результата ─────────────────────────────────────


@dataclass
class OcrTextResult:
    """Результат OCR-извлечения текста."""
    text: str = ""
    engine: str = ""  # "tesseract" | "easyocr" | "pdfplumber"
    confidence: float = 0.0
    language: str = "rus"
    warnings: list[str] = field(default_factory=list)


@dataclass
class RecognizedCounterparty:
    """Распознанный контрагент из LLM-ответа."""
    name: str = ""
    inn: str = ""
    kpp: str | None = None
    address: str | None = None


@dataclass
class RecognizedItem:
    """Распознанная позиция документа."""
    name: str = ""
    quantity: Decimal = Decimal("1")
    unit: str = ""
    price_without_vat: Decimal = Decimal("0")
    vat_rate: Decimal = Decimal("0")
    vat_amount: Decimal = Decimal("0")
    total_with_vat: Decimal = Decimal("0")


@dataclass
class RecognizedDocument:
    """Итоговый результат распознавания документа (OCR + LLM + валидация)."""
    doc_type: DocumentType = DocumentType.OTHER
    doc_number: str | None = None
    doc_date: date | None = None

    seller: RecognizedCounterparty | None = None
    buyer: RecognizedCounterparty | None = None

    items: list[RecognizedItem] = field(default_factory=list)

    total_without_vat: Decimal = Decimal("0")
    vat_amount: Decimal = Decimal("0")
    total_with_vat: Decimal = Decimal("0")
    vat_rate: Decimal = Decimal("22")
    currency: str = "RUB"

    # OCR-метаданные
    ocr_text: str = ""
    ocr_engine: str = ""
    ocr_confidence: float = 0.0

    # LLM-метаданные
    llm_model: str = ""
    llm_confidence: float = 0.0
    llm_raw_response: dict[str, Any] = field(default_factory=dict)

    # Дополнительные поля (чеки, платёжки)
    additional_info: dict[str, Any] = field(default_factory=dict)

    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    @property
    def confidence_score(self) -> float:
        """Общий скор уверенности (среднее OCR + LLM)."""
        if self.ocr_confidence > 0 and self.llm_confidence > 0:
            return (self.ocr_confidence * 0.3 + self.llm_confidence * 0.7)
        return self.llm_confidence or self.ocr_confidence


# ─── 1.8.1: Предобработка изображения (OpenCV) ──────────────────


def preprocess_image(image_data: bytes) -> bytes:
    """
    Предобработка изображения для улучшения OCR:
    1. Конвертация в grayscale
    2. Удаление шума (bilateral filter)
    3. Коррекция угла наклона (deskew)
    4. Адаптивная бинаризация
    5. Удаление мелких артефактов

    Args:
        image_data: Байты исходного изображения

    Returns:
        Байты обработанного изображения (PNG)
    """
    # Декодируем изображение
    nparr = np.frombuffer(image_data, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        logger.warning("Не удалось декодировать изображение, возвращаем как есть")
        return image_data

    # 1. Grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 2. Удаление шума (bilateral filter сохраняет текст лучше Gaussian)
    denoised = cv2.bilateralFilter(gray, 9, 75, 75)

    # 3. Коррекция угла наклона
    deskewed = _deskew(denoised)

    # 4. Адаптивная бинаризация (лучше для документов с неравномерным освещением)
    binary = cv2.adaptiveThreshold(
        deskewed,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=15,
        C=10,
    )

    # 5. Удаление мелких артефактов (морфологическое открытие)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    cleaned = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)

    # Кодируем обратно в PNG
    success, encoded = cv2.imencode(".png", cleaned)
    if not success:
        logger.warning("Не удалось закодировать обработанное изображение")
        return image_data

    return encoded.tobytes()


def _deskew(image: np.ndarray) -> np.ndarray:
    """Коррекция угла наклона документа (до ±15°)."""
    # Определяем угол через Hough Lines
    edges = cv2.Canny(image, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180,
        threshold=100,
        minLineLength=100,
        maxLineGap=10,
    )

    if lines is None or len(lines) == 0:
        return image

    # Собираем углы всех найденных линий
    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        if abs(x2 - x1) < 1:
            continue
        angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        # Фильтруем — берём только почти горизонтальные линии
        if abs(angle) < 15:
            angles.append(angle)

    if not angles:
        return image

    median_angle = float(np.median(angles))

    # Если угол меньше 0.5° — не корректируем
    if abs(median_angle) < 0.5:
        return image

    # Поворачиваем изображение
    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    rotation_matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)
    rotated = cv2.warpAffine(
        image, rotation_matrix, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )

    logger.debug(f"Deskew: скорректирован угол {median_angle:.2f}°")
    return rotated


def enhance_image_for_ocr(image_data: bytes) -> bytes:
    """
    Мягкая предобработка для отправки в LLM (vision).
    Не бинаризуем — LLM лучше работает с оригинальным изображением.
    Только resize если слишком большое + лёгкое повышение контраста.
    """
    nparr = np.frombuffer(image_data, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        return image_data

    h, w = img.shape[:2]

    # Resize если > 4000px по любой стороне (для экономии токенов LLM)
    max_side = 4000
    if max(h, w) > max_side:
        scale = max_side / max(h, w)
        new_w = int(w * scale)
        new_h = int(h * scale)
        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

    # Лёгкое повышение контраста (CLAHE)
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l_enhanced = clahe.apply(l_channel)
    enhanced = cv2.merge([l_enhanced, a_channel, b_channel])
    result = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)

    success, encoded = cv2.imencode(".jpg", result, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not success:
        return image_data

    return encoded.tobytes()


# ─── 1.8.2: OCR через Tesseract ─────────────────────────────────


def extract_text_tesseract(image_data: bytes, lang: str = "rus+eng") -> OcrTextResult:
    """
    Извлечение текста из изображения через Tesseract OCR.

    Args:
        image_data: Байты изображения (предобработанного)
        lang: Языки распознавания

    Returns:
        OcrTextResult с текстом и уверенностью
    """
    result = OcrTextResult(engine="tesseract", language=lang)

    try:
        import pytesseract
    except ImportError:
        result.warnings.append("pytesseract не установлен")
        return result

    try:
        # Предобработка
        preprocessed = preprocess_image(image_data)

        # Конвертация в PIL Image
        pil_image = Image.open(io.BytesIO(preprocessed))

        # Полные данные с confidence
        tsv_data = pytesseract.image_to_data(
            pil_image, lang=lang, output_type=pytesseract.Output.DICT
        )

        # Извлекаем текст
        texts = []
        confidences = []
        for i, text in enumerate(tsv_data["text"]):
            conf = int(tsv_data["conf"][i])
            if conf > 0 and text.strip():
                texts.append(text)
                confidences.append(conf)

        result.text = " ".join(texts)

        # Средняя уверенность
        if confidences:
            result.confidence = sum(confidences) / len(confidences) / 100.0
        else:
            result.confidence = 0.0
            result.warnings.append("Tesseract не извлёк ни одного символа")

        logger.info(
            "Tesseract OCR: %d слов, confidence=%.2f",
            len(texts), result.confidence,
        )

    except Exception as e:
        logger.exception(f"Ошибка Tesseract OCR: {e}")
        result.warnings.append(f"Ошибка Tesseract: {str(e)}")

    return result


# ─── 1.8.3: OCR через EasyOCR ───────────────────────────────────

# Глобальный reader — инициализируется один раз (EasyOCR загружает модель при создании)
_easyocr_reader = None


def _get_easyocr_reader(langs: list[str] | None = None):
    """Lazy-инициализация EasyOCR reader (синглтон)."""
    global _easyocr_reader
    if _easyocr_reader is None:
        try:
            import easyocr
            _easyocr_reader = easyocr.Reader(
                langs or ["ru", "en"],
                gpu=False,  # CPU-only для стабильности в Docker
                verbose=False,
            )
            logger.info("EasyOCR reader инициализирован")
        except ImportError:
            logger.warning("easyocr не установлен")
            return None
        except Exception as e:
            logger.error(f"Ошибка инициализации EasyOCR: {e}")
            return None
    return _easyocr_reader


def extract_text_easyocr(image_data: bytes, langs: list[str] | None = None) -> OcrTextResult:
    """
    Извлечение текста из изображения через EasyOCR.

    Args:
        image_data: Байты изображения
        langs: Языки (по умолчанию: ["ru", "en"])

    Returns:
        OcrTextResult с текстом и уверенностью
    """
    result = OcrTextResult(engine="easyocr", language=",".join(langs or ["ru", "en"]))

    reader = _get_easyocr_reader(langs)
    if reader is None:
        result.warnings.append("EasyOCR не доступен")
        return result

    try:
        # Предобработка
        preprocessed = preprocess_image(image_data)

        # EasyOCR принимает numpy array или путь к файлу
        nparr = np.frombuffer(preprocessed, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)

        if img is None:
            result.warnings.append("Не удалось декодировать изображение для EasyOCR")
            return result

        # Распознавание
        ocr_results = reader.readtext(img, detail=1, paragraph=True)

        texts = []
        confidences = []
        for item in ocr_results:
            # item: (bbox, text, confidence)
            if len(item) >= 3:
                _, text, conf = item[0], item[1], item[2]
            elif len(item) == 2:
                text, conf = item[0], item[1]
            else:
                continue

            if isinstance(text, str) and text.strip():
                texts.append(text.strip())
                if isinstance(conf, (int, float)):
                    confidences.append(float(conf))

        result.text = "\n".join(texts)

        if confidences:
            result.confidence = sum(confidences) / len(confidences)
        else:
            result.confidence = 0.0
            result.warnings.append("EasyOCR не извлёк текст")

        logger.info(
            "EasyOCR: %d блоков текста, confidence=%.2f",
            len(texts), result.confidence,
        )

    except Exception as e:
        logger.exception(f"Ошибка EasyOCR: {e}")
        result.warnings.append(f"Ошибка EasyOCR: {str(e)}")

    return result


# ─── 1.8.4: Извлечение текста из PDF ────────────────────────────


def extract_text_from_pdf(pdf_data: bytes) -> OcrTextResult:
    """
    Извлечение текста из PDF:
    1. Пробуем pdfplumber (текстовый PDF)
    2. Если текста мало — fallback на OCR каждой страницы

    Args:
        pdf_data: Байты PDF-файла

    Returns:
        OcrTextResult
    """
    result = OcrTextResult(engine="pdfplumber")

    try:
        import pdfplumber
    except ImportError:
        result.warnings.append("pdfplumber не установлен")
        return result

    try:
        pages_text = []
        pages_images = []

        with pdfplumber.open(io.BytesIO(pdf_data)) as pdf:
            for i, page in enumerate(pdf.pages):
                # Извлекаем текст
                text = page.extract_text() or ""
                pages_text.append(text.strip())

                # Если на странице мало текста — конвертируем в изображение для OCR
                if len(text.strip()) < 50:
                    try:
                        # Рендерим страницу как изображение
                        pil_img = page.to_image(resolution=300).original
                        img_buffer = io.BytesIO()
                        pil_img.save(img_buffer, format="PNG")
                        pages_images.append((i, img_buffer.getvalue()))
                    except Exception as img_err:
                        logger.warning(
                            "Не удалось сконвертировать PDF-страницу %d в изображение: %s",
                            i, img_err,
                        )

        full_text = "\n\n".join(t for t in pages_text if t)

        # Если текста достаточно — используем pdfplumber
        if len(full_text) > 100:
            result.text = full_text
            result.confidence = 0.9  # Текстовый PDF — высокая точность
            result.engine = "pdfplumber"
            logger.info("PDF: текстовый, %d символов из pdfplumber", len(full_text))
            return result

        # Fallback: OCR страниц
        logger.info(
            "PDF: мало текста (%d символов), запускаем OCR для %d страниц",
            len(full_text), len(pages_images),
        )

        ocr_texts = []
        ocr_confidences = []

        for page_num, img_bytes in pages_images:
            # Пробуем Tesseract
            ocr_result = extract_text_tesseract(img_bytes)
            if ocr_result.text:
                ocr_texts.append(f"--- Страница {page_num + 1} ---\n{ocr_result.text}")
                ocr_confidences.append(ocr_result.confidence)

        if ocr_texts:
            result.text = "\n\n".join(ocr_texts)
            result.confidence = sum(ocr_confidences) / len(ocr_confidences) if ocr_confidences else 0.0
            result.engine = "pdfplumber+tesseract"
        else:
            # Последний fallback — возвращаем что есть из pdfplumber
            result.text = full_text
            result.confidence = 0.3
            result.warnings.append("Мало текста в PDF, OCR не дал результатов")

    except Exception as e:
        logger.exception(f"Ошибка обработки PDF: {e}")
        result.warnings.append(f"Ошибка PDF: {str(e)}")

    return result


# ─── 1.8.5: Распознавание документа через LLM ───────────────────


async def recognize_document_with_llm(
    image_data: bytes | None,
    ocr_text: str,
    client: OpenRouterClient | None = None,
    image_media_type: str = "image/jpeg",
) -> tuple[dict[str, Any], LLMResponse]:
    """
    Отправка изображения + OCR-текста в LLM для структуризации.
    
    Используется Qwen 2.5 72B (vision capabilities) через OpenRouter.

    Args:
        image_data: Байты изображения (если есть). Для PDF — None.
        ocr_text: Извлечённый OCR-текст
        client: OpenRouter клиент (если None — создаётся)
        image_media_type: MIME-тип изображения

    Returns:
        Кортеж (parsed_json, llm_response)
    """
    if client is None:
        from app.services.openrouter_client import get_openrouter_client
        client = get_openrouter_client()

    # Формируем контекст OCR
    ocr_context = ""
    if ocr_text:
        # Ограничиваем длину OCR-текста чтобы не раздувать промпт
        truncated = ocr_text[:8000]
        if len(ocr_text) > 8000:
            truncated += "\n... (текст обрезан)"
        ocr_context = f"Извлечённый OCR-текст:\n```\n{truncated}\n```"

    user_message = DOCUMENT_RECOGNITION_USER_PROMPT.format(ocr_context=ocr_context)

    messages = [
        {"role": "system", "content": DOCUMENT_RECOGNITION_PROMPT},
        {"role": "user", "content": user_message},
    ]

    # Вызов LLM
    if image_data:
        # С изображением (vision) — улучшаем для LLM
        enhanced_image = enhance_image_for_ocr(image_data)
        llm_response = await client.chat_completion_with_image(
            messages=messages,
            image_data=enhanced_image,
            image_media_type=image_media_type,
            task="document_recognition",
        )
    else:
        # Только текст (для PDF)
        llm_response = await client.chat_completion(
            messages=messages,
            task="document_recognition",
        )

    # Парсим JSON из ответа LLM
    parsed_json = _parse_llm_json_response(llm_response.content or "")

    return parsed_json, llm_response


def _parse_llm_json_response(content: str) -> dict[str, Any]:
    """Извлечение JSON из ответа LLM (может быть обёрнут в markdown)."""
    if not content:
        return {"doc_type": "other", "confidence": 0.0, "errors": ["Пустой ответ LLM"]}

    # 1. Пробуем прямой парсинг
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # 2. Извлекаем JSON из markdown ```json ... ```
    json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", content, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # 3. Ищем первый { ... } блок
    brace_match = re.search(r"\{.*\}", content, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    logger.warning("Не удалось извлечь JSON из ответа LLM: %s...", content[:200])
    return {
        "doc_type": "other",
        "confidence": 0.0,
        "errors": [f"Не удалось распарсить ответ LLM: {content[:500]}"],
    }


# ─── 1.8.7: Валидация распознанных данных ───────────────────────


def validate_recognized_data(data: dict[str, Any]) -> tuple[list[str], list[str]]:
    """
    Валидация результата распознавания: ИНН, суммы, даты, обязательные поля.

    Args:
        data: JSON от LLM

    Returns:
        (warnings, errors)
    """
    warnings: list[str] = list(data.get("warnings", []))
    errors: list[str] = list(data.get("errors", []))

    doc_type = data.get("doc_type", "other")

    # 1. Валидация даты
    doc_date_str = data.get("doc_date")
    if doc_date_str:
        parsed_date = _parse_date_str(doc_date_str)
        if parsed_date is None:
            warnings.append(f"Не удалось распарсить дату: {doc_date_str}")
    else:
        if doc_type not in ("other", "contract"):
            warnings.append("Дата документа не распознана")

    # 2. Валидация ИНН продавца
    seller = data.get("seller") or data.get("payer")
    if seller and isinstance(seller, dict):
        inn = seller.get("inn")
        if inn:
            inn_clean = str(inn).strip().replace("\xa0", "")
            ok, err = validate_inn(inn_clean)
            if not ok:
                warnings.append(f"ИНН продавца/плательщика: {err}")
        kpp = seller.get("kpp")
        if kpp:
            ok, err = validate_kpp(str(kpp).strip())
            if not ok:
                warnings.append(f"КПП продавца/плательщика: {err}")

    # 3. Валидация ИНН покупателя
    buyer = data.get("buyer") or data.get("payee")
    if buyer and isinstance(buyer, dict):
        inn = buyer.get("inn")
        if inn:
            inn_clean = str(inn).strip().replace("\xa0", "")
            ok, err = validate_inn(inn_clean)
            if not ok:
                warnings.append(f"ИНН покупателя/получателя: {err}")
        kpp = buyer.get("kpp")
        if kpp:
            ok, err = validate_kpp(str(kpp).strip())
            if not ok:
                warnings.append(f"КПП покупателя/получателя: {err}")

    # 4. Валидация сумм (для документов с позициями)
    if doc_type in ("invoice", "upd", "torg12", "act", "bill", "cash_receipt"):
        total_without_vat = _safe_decimal(data.get("total_without_vat"))
        vat_amount = _safe_decimal(data.get("vat_amount"))
        total_with_vat = _safe_decimal(data.get("total_with_vat"))

        if total_with_vat > 0 and total_without_vat > 0:
            ok, err = validate_amounts_consistency(
                total_without_vat, vat_amount, total_with_vat,
                tolerance=Decimal("2.00"),  # Чуть больше допуск для OCR
            )
            if not ok:
                warnings.append(err)

        # Проверяем что есть хотя бы итоговая сумма
        if total_with_vat == 0 and total_without_vat == 0:
            warnings.append("Суммы документа не распознаны")

    # 5. Проверка номера документа
    if not data.get("doc_number") and doc_type not in ("other", "contract", "cash_receipt"):
        warnings.append("Номер документа не распознан")

    # 6. Проверка позиций
    items = data.get("items", [])
    if doc_type in ("invoice", "upd", "torg12") and not items:
        warnings.append("Позиции документа не распознаны")

    # 7. Confidence
    confidence = data.get("confidence", 0.0)
    if isinstance(confidence, (int, float)) and confidence < 0.5:
        warnings.append(f"Низкая уверенность распознавания: {confidence:.2f}")

    return warnings, errors


def _safe_decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    """Безопасная конвертация в Decimal."""
    if value is None:
        return default
    try:
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value).replace(",", ".").replace(" ", "").replace("\xa0", ""))
    except (InvalidOperation, ValueError):
        return default


def _parse_date_str(date_str: str) -> date | None:
    """Парсинг даты из строки (несколько форматов)."""
    if not date_str:
        return None
    date_str = str(date_str).strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


# ─── 1.8.8: Полный пайплайн process_document_image ──────────────


async def process_document_image(
    file_data: bytes,
    file_type: FileType,
    openrouter_client: OpenRouterClient | None = None,
) -> RecognizedDocument:
    """
    Полный OCR-пайплайн:
    1. Предобработка изображения
    2. OCR (Tesseract → fallback EasyOCR)
    3. Отправка в LLM (Qwen 2.5 72B vision)
    4. Валидация результата
    5. Маппинг в RecognizedDocument

    Args:
        file_data: Байты файла (изображение или PDF)
        file_type: Тип файла
        openrouter_client: OpenRouter клиент (опционально)

    Returns:
        RecognizedDocument
    """
    result = RecognizedDocument()

    # === ШАГ 1: Определяем тип обработки ===
    is_pdf = file_type == FileType.PDF
    is_image = file_type in (
        FileType.JPG, FileType.JPEG, FileType.PNG, FileType.TIFF, FileType.HEIC,
    )

    if not is_pdf and not is_image:
        result.errors.append(f"Неподдерживаемый тип файла для OCR: {file_type}")
        return result

    # === ШАГ 2: OCR — извлечение текста ===
    ocr_result: OcrTextResult

    if is_pdf:
        ocr_result = extract_text_from_pdf(file_data)
        image_for_llm = None
        image_media_type = ""

        # Для PDF с картинками — пробуем достать первую страницу как изображение
        if ocr_result.confidence < 0.5:
            first_page_image = _extract_first_pdf_page_as_image(file_data)
            if first_page_image:
                image_for_llm = first_page_image
                image_media_type = "image/png"
    else:
        # Изображение — OCR + передаём оригинал в LLM
        ocr_result = extract_text_tesseract(file_data)

        # Если Tesseract дал слабый результат — пробуем EasyOCR
        if ocr_result.confidence < 0.4 or len(ocr_result.text) < 30:
            logger.info("Tesseract дал слабый результат, пробуем EasyOCR")
            easyocr_result = extract_text_easyocr(file_data)

            if easyocr_result.confidence > ocr_result.confidence:
                ocr_result = easyocr_result
            elif easyocr_result.text and not ocr_result.text:
                ocr_result = easyocr_result

        image_for_llm = file_data
        image_media_type = _detect_image_media_type(file_type)

    result.ocr_text = ocr_result.text
    result.ocr_engine = ocr_result.engine
    result.ocr_confidence = ocr_result.confidence
    result.warnings.extend(ocr_result.warnings)

    logger.info(
        "OCR завершён: engine=%s, confidence=%.2f, text_len=%d",
        ocr_result.engine, ocr_result.confidence, len(ocr_result.text),
    )

    # === ШАГ 3: LLM-структуризация ===
    try:
        parsed_json, llm_response = await recognize_document_with_llm(
            image_data=image_for_llm,
            ocr_text=ocr_result.text,
            client=openrouter_client,
            image_media_type=image_media_type,
        )

        result.llm_model = llm_response.model
        result.llm_confidence = parsed_json.get("confidence", 0.0)
        result.llm_raw_response = parsed_json

        logger.info(
            "LLM распознавание: model=%s, doc_type=%s, confidence=%.2f, tokens=%d+%d",
            llm_response.model,
            parsed_json.get("doc_type", "?"),
            result.llm_confidence,
            llm_response.tokens_input,
            llm_response.tokens_output,
        )

    except Exception as e:
        logger.exception(f"Ошибка LLM-распознавания: {e}")
        result.errors.append(f"Ошибка LLM: {str(e)}")
        return result

    # === ШАГ 4: Валидация ===
    val_warnings, val_errors = validate_recognized_data(parsed_json)
    result.warnings.extend(val_warnings)
    result.errors.extend(val_errors)

    # === ШАГ 5: Маппинг в RecognizedDocument ===
    _map_llm_to_recognized_document(parsed_json, result)

    return result


def _extract_first_pdf_page_as_image(pdf_data: bytes) -> bytes | None:
    """Извлечение первой страницы PDF как изображения для LLM."""
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(pdf_data)) as pdf:
            if pdf.pages:
                pil_img = pdf.pages[0].to_image(resolution=200).original
                buf = io.BytesIO()
                pil_img.save(buf, format="PNG")
                return buf.getvalue()
    except Exception as e:
        logger.warning(f"Не удалось извлечь страницу PDF как изображение: {e}")
    return None


def _detect_image_media_type(file_type: FileType) -> str:
    """Определение MIME-типа по FileType."""
    mapping = {
        FileType.JPG: "image/jpeg",
        FileType.JPEG: "image/jpeg",
        FileType.PNG: "image/png",
        FileType.TIFF: "image/tiff",
        FileType.HEIC: "image/heic",
    }
    return mapping.get(file_type, "image/jpeg")


def _map_llm_to_recognized_document(data: dict[str, Any], result: RecognizedDocument):
    """Маппинг JSON от LLM в RecognizedDocument."""

    # Тип документа
    doc_type_str = data.get("doc_type", "other")
    try:
        result.doc_type = DocumentType(doc_type_str)
    except ValueError:
        result.doc_type = DocumentType.OTHER
        result.warnings.append(f"Неизвестный тип документа: {doc_type_str}")

    # Номер и дата
    result.doc_number = data.get("doc_number")
    date_str = data.get("doc_date")
    if date_str:
        result.doc_date = _parse_date_str(str(date_str))

    # Продавец
    seller_data = data.get("seller") or data.get("payer")
    if seller_data and isinstance(seller_data, dict):
        result.seller = RecognizedCounterparty(
            name=seller_data.get("name", ""),
            inn=str(seller_data.get("inn", "")).strip() if seller_data.get("inn") else "",
            kpp=str(seller_data.get("kpp", "")).strip() if seller_data.get("kpp") else None,
            address=seller_data.get("address"),
        )

    # Покупатель
    buyer_data = data.get("buyer") or data.get("payee")
    if buyer_data and isinstance(buyer_data, dict):
        result.buyer = RecognizedCounterparty(
            name=buyer_data.get("name", ""),
            inn=str(buyer_data.get("inn", "")).strip() if buyer_data.get("inn") else "",
            kpp=str(buyer_data.get("kpp", "")).strip() if buyer_data.get("kpp") else None,
            address=buyer_data.get("address"),
        )

    # Позиции
    for item_data in data.get("items", []):
        if not isinstance(item_data, dict):
            continue
        item = RecognizedItem(
            name=item_data.get("name", ""),
            quantity=_safe_decimal(item_data.get("quantity"), Decimal("1")),
            unit=item_data.get("unit", ""),
            price_without_vat=_safe_decimal(item_data.get("price_without_vat")),
            vat_rate=_safe_decimal(item_data.get("vat_rate")),
            vat_amount=_safe_decimal(item_data.get("vat_amount")),
            total_with_vat=_safe_decimal(item_data.get("total_with_vat")),
        )
        result.items.append(item)

    # Суммы
    result.total_without_vat = _safe_decimal(data.get("total_without_vat"))
    result.vat_amount = _safe_decimal(data.get("vat_amount"))
    result.total_with_vat = _safe_decimal(data.get("total_with_vat"))
    result.vat_rate = _safe_decimal(data.get("vat_rate"), Decimal("22"))
    result.currency = data.get("currency", "RUB")

    # Дополнительные данные
    additional = {}
    if data.get("additional_info"):
        additional.update(data["additional_info"])
    if data.get("receipt_info"):
        additional["receipt_info"] = data["receipt_info"]
    if data.get("purpose"):
        additional["purpose"] = data["purpose"]
    if data.get("amount") and not result.total_with_vat:
        result.total_with_vat = _safe_decimal(data["amount"])
    result.additional_info = additional


# ─── Утилита: маппинг RecognizedDocument → dict для БД ──────────


def map_recognized_to_document_dict(recognized: RecognizedDocument) -> dict[str, Any]:
    """
    Маппинг RecognizedDocument в словарь полей для создания Document + DocumentItem в БД.
    Совместим с DocumentCreate Pydantic-схемой.
    """
    items = []
    for item in recognized.items:
        items.append({
            "name": item.name or "Позиция",
            "quantity": item.quantity,
            "unit": item.unit or None,
            "price_without_vat": item.price_without_vat,
            "vat_rate": item.vat_rate,
            "vat_amount": item.vat_amount,
            "total_with_vat": item.total_with_vat,
        })

    return {
        "doc_type": recognized.doc_type.value,
        "doc_number": recognized.doc_number,
        "doc_date": recognized.doc_date,
        "total_without_vat": recognized.total_without_vat,
        "vat_amount": recognized.vat_amount,
        "total_with_vat": recognized.total_with_vat,
        "vat_rate": recognized.vat_rate,
        "items": items,
        "seller": {
            "name": recognized.seller.name if recognized.seller else "",
            "inn": recognized.seller.inn if recognized.seller else "",
            "kpp": recognized.seller.kpp if recognized.seller else None,
            "address": recognized.seller.address if recognized.seller else None,
        } if recognized.seller else None,
        "buyer": {
            "name": recognized.buyer.name if recognized.buyer else "",
            "inn": recognized.buyer.inn if recognized.buyer else "",
            "kpp": recognized.buyer.kpp if recognized.buyer else None,
            "address": recognized.buyer.address if recognized.buyer else None,
        } if recognized.buyer else None,
        "confidence_score": recognized.confidence_score,
        "recognized_data_json": {
            "ocr_text": recognized.ocr_text[:2000] if recognized.ocr_text else "",
            "ocr_engine": recognized.ocr_engine,
            "ocr_confidence": recognized.ocr_confidence,
            "llm_model": recognized.llm_model,
            "llm_confidence": recognized.llm_confidence,
            "additional_info": recognized.additional_info,
        },
        "warnings": recognized.warnings,
        "errors": recognized.errors,
    }