"""
Тесты загрузки файлов (пункт 1.5.9).

Тестируем:
- FileService: upload_file, get_file_by_id, get_files_list, delete_file
- Валидация формата и размера файлов
- Определение пайплайна обработки
- file_utils: detect_file_type, sanitize_filename, validate_file_extension, validate_file_size
"""

import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.constants.enums import FileType, ProcessingStatus
from app.schemas.uploaded_file import (
    FileUploadResult,
    MultiUploadResponse,
    UploadedFileResponse,
    UploadedFileShortResponse,
)
from app.utils.file_utils import (
    detect_file_type,
    get_processing_pipeline,
    sanitize_filename,
    validate_file_extension,
    validate_file_size,
)


# ─── detect_file_type ───────────────────────────────────────


class TestDetectFileType:
    """Тесты определения типа файла."""

    def test_detect_pdf(self):
        assert detect_file_type("document.pdf") == FileType.PDF

    def test_detect_xml(self):
        assert detect_file_type("invoice.xml") == FileType.XML

    def test_detect_csv(self):
        assert detect_file_type("statement.csv") == FileType.CSV

    def test_detect_xls(self):
        assert detect_file_type("data.xls") == FileType.XLS

    def test_detect_xlsx(self):
        assert detect_file_type("report.xlsx") == FileType.XLSX

    def test_detect_jpg(self):
        assert detect_file_type("photo.jpg") == FileType.JPG

    def test_detect_jpeg(self):
        assert detect_file_type("photo.jpeg") == FileType.JPEG

    def test_detect_png(self):
        assert detect_file_type("scan.png") == FileType.PNG

    def test_detect_tiff(self):
        assert detect_file_type("scan.tiff") == FileType.TIFF

    def test_detect_tif(self):
        assert detect_file_type("scan.tif") == FileType.TIFF

    def test_detect_heic(self):
        assert detect_file_type("photo.heic") == FileType.HEIC

    def test_detect_unknown_extension(self):
        assert detect_file_type("file.unknown") == FileType.OTHER

    def test_detect_by_content_type_fallback(self):
        """Fallback по MIME-типу если расширение неизвестно."""
        assert detect_file_type("file", "application/pdf") == FileType.PDF
        assert detect_file_type("file", "image/jpeg") == FileType.JPG
        assert detect_file_type("file", "text/xml") == FileType.XML

    def test_detect_case_insensitive(self):
        """Расширение не зависит от регистра."""
        assert detect_file_type("DOC.PDF") == FileType.PDF
        assert detect_file_type("photo.JPG") == FileType.JPG
        assert detect_file_type("data.Xlsx") == FileType.XLSX


# ─── validate_file_extension ────────────────────────────────


class TestValidateFileExtension:
    """Тесты валидации расширений."""

    def test_allowed_extensions(self):
        allowed = ["test.pdf", "test.xml", "test.csv", "test.xls",
                    "test.xlsx", "test.jpg", "test.jpeg", "test.png",
                    "test.tiff", "test.tif", "test.heic"]
        for fn in allowed:
            assert validate_file_extension(fn) is True, f"Ожидали допустимый: {fn}"

    def test_disallowed_extensions(self):
        disallowed = ["test.exe", "test.sh", "test.py", "test.zip",
                      "test.doc", "test.docx", "test.txt", "test"]
        for fn in disallowed:
            assert validate_file_extension(fn) is False, f"Ожидали недопустимый: {fn}"


# ─── validate_file_size ─────────────────────────────────────


class TestValidateFileSize:
    """Тесты валидации размера файлов."""

    def test_within_limit(self):
        assert validate_file_size(1024, 50 * 1024 * 1024) is True

    def test_at_limit(self):
        max_size = 50 * 1024 * 1024
        assert validate_file_size(max_size, max_size) is True

    def test_exceeds_limit(self):
        max_size = 50 * 1024 * 1024
        assert validate_file_size(max_size + 1, max_size) is False

    def test_zero_size(self):
        assert validate_file_size(0, 50 * 1024 * 1024) is True


# ─── sanitize_filename ──────────────────────────────────────


class TestSanitizeFilename:
    """Тесты очистки имени файла."""

    def test_normal_filename(self):
        assert sanitize_filename("invoice.pdf") == "invoice.pdf"

    def test_path_traversal(self):
        """Удаление path traversal."""
        result = sanitize_filename("../../etc/passwd")
        assert ".." not in result
        assert "/" not in result

    def test_backslash_removal(self):
        result = sanitize_filename("C:\\Users\\test\\doc.pdf")
        assert "\\" not in result

    def test_null_byte(self):
        result = sanitize_filename("file\x00.pdf")
        assert "\x00" not in result

    def test_long_filename(self):
        """Длинное имя файла обрезается до 255 символов."""
        long_name = "a" * 300 + ".pdf"
        result = sanitize_filename(long_name)
        assert len(result) <= 255
        assert result.endswith(".pdf")

    def test_cyrillic_filename(self):
        """Кириллические имена сохраняются."""
        assert sanitize_filename("счёт_фактура.pdf") == "счёт_фактура.pdf"


# ─── get_processing_pipeline ────────────────────────────────


class TestGetProcessingPipeline:
    """Тесты определения пайплайна обработки."""

    def test_ocr_pipeline(self):
        for ft in [FileType.JPG, FileType.JPEG, FileType.PNG, FileType.TIFF, FileType.HEIC]:
            assert get_processing_pipeline(ft) == "ocr", f"Ожидали OCR для {ft}"

    def test_xml_parser(self):
        assert get_processing_pipeline(FileType.XML) == "xml_parser"

    def test_table_parser(self):
        for ft in [FileType.CSV, FileType.XLS, FileType.XLSX]:
            assert get_processing_pipeline(ft) == "table_parser", f"Ожидали table_parser для {ft}"

    def test_pdf_parser(self):
        assert get_processing_pipeline(FileType.PDF) == "pdf_parser"

    def test_unknown_pipeline(self):
        assert get_processing_pipeline(FileType.OTHER) == "unknown"


# ─── FileService ────────────────────────────────────────────


class TestFileServiceUpload:
    """Тесты FileService.upload_file."""

    @pytest.mark.asyncio
    async def test_upload_invalid_extension(self):
        """Загрузка файла с недопустимым расширением → ValueError."""
        from app.services.file_service import FileService

        mock_db = AsyncMock()
        service = FileService(mock_db)

        mock_file = MagicMock()
        mock_file.filename = "virus.exe"
        mock_file.read = AsyncMock(return_value=b"content")
        mock_file.content_type = "application/octet-stream"

        with pytest.raises(ValueError, match="Недопустимый формат"):
            await service.upload_file(mock_file, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_upload_too_large(self):
        """Загрузка слишком большого файла → ValueError."""
        from app.services.file_service import FileService

        mock_db = AsyncMock()
        service = FileService(mock_db)

        # Создаём файл «побольше лимита»
        big_content = b"x" * (60 * 1024 * 1024)  # 60 MB

        mock_file = MagicMock()
        mock_file.filename = "huge.pdf"
        mock_file.read = AsyncMock(return_value=big_content)
        mock_file.content_type = "application/pdf"

        with pytest.raises(ValueError, match="слишком большой"):
            await service.upload_file(mock_file, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_upload_success(self, tmp_path):
        """Успешная загрузка файла."""
        from app.services.file_service import FileService

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()

        service = FileService(mock_db)

        mock_file = MagicMock()
        mock_file.filename = "invoice.pdf"
        mock_file.read = AsyncMock(return_value=b"PDF content here")
        mock_file.content_type = "application/pdf"

        user_id = uuid.uuid4()

        with patch("app.services.file_service.settings") as mock_settings:
            mock_settings.upload_path = tmp_path
            mock_settings.max_file_size_bytes = 50 * 1024 * 1024
            mock_settings.MAX_FILE_SIZE_MB = 50

            result = await service.upload_file(mock_file, user_id)

        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_file_by_id_not_found(self):
        """Файл не найден → None."""
        from app.services.file_service import FileService

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        service = FileService(mock_db)
        result = await service.get_file_by_id(uuid.uuid4(), uuid.uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_file_not_found(self):
        """Удаление несуществующего файла → False."""
        from app.services.file_service import FileService

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        service = FileService(mock_db)
        result = await service.delete_file(uuid.uuid4(), uuid.uuid4())
        assert result is False


# ─── Pydantic-схемы файлов ──────────────────────────────────


class TestFileSchemas:
    """Тесты Pydantic-схем загрузки файлов."""

    def test_file_upload_result(self):
        result = FileUploadResult(
            file_id=uuid.uuid4(),
            filename="test.pdf",
            file_type=FileType.PDF,
            file_size=1024,
            processing_status=ProcessingStatus.QUEUED,
            pipeline="pdf_parser",
        )
        assert result.pipeline == "pdf_parser"

    def test_multi_upload_response(self):
        resp = MultiUploadResponse(
            uploaded=[],
            errors=[{"filename": "bad.exe", "error": "Недопустимый формат"}],
            total_uploaded=0,
            total_errors=1,
        )
        assert resp.total_errors == 1

    def test_uploaded_file_short_response(self):
        resp = UploadedFileShortResponse(
            id=uuid.uuid4(),
            original_filename="invoice.xml",
            file_type=FileType.XML,
            file_size=4096,
            processing_status=ProcessingStatus.COMPLETED,
            created_at=datetime.now(timezone.utc),
        )
        assert resp.processing_status == ProcessingStatus.COMPLETED