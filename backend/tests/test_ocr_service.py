"""
Тесты OCR-пайплайна: предобработка, парсинг JSON, валидация, маппинг.
Пункт плана: 1.8.10

Тесты НЕ требуют Tesseract/EasyOCR/LLM — тестируют внутреннюю логику.
"""

import io
import json
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from app.services.ocr_service import (
    OcrTextResult,
    RecognizedCounterparty,
    RecognizedDocument,
    RecognizedItem,
    _deskew,
    _detect_image_media_type,
    _map_llm_to_recognized_document,
    _parse_date_str,
    _parse_llm_json_response,
    _safe_decimal,
    enhance_image_for_ocr,
    map_recognized_to_document_dict,
    preprocess_image,
    validate_recognized_data,
)
from app.constants.enums import DocumentType, FileType


# ═══════════════════════════════════════════════════════════
# 1. Тесты предобработки изображения
# ═══════════════════════════════════════════════════════════


class TestPreprocessImage:
    """Тесты preprocess_image()."""

    def _make_test_image(self, width: int = 200, height: int = 100) -> bytes:
        """Создать тестовое изображение в памяти."""
        import cv2
        img = np.zeros((height, width, 3), dtype=np.uint8)
        img[:] = (255, 255, 255)  # Белый фон
        # Рисуем текст
        cv2.putText(img, "Test 123", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
        success, encoded = cv2.imencode(".png", img)
        assert success
        return encoded.tobytes()

    def test_preprocess_returns_bytes(self):
        """Предобработка возвращает bytes."""
        img = self._make_test_image()
        result = preprocess_image(img)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_preprocess_invalid_image_returns_original(self):
        """При невалидном изображении возвращает оригинал."""
        invalid_data = b"not an image"
        result = preprocess_image(invalid_data)
        assert result == invalid_data

    def test_preprocess_output_is_valid_image(self):
        """Результат предобработки — валидное изображение."""
        import cv2
        img = self._make_test_image()
        result = preprocess_image(img)

        nparr = np.frombuffer(result, np.uint8)
        decoded = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
        assert decoded is not None
        # Должен быть grayscale (2D)
        assert len(decoded.shape) == 2


class TestEnhanceImageForOcr:
    """Тесты enhance_image_for_ocr()."""

    def _make_large_image(self, width: int = 5000, height: int = 5000) -> bytes:
        """Создать большое тестовое изображение."""
        import cv2
        img = np.ones((height, width, 3), dtype=np.uint8) * 128
        success, encoded = cv2.imencode(".jpg", img)
        assert success
        return encoded.tobytes()

    def test_enhance_returns_bytes(self):
        """Возвращает bytes."""
        import cv2
        img = np.zeros((100, 200, 3), dtype=np.uint8)
        success, encoded = cv2.imencode(".jpg", img)
        result = enhance_image_for_ocr(encoded.tobytes())
        assert isinstance(result, bytes)

    def test_enhance_resizes_large_images(self):
        """Большие изображения уменьшаются до 4000px."""
        import cv2
        large_img = self._make_large_image(5000, 5000)
        result = enhance_image_for_ocr(large_img)

        nparr = np.frombuffer(result, np.uint8)
        decoded = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        assert decoded is not None
        h, w = decoded.shape[:2]
        assert max(h, w) <= 4000

    def test_enhance_invalid_image_returns_original(self):
        """При невалидном изображении возвращает оригинал."""
        result = enhance_image_for_ocr(b"not an image")
        assert result == b"not an image"


# ═══════════════════════════════════════════════════════════
# 2. Тесты парсинга JSON ответа LLM
# ═══════════════════════════════════════════════════════════


class TestParseLlmJsonResponse:
    """Тесты _parse_llm_json_response()."""

    def test_parse_plain_json(self):
        """Парсинг чистого JSON."""
        content = '{"doc_type": "invoice", "confidence": 0.9}'
        result = _parse_llm_json_response(content)
        assert result["doc_type"] == "invoice"
        assert result["confidence"] == 0.9

    def test_parse_json_in_markdown(self):
        """Парсинг JSON обёрнутого в ```json ... ```."""
        content = 'Вот результат:\n```json\n{"doc_type": "upd", "confidence": 0.85}\n```\nГотово.'
        result = _parse_llm_json_response(content)
        assert result["doc_type"] == "upd"
        assert result["confidence"] == 0.85

    def test_parse_json_in_code_block_no_lang(self):
        """Парсинг JSON в code block без указания языка."""
        content = '```\n{"doc_type": "act"}\n```'
        result = _parse_llm_json_response(content)
        assert result["doc_type"] == "act"

    def test_parse_json_with_text_around(self):
        """Парсинг JSON с текстом вокруг (без markdown)."""
        content = 'Анализ документа: {"doc_type": "torg12", "confidence": 0.7} Конец.'
        result = _parse_llm_json_response(content)
        assert result["doc_type"] == "torg12"

    def test_parse_empty_returns_error(self):
        """Пустой ответ возвращает ошибку."""
        result = _parse_llm_json_response("")
        assert result["doc_type"] == "other"
        assert result["confidence"] == 0.0
        assert "errors" in result

    def test_parse_invalid_json_returns_error(self):
        """Невалидный JSON возвращает ошибку."""
        result = _parse_llm_json_response("Это просто текст без JSON")
        assert result["doc_type"] == "other"
        assert "errors" in result


# ═══════════════════════════════════════════════════════════
# 3. Тесты утилит
# ═══════════════════════════════════════════════════════════


class TestSafeDecimal:
    """Тесты _safe_decimal()."""

    def test_from_string(self):
        assert _safe_decimal("123.45") == Decimal("123.45")

    def test_from_int(self):
        assert _safe_decimal(100) == Decimal("100")

    def test_from_float(self):
        assert _safe_decimal(99.99) == Decimal("99.99")

    def test_from_none(self):
        assert _safe_decimal(None) == Decimal("0")

    def test_from_decimal(self):
        assert _safe_decimal(Decimal("42.00")) == Decimal("42.00")

    def test_with_comma(self):
        """Запятая как разделитель (российский формат)."""
        assert _safe_decimal("1 234,56") == Decimal("1234.56")

    def test_with_spaces(self):
        """Пробелы как разделители тысяч."""
        assert _safe_decimal("1 000 000") == Decimal("1000000")

    def test_invalid_returns_default(self):
        assert _safe_decimal("abc") == Decimal("0")
        assert _safe_decimal("abc", Decimal("99")) == Decimal("99")

    def test_with_nbsp(self):
        """Неразрывный пробел (\xa0)."""
        assert _safe_decimal("1\xa0000.50") == Decimal("1000.50")


class TestParseDateStr:
    """Тесты _parse_date_str()."""

    def test_dd_mm_yyyy(self):
        assert _parse_date_str("25.12.2024") == date(2024, 12, 25)

    def test_yyyy_mm_dd(self):
        assert _parse_date_str("2024-12-25") == date(2024, 12, 25)

    def test_dd_slash_mm_slash_yyyy(self):
        assert _parse_date_str("25/12/2024") == date(2024, 12, 25)

    def test_dd_dash_mm_dash_yyyy(self):
        assert _parse_date_str("25-12-2024") == date(2024, 12, 25)

    def test_invalid_returns_none(self):
        assert _parse_date_str("invalid") is None
        assert _parse_date_str("") is None
        assert _parse_date_str(None) is None

    def test_strips_whitespace(self):
        assert _parse_date_str("  25.12.2024  ") == date(2024, 12, 25)


class TestDetectImageMediaType:
    """Тесты _detect_image_media_type()."""

    def test_jpg(self):
        assert _detect_image_media_type(FileType.JPG) == "image/jpeg"

    def test_jpeg(self):
        assert _detect_image_media_type(FileType.JPEG) == "image/jpeg"

    def test_png(self):
        assert _detect_image_media_type(FileType.PNG) == "image/png"

    def test_tiff(self):
        assert _detect_image_media_type(FileType.TIFF) == "image/tiff"

    def test_unknown_defaults_to_jpeg(self):
        assert _detect_image_media_type(FileType.PDF) == "image/jpeg"


# ═══════════════════════════════════════════════════════════
# 4. Тесты валидации распознанных данных
# ═══════════════════════════════════════════════════════════


class TestValidateRecognizedData:
    """Тесты validate_recognized_data()."""

    def test_valid_invoice(self):
        """Валидная счёт-фактура без предупреждений."""
        data = {
            "doc_type": "invoice",
            "doc_number": "123",
            "doc_date": "25.12.2024",
            "seller": {"name": "ООО Тест", "inn": "7707083893"},
            "buyer": {"name": "ООО Покупатель", "inn": "7719261250"},
            "items": [{"name": "Услуга", "quantity": 1}],
            "total_without_vat": "100.00",
            "vat_amount": "20.00",
            "total_with_vat": "120.00",
            "confidence": 0.9,
        }
        warnings, errors = validate_recognized_data(data)
        assert len(errors) == 0
        # ИНН — тестовые, могут не пройти контрольную сумму → warning допустим
        # но не errors

    def test_invalid_inn_gives_warning(self):
        """Невалидный ИНН → предупреждение."""
        data = {
            "doc_type": "invoice",
            "doc_number": "1",
            "doc_date": "01.01.2025",
            "seller": {"name": "Тест", "inn": "1234567890"},
            "items": [{"name": "Товар"}],
            "total_without_vat": "100",
            "total_with_vat": "120",
            "vat_amount": "20",
            "confidence": 0.8,
        }
        warnings, errors = validate_recognized_data(data)
        # Должен быть warning про ИНН
        assert any("ИНН" in w for w in warnings)

    def test_missing_date_gives_warning(self):
        """Отсутствие даты → предупреждение для invoice."""
        data = {
            "doc_type": "invoice",
            "doc_number": "1",
            "items": [{"name": "Товар"}],
            "total_without_vat": "100",
            "total_with_vat": "120",
            "vat_amount": "20",
            "confidence": 0.7,
        }
        warnings, errors = validate_recognized_data(data)
        assert any("дата" in w.lower() or "Дата" in w for w in warnings)

    def test_amounts_inconsistency_gives_warning(self):
        """Несоответствие сумм → предупреждение."""
        data = {
            "doc_type": "invoice",
            "doc_number": "1",
            "doc_date": "01.01.2025",
            "items": [{"name": "Товар"}],
            "total_without_vat": "100.00",
            "vat_amount": "20.00",
            "total_with_vat": "200.00",  # Неверно! Должно быть 120
            "confidence": 0.8,
        }
        warnings, errors = validate_recognized_data(data)
        assert any("сумм" in w.lower() or "Несоответствие" in w for w in warnings)

    def test_missing_doc_number_warning(self):
        """Отсутствие номера документа для invoice."""
        data = {
            "doc_type": "invoice",
            "doc_date": "01.01.2025",
            "items": [{"name": "Товар"}],
            "total_without_vat": "100",
            "total_with_vat": "120",
            "vat_amount": "20",
            "confidence": 0.8,
        }
        warnings, errors = validate_recognized_data(data)
        assert any("номер" in w.lower() or "Номер" in w for w in warnings)

    def test_low_confidence_warning(self):
        """Низкая уверенность → предупреждение."""
        data = {
            "doc_type": "other",
            "confidence": 0.3,
        }
        warnings, errors = validate_recognized_data(data)
        assert any("уверенност" in w.lower() for w in warnings)

    def test_other_doctype_no_date_no_warning(self):
        """Для типа other — отсутствие даты не даёт warning."""
        data = {
            "doc_type": "other",
            "confidence": 0.6,
        }
        warnings, errors = validate_recognized_data(data)
        assert not any("дата" in w.lower() for w in warnings)

    def test_missing_items_warning_for_invoice(self):
        """Отсутствие позиций для invoice → warning."""
        data = {
            "doc_type": "invoice",
            "doc_number": "1",
            "doc_date": "01.01.2025",
            "total_without_vat": "100",
            "total_with_vat": "120",
            "vat_amount": "20",
            "confidence": 0.8,
        }
        warnings, errors = validate_recognized_data(data)
        assert any("позиции" in w.lower() or "Позиции" in w for w in warnings)


# ═══════════════════════════════════════════════════════════
# 5. Тесты маппинга LLM → RecognizedDocument
# ═══════════════════════════════════════════════════════════


class TestMapLlmToRecognizedDocument:
    """Тесты _map_llm_to_recognized_document()."""

    def test_full_invoice_mapping(self):
        """Полный маппинг счёт-фактуры."""
        data = {
            "doc_type": "invoice",
            "doc_number": "СФ-123",
            "doc_date": "15.03.2025",
            "seller": {
                "name": "ООО Поставщик",
                "inn": "7707083893",
                "kpp": "770701001",
                "address": "г. Москва, ул. Тестовая, 1",
            },
            "buyer": {
                "name": "ООО Покупатель",
                "inn": "7719261250",
            },
            "items": [
                {
                    "name": "Консультационные услуги",
                    "quantity": "10",
                    "unit": "час",
                    "price_without_vat": "5000.00",
                    "vat_rate": "20",
                    "vat_amount": "10000.00",
                    "total_with_vat": "60000.00",
                },
            ],
            "total_without_vat": "50000.00",
            "vat_amount": "10000.00",
            "total_with_vat": "60000.00",
            "vat_rate": "20",
            "currency": "RUB",
        }
        result = RecognizedDocument()
        _map_llm_to_recognized_document(data, result)

        assert result.doc_type == DocumentType.INVOICE
        assert result.doc_number == "СФ-123"
        assert result.doc_date == date(2025, 3, 15)

        assert result.seller is not None
        assert result.seller.name == "ООО Поставщик"
        assert result.seller.inn == "7707083893"
        assert result.seller.kpp == "770701001"

        assert result.buyer is not None
        assert result.buyer.name == "ООО Покупатель"

        assert len(result.items) == 1
        assert result.items[0].name == "Консультационные услуги"
        assert result.items[0].quantity == Decimal("10")
        assert result.items[0].price_without_vat == Decimal("5000.00")

        assert result.total_without_vat == Decimal("50000.00")
        assert result.vat_amount == Decimal("10000.00")
        assert result.total_with_vat == Decimal("60000.00")
        assert result.currency == "RUB"

    def test_unknown_doctype_defaults_to_other(self):
        """Неизвестный тип документа → OTHER + warning."""
        data = {"doc_type": "unknown_type"}
        result = RecognizedDocument()
        _map_llm_to_recognized_document(data, result)
        assert result.doc_type == DocumentType.OTHER
        assert any("Неизвестный" in w for w in result.warnings)

    def test_missing_fields_graceful(self):
        """Отсутствие полей обрабатывается без ошибок."""
        data = {"doc_type": "act"}
        result = RecognizedDocument()
        _map_llm_to_recognized_document(data, result)
        assert result.doc_type == DocumentType.ACT
        assert result.seller is None
        assert result.buyer is None
        assert result.items == []

    def test_payment_order_with_payer_payee(self):
        """Платёжное поручение с payer/payee маппится в seller/buyer."""
        data = {
            "doc_type": "payment_order",
            "payer": {"name": "Плательщик", "inn": "1234567890"},
            "payee": {"name": "Получатель", "inn": "0987654321"},
            "amount": "50000.00",
            "purpose": "Оплата по счёту №42",
        }
        result = RecognizedDocument()
        _map_llm_to_recognized_document(data, result)
        assert result.seller is not None
        assert result.seller.name == "Плательщик"
        assert result.buyer is not None
        assert result.buyer.name == "Получатель"
        assert result.total_with_vat == Decimal("50000.00")
        assert result.additional_info.get("purpose") == "Оплата по счёту №42"

    def test_additional_info_mapping(self):
        """Дополнительные поля маппятся в additional_info."""
        data = {
            "doc_type": "cash_receipt",
            "additional_info": {"fiscal_number": "12345"},
            "receipt_info": {"payment_type": "card"},
        }
        result = RecognizedDocument()
        _map_llm_to_recognized_document(data, result)
        assert result.additional_info["fiscal_number"] == "12345"
        assert result.additional_info["receipt_info"]["payment_type"] == "card"


# ═══════════════════════════════════════════════════════════
# 6. Тесты map_recognized_to_document_dict
# ═══════════════════════════════════════════════════════════


class TestMapRecognizedToDocumentDict:
    """Тесты map_recognized_to_document_dict()."""

    def test_basic_mapping(self):
        """Базовый маппинг RecognizedDocument → dict."""
        doc = RecognizedDocument(
            doc_type=DocumentType.INVOICE,
            doc_number="123",
            doc_date=date(2025, 1, 1),
            total_without_vat=Decimal("1000"),
            vat_amount=Decimal("200"),
            total_with_vat=Decimal("1200"),
            seller=RecognizedCounterparty(name="Продавец", inn="1234567890"),
            buyer=RecognizedCounterparty(name="Покупатель", inn="0987654321"),
            items=[
                RecognizedItem(
                    name="Товар",
                    quantity=Decimal("2"),
                    unit="шт",
                    price_without_vat=Decimal("500"),
                    vat_rate=Decimal("20"),
                    vat_amount=Decimal("200"),
                    total_with_vat=Decimal("1200"),
                ),
            ],
            ocr_engine="tesseract",
            ocr_confidence=0.85,
            llm_model="claude-sonnet",
            llm_confidence=0.92,
        )

        result = map_recognized_to_document_dict(doc)

        assert result["doc_type"] == "invoice"
        assert result["doc_number"] == "123"
        assert result["doc_date"] == date(2025, 1, 1)
        assert result["total_with_vat"] == Decimal("1200")
        assert result["seller"]["name"] == "Продавец"
        assert result["buyer"]["name"] == "Покупатель"
        assert len(result["items"]) == 1
        assert result["items"][0]["name"] == "Товар"
        assert result["confidence_score"] > 0
        assert result["recognized_data_json"]["ocr_engine"] == "tesseract"

    def test_no_seller_buyer(self):
        """Без seller/buyer — None в результате."""
        doc = RecognizedDocument(doc_type=DocumentType.OTHER)
        result = map_recognized_to_document_dict(doc)
        assert result["seller"] is None
        assert result["buyer"] is None

    def test_confidence_score_calculation(self):
        """Проверка расчёта confidence_score."""
        doc = RecognizedDocument(
            ocr_confidence=0.8,
            llm_confidence=0.9,
        )
        # 0.8 * 0.3 + 0.9 * 0.7 = 0.24 + 0.63 = 0.87
        assert abs(doc.confidence_score - 0.87) < 0.01


# ═══════════════════════════════════════════════════════════
# 7. Тесты RecognizedDocument
# ═══════════════════════════════════════════════════════════


class TestRecognizedDocument:
    """Тесты RecognizedDocument dataclass."""

    def test_is_valid_no_errors(self):
        doc = RecognizedDocument()
        assert doc.is_valid is True

    def test_is_valid_with_errors(self):
        doc = RecognizedDocument(errors=["Something wrong"])
        assert doc.is_valid is False

    def test_confidence_score_both(self):
        doc = RecognizedDocument(ocr_confidence=0.8, llm_confidence=0.9)
        expected = 0.8 * 0.3 + 0.9 * 0.7
        assert abs(doc.confidence_score - expected) < 0.001

    def test_confidence_score_only_llm(self):
        doc = RecognizedDocument(ocr_confidence=0.0, llm_confidence=0.85)
        assert doc.confidence_score == 0.85

    def test_confidence_score_only_ocr(self):
        doc = RecognizedDocument(ocr_confidence=0.75, llm_confidence=0.0)
        assert doc.confidence_score == 0.75


# ═══════════════════════════════════════════════════════════
# 8. Тест полного пайплайна (мок LLM)
# ═══════════════════════════════════════════════════════════


class TestProcessDocumentImageMocked:
    """Тесты process_document_image с моками OCR и LLM."""

    @pytest.mark.asyncio
    async def test_pipeline_with_mocked_llm(self):
        """Полный пайплайн с мок-LLM."""
        from app.services.ocr_service import process_document_image
        from app.services.openrouter_client import LLMResponse

        # Создаём тестовое изображение
        import cv2
        img = np.zeros((200, 400, 3), dtype=np.uint8)
        img[:] = (255, 255, 255)
        cv2.putText(img, "Invoice 123", (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
        success, encoded = cv2.imencode(".jpg", img)
        assert success
        image_data = encoded.tobytes()

        # Мок LLM-ответа
        llm_json = json.dumps({
            "doc_type": "invoice",
            "doc_number": "123",
            "doc_date": "01.01.2025",
            "seller": {"name": "ООО Тест", "inn": "7707083893"},
            "buyer": {"name": "ООО Покупатель", "inn": "7719261250"},
            "items": [{"name": "Услуга", "quantity": 1, "total_with_vat": "100.00"}],
            "total_without_vat": "83.33",
            "vat_amount": "16.67",
            "total_with_vat": "100.00",
            "confidence": 0.85,
        })

        mock_llm_response = LLMResponse(
            content=llm_json,
            model="anthropic/claude-sonnet-4-20250514",
            tokens_input=1000,
            tokens_output=500,
        )

        mock_client = AsyncMock()
        mock_client.chat_completion_with_image = AsyncMock(return_value=mock_llm_response)
        mock_client.chat_completion = AsyncMock(return_value=mock_llm_response)

        # Мокаем Tesseract чтобы не требовать его установки
        with patch("app.services.ocr_service.extract_text_tesseract") as mock_tesseract:
            mock_tesseract.return_value = OcrTextResult(
                text="Invoice 123 some text",
                engine="tesseract",
                confidence=0.75,
            )

            result = await process_document_image(
                file_data=image_data,
                file_type=FileType.JPG,
                openrouter_client=mock_client,
            )

        assert isinstance(result, RecognizedDocument)
        assert result.doc_type == DocumentType.INVOICE
        assert result.doc_number == "123"
        assert result.total_with_vat == Decimal("100.00")
        assert result.llm_model == "anthropic/claude-sonnet-4-20250514"
        assert result.ocr_engine == "tesseract"

    @pytest.mark.asyncio
    async def test_pipeline_unsupported_filetype(self):
        """Неподдерживаемый тип файла → error."""
        from app.services.ocr_service import process_document_image

        result = await process_document_image(
            file_data=b"some data",
            file_type=FileType.CSV,
        )

        assert not result.is_valid
        assert any("Неподдерживаемый" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_pipeline_llm_error_captured(self):
        """Ошибка LLM → captured в errors."""
        from app.services.ocr_service import process_document_image

        import cv2
        img = np.zeros((100, 200, 3), dtype=np.uint8)
        success, encoded = cv2.imencode(".jpg", img)
        image_data = encoded.tobytes()

        mock_client = AsyncMock()
        mock_client.chat_completion_with_image = AsyncMock(
            side_effect=Exception("LLM API error")
        )

        with patch("app.services.ocr_service.extract_text_tesseract") as mock_tesseract:
            mock_tesseract.return_value = OcrTextResult(
                text="some text", engine="tesseract", confidence=0.5,
            )

            result = await process_document_image(
                file_data=image_data,
                file_type=FileType.JPG,
                openrouter_client=mock_client,
            )

        assert not result.is_valid
        assert any("LLM" in e for e in result.errors)