"""
Главный роутер API v1. Подключает все под-роутеры.
"""

from fastapi import APIRouter

router = APIRouter()


# === Подключённые роутеры ===
from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router
from app.api.v1.files import router as files_router

router.include_router(auth_router)
router.include_router(users_router)
router.include_router(files_router)

from app.api.v1.agent import router as agent_router

router.include_router(agent_router)

from app.api.v1.operations import router as operations_router

router.include_router(operations_router)

# === Учётные книги ===
from app.api.v1.kudir import router as kudir_router
from app.api.v1.purchase_book import router as purchase_book_router
from app.api.v1.sales_book import router as sales_book_router

router.include_router(kudir_router)
router.include_router(purchase_book_router)
router.include_router(sales_book_router)

# === Налоги ===
from app.api.v1.taxes import router as taxes_router

router.include_router(taxes_router)

# === Декларации ===
from app.api.v1.declarations import router as declarations_router

router.include_router(declarations_router)

# === Налоговый календарь ===
from app.api.v1.calendar import router as calendar_router

router.include_router(calendar_router)

# === Дашборд ===
from app.api.v1.dashboard import router as dashboard_router

router.include_router(dashboard_router)

# === Документы ===
from app.api.v1.documents import router as documents_router

router.include_router(documents_router)
