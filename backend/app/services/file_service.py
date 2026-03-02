"""
Сервис загрузки и управления файлами.
Справочник: СПРАВОЧНИК_СУЩНОСТЕЙ.md → services/file_service.py
"""

import uuid
from datetime import date
from pathlib import Path

import aiofiles
from fastapi import UploadFile
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.enums import FileType, ProcessingStatus
from app.core.config import settings
from app.models.uploaded_file import UploadedFile
from app.utils.file_utils import (
    detect_file_type,
    get_processing_pipeline,
    sanitize_filename,
    validate_file_extension,
    validate_file_size,
)


class FileService:
    """Сервис для загрузки, хранения и управления файлами."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def upload_file(
        self,
        file: UploadFile,
        user_id: uuid.UUID,
    ) -> UploadedFile:
        """
        Загрузить один файл: валидация → сохранение на диск → запись в БД.

        Args:
            file: Загружаемый файл из FastAPI
            user_id: ID текущего пользователя

        Returns:
            Объект UploadedFile

        Raises:
            ValueError: Если файл не прошёл валидацию
        """
        filename = file.filename or "unknown"
        safe_filename = sanitize_filename(filename)

        # 1. Валидация расширения
        if not validate_file_extension(safe_filename):
            raise ValueError(
                f"Недопустимый формат файла: {safe_filename}. "
                f"Допустимые: XML, CSV, XLS, XLSX, PDF, JPG, PNG, TIFF, HEIC"
            )

        # 2. Читаем содержимое файла
        content = await file.read()
        file_size = len(content)

        # 3. Валидация размера
        if not validate_file_size(file_size, settings.max_file_size_bytes):
            raise ValueError(
                f"Файл {safe_filename} слишком большой: {file_size / 1024 / 1024:.1f} МБ. "
                f"Максимум: {settings.MAX_FILE_SIZE_MB} МБ"
            )

        # 4. Определяем тип файла
        file_type = detect_file_type(safe_filename, file.content_type)

        # 5. Формируем путь хранения: storage/uploads/{user_id}/{date}/{uuid}_{filename}
        today = date.today().isoformat()
        file_uuid = uuid.uuid4().hex[:12]
        relative_dir = Path(str(user_id)) / today
        stored_filename = f"{file_uuid}_{safe_filename}"
        relative_path = relative_dir / stored_filename

        # Абсолютный путь для сохранения
        absolute_dir = settings.upload_path / relative_dir
        absolute_dir.mkdir(parents=True, exist_ok=True)
        absolute_path = settings.upload_path / relative_path

        # 6. Сохраняем файл на диск асинхронно
        async with aiofiles.open(str(absolute_path), "wb") as f:
            await f.write(content)

        # 7. Определяем MIME-тип
        mime_type = file.content_type

        # 8. Создаём запись в БД
        uploaded_file = UploadedFile(
            user_id=user_id,
            original_filename=safe_filename,
            stored_path=str(relative_path),
            file_type=file_type,
            file_size=file_size,
            mime_type=mime_type,
            processing_status=ProcessingStatus.QUEUED,
        )
        self.db.add(uploaded_file)
        await self.db.flush()
        await self.db.refresh(uploaded_file)

        return uploaded_file

    async def get_file_by_id(
        self,
        file_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> UploadedFile | None:
        """
        Получить файл по ID (только файлы текущего пользователя).

        Args:
            file_id: ID файла
            user_id: ID текущего пользователя

        Returns:
            UploadedFile или None
        """
        result = await self.db.execute(
            select(UploadedFile).where(
                UploadedFile.id == file_id,
                UploadedFile.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_files_list(
        self,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        processing_status: ProcessingStatus | None = None,
        file_type: FileType | None = None,
    ) -> tuple[list[UploadedFile], int]:
        """
        Получить список файлов пользователя с пагинацией и фильтрами.

        Args:
            user_id: ID текущего пользователя
            page: Номер страницы
            page_size: Размер страницы
            processing_status: Фильтр по статусу обработки
            file_type: Фильтр по типу файла

        Returns:
            Кортеж (список файлов, общее количество)
        """
        # Базовый запрос с фильтрацией по user_id
        query = select(UploadedFile).where(UploadedFile.user_id == user_id)
        count_query = select(func.count(UploadedFile.id)).where(
            UploadedFile.user_id == user_id
        )

        # Дополнительные фильтры
        if processing_status is not None:
            query = query.where(UploadedFile.processing_status == processing_status)
            count_query = count_query.where(
                UploadedFile.processing_status == processing_status
            )

        if file_type is not None:
            query = query.where(UploadedFile.file_type == file_type)
            count_query = count_query.where(UploadedFile.file_type == file_type)

        # Общее количество
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Сортировка и пагинация
        offset = (page - 1) * page_size
        query = query.order_by(desc(UploadedFile.created_at)).offset(offset).limit(page_size)

        result = await self.db.execute(query)
        files = list(result.scalars().all())

        return files, total

    async def delete_file(
        self,
        file_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """
        Удалить файл (из БД и с диска).

        Args:
            file_id: ID файла
            user_id: ID текущего пользователя

        Returns:
            True если файл был удалён, False если не найден
        """
        uploaded_file = await self.get_file_by_id(file_id, user_id)
        if uploaded_file is None:
            return False

        # Удаляем файл с диска
        absolute_path = settings.upload_path / uploaded_file.stored_path
        try:
            if absolute_path.exists():
                absolute_path.unlink()
        except OSError:
            # Логируем, но не прерываем удаление из БД
            pass

        # Удаляем запись из БД
        await self.db.delete(uploaded_file)
        await self.db.flush()

        return True

    def get_pipeline_for_file(self, uploaded_file: UploadedFile) -> str:
        """
        Определить пайплайн обработки для загруженного файла.

        Args:
            uploaded_file: Объект файла

        Returns:
            Название пайплайна
        """
        if uploaded_file.file_type:
            return get_processing_pipeline(uploaded_file.file_type)
        return "unknown"