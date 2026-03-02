"""
Утилиты для работы с файлами: определение типа, валидация формата,
автодетект кодировки и разделителя CSV.
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → utils/file_utils.py
"""

import csv
import io
import logging
import mimetypes
from pathlib import Path

import chardet

from app.constants.enums import FileType

logger = logging.getLogger(__name__)

# Допустимые расширения файлов → FileType
EXTENSION_TO_FILE_TYPE: dict[str, FileType] = {
    ".pdf": FileType.PDF,
    ".xml": FileType.XML,
    ".csv": FileType.CSV,
    ".xls": FileType.XLS,
    ".xlsx": FileType.XLSX,
    ".jpg": FileType.JPG,
    ".jpeg": FileType.JPEG,
    ".png": FileType.PNG,
    ".tiff": FileType.TIFF,
    ".tif": FileType.TIFF,
    ".heic": FileType.HEIC,
}

# Допустимые MIME-типы
ALLOWED_MIME_TYPES: set[str] = {
    # PDF
    "application/pdf",
    # XML
    "application/xml",
    "text/xml",
    # CSV
    "text/csv",
    "text/plain",
    # Excel
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    # Изображения
    "image/jpeg",
    "image/png",
    "image/tiff",
    "image/heic",
    "image/heif",
}

# Расширения, допустимые для загрузки
ALLOWED_EXTENSIONS: set[str] = set(EXTENSION_TO_FILE_TYPE.keys())

# Типы файлов, которые направляются на OCR-пайплайн
OCR_FILE_TYPES: set[FileType] = {
    FileType.JPG,
    FileType.JPEG,
    FileType.PNG,
    FileType.TIFF,
    FileType.HEIC,
}

# Типы файлов для парсинга структурированных данных
STRUCTURED_FILE_TYPES: set[FileType] = {
    FileType.XML,
    FileType.CSV,
    FileType.XLS,
    FileType.XLSX,
}

# PDF может содержать как текст (парсинг), так и сканы (OCR)
PDF_FILE_TYPE: FileType = FileType.PDF


def detect_file_type(filename: str, content_type: str | None = None) -> FileType:
    """
    Определить тип файла по расширению и MIME-типу.

    Приоритет: расширение файла > content_type из запроса.

    Args:
        filename: Имя файла (original_filename)
        content_type: MIME-тип из HTTP-заголовка

    Returns:
        FileType enum
    """
    # 1. Определяем по расширению
    ext = Path(filename).suffix.lower()
    if ext in EXTENSION_TO_FILE_TYPE:
        return EXTENSION_TO_FILE_TYPE[ext]

    # 2. Fallback: определяем по content_type
    if content_type:
        mime_to_type = {
            "application/pdf": FileType.PDF,
            "application/xml": FileType.XML,
            "text/xml": FileType.XML,
            "text/csv": FileType.CSV,
            "text/plain": FileType.CSV,  # CSV часто приходит как text/plain
            "application/vnd.ms-excel": FileType.XLS,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": FileType.XLSX,
            "image/jpeg": FileType.JPG,
            "image/png": FileType.PNG,
            "image/tiff": FileType.TIFF,
            "image/heic": FileType.HEIC,
            "image/heif": FileType.HEIC,
        }
        if content_type in mime_to_type:
            return mime_to_type[content_type]

    return FileType.OTHER


def validate_file_extension(filename: str) -> bool:
    """
    Проверить, допустимо ли расширение файла.

    Args:
        filename: Имя файла

    Returns:
        True если расширение допустимо
    """
    ext = Path(filename).suffix.lower()
    return ext in ALLOWED_EXTENSIONS


def validate_file_size(file_size: int, max_size_bytes: int) -> bool:
    """
    Проверить, не превышает ли размер файла допустимый лимит.

    Args:
        file_size: Размер файла в байтах
        max_size_bytes: Максимальный допустимый размер в байтах

    Returns:
        True если размер допустим
    """
    return file_size <= max_size_bytes


def get_mime_type(filename: str) -> str | None:
    """
    Определить MIME-тип файла по расширению.

    Args:
        filename: Имя файла

    Returns:
        MIME-тип или None
    """
    mime_type, _ = mimetypes.guess_type(filename)
    return mime_type


def get_processing_pipeline(file_type: FileType) -> str:
    """
    Определить пайплайн обработки для данного типа файла.

    Args:
        file_type: Тип файла

    Returns:
        Название пайплайна: 'ocr', 'xml_parser', 'table_parser', 'pdf_parser', 'unknown'
    """
    if file_type in OCR_FILE_TYPES:
        return "ocr"
    elif file_type == FileType.XML:
        return "xml_parser"
    elif file_type in {FileType.CSV, FileType.XLS, FileType.XLSX}:
        return "table_parser"
    elif file_type == FileType.PDF:
        return "pdf_parser"
    else:
        return "unknown"


def sanitize_filename(filename: str) -> str:
    """
    Очистить имя файла от опасных символов.

    Args:
        filename: Оригинальное имя файла

    Returns:
        Безопасное имя файла
    """
    # Убираем путь, оставляем только имя файла
    name = Path(filename).name
    # Заменяем опасные символы
    dangerous_chars = ['..', '/', '\\', '\x00', '~']
    for char in dangerous_chars:
        name = name.replace(char, '_')
    # Ограничиваем длину
    if len(name) > 255:
        ext = Path(name).suffix
        name = name[:255 - len(ext)] + ext
    return name


# ─── CSV утилиты (1.7.5, 1.7.6) ────────────────────────────────


def detect_encoding(file_data: bytes, sample_size: int = 65536) -> str:
    """
    Автодетект кодировки CSV/текстового файла с помощью chardet.

    Сначала проверяет BOM-маркеры, затем chardet.
    Типичные кодировки российских банковских выписок:
    - UTF-8 (с BOM и без)
    - Windows-1251 (cp1251) — наиболее частая для российских банков
    - KOI8-R — устаревшая, но встречается

    Args:
        file_data: Байтовое содержимое файла
        sample_size: Размер выборки для анализа (по умолчанию 64KB)

    Returns:
        Название кодировки (например, 'utf-8', 'windows-1251')
    """
    if not file_data:
        return "utf-8"

    # 1. Проверка BOM-маркеров
    if file_data.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if file_data.startswith(b"\xff\xfe"):
        return "utf-16-le"
    if file_data.startswith(b"\xfe\xff"):
        return "utf-16-be"

    # 2. chardet анализ
    sample = file_data[:sample_size]
    detected = chardet.detect(sample)

    encoding = detected.get("encoding", "utf-8") or "utf-8"
    confidence = detected.get("confidence", 0) or 0

    logger.debug(
        f"Определена кодировка: {encoding} (уверенность: {confidence:.2f})"
    )

    # 3. Нормализация названий кодировок
    encoding_lower = encoding.lower()
    encoding_map = {
        "ascii": "utf-8",  # ASCII совместим с UTF-8
        "iso-8859-5": "windows-1251",  # Часто путает с cp1251
        "maccyrillic": "windows-1251",  # Mac Cyrillic → cp1251
        "ibm866": "windows-1251",  # IBM866 → cp1251 для CSV
        "iso-8859-1": "windows-1251",  # Latin-1 → скорее всего cp1251 для рус. файлов
    }
    if encoding_lower in encoding_map:
        encoding = encoding_map[encoding_lower]

    # 4. Валидация: пробуем декодировать
    try:
        file_data[:min(len(file_data), 4096)].decode(encoding)
    except (UnicodeDecodeError, LookupError):
        logger.warning(
            f"Не удалось декодировать с {encoding}, fallback на windows-1251"
        )
        try:
            file_data[:min(len(file_data), 4096)].decode("windows-1251")
            encoding = "windows-1251"
        except UnicodeDecodeError:
            encoding = "utf-8"

    return encoding


def detect_delimiter(
    text: str,
    candidates: tuple[str, ...] = (";", ",", "\t", "|"),
    sample_lines: int = 20,
) -> str:
    """
    Автодетект разделителя CSV по содержимому текста.

    Использует csv.Sniffer + эвристику по частоте символов.
    Российские банковские выписки чаще всего используют ';' (точка с запятой).

    Args:
        text: Текстовое содержимое файла (декодированное)
        candidates: Возможные разделители
        sample_lines: Количество строк для анализа

    Returns:
        Символ-разделитель (например, ';', ',', '\\t')
    """
    if not text or not text.strip():
        return ";"

    # Берём выборку строк
    lines = text.strip().splitlines()[:sample_lines]
    sample = "\n".join(lines)

    # 1. Пробуем csv.Sniffer
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters="".join(candidates))
        if dialect.delimiter in candidates:
            logger.debug(f"csv.Sniffer определил разделитель: '{dialect.delimiter}'")
            return dialect.delimiter
    except csv.Error:
        pass

    # 2. Эвристика: считаем частоту каждого кандидата в строках
    # Хороший разделитель встречается одинаковое количество раз в каждой строке
    best_delimiter = ";"
    best_score = -1

    for delim in candidates:
        counts = []
        for line in lines:
            if line.strip():
                counts.append(line.count(delim))

        if not counts or max(counts) == 0:
            continue

        # Все строки должны иметь одинаковое количество разделителей
        # (или почти одинаковое — допускаем заголовок)
        non_zero = [c for c in counts if c > 0]
        if not non_zero:
            continue

        # Считаем «консистентность» — доля строк с одинаковым количеством
        from collections import Counter
        freq = Counter(non_zero)
        most_common_count, most_common_freq = freq.most_common(1)[0]

        # Оценка: (количество колонок) * (доля одинаковых строк)
        consistency = most_common_freq / len(non_zero)
        score = most_common_count * consistency

        if score > best_score:
            best_score = score
            best_delimiter = delim

    logger.debug(
        f"Эвристика определила разделитель: '{best_delimiter}' (score={best_score:.2f})"
    )
    return best_delimiter