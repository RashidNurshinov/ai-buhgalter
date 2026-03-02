"""
API роутер: расчёт налогов.
Пункт плана: 1.12.4

Эндпоинты:
- POST /api/v1/taxes/calculate — рассчитать налог(и) за период
- GET  /api/v1/taxes/ — список сохранённых расчётов
- GET  /api/v1/taxes/summary — сводка по всем налогам за период
- GET  /api/v1/taxes/history — история расчётов
- POST /api/v1/taxes/ndfl — расчёт НДФЛ за сотрудника
- POST /api/v1/taxes/insurance — расчёт страховых взносов за сотрудника
"""

import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.enums import (
    CalculationStatus,
    PeriodType,
    TaxType,
)
from app.core.dependencies import get_current_user, get_db
from app.models.tax_calculation import TaxCalculation
from app.models.user import User
from app.schemas.tax import (
    InsuranceCalculationRequest,
    InsuranceResultResponse,
    IpContributionsResultResponse,
    NdflCalculationRequest,
    NdflResultResponse,
    TaxCalculationRequest,
    TaxCalculationResponse,
    TaxSummaryResponse,
    UsnResultResponse,
    VatResultResponse,
)
from app.services.tax_calculation_service import (
    TaxCalculationService,
    get_quarter_dates,
    get_year_dates,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/taxes", tags=["taxes"])


# ─── POST /taxes/calculate — расчёт налога ────────────────────


@router.post(
    "/calculate",
    response_model=TaxSummaryResponse,
    summary="Рассчитать налоги за период",
    description=(
        "Рассчитывает налоги за указанный период и сохраняет результаты. "
        "Если tax_type не указан — рассчитывает все налоги (УСН, НДС, взносы ИП)."
    ),
)
async def calculate_taxes(
    request: TaxCalculationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaxSummaryResponse:
    """Рассчитать налоги за период."""
    service = TaxCalculationService(db, current_user)

    year = request.year
    quarter = request.quarter
    tax_type = request.tax_type

    # Определяем период для ответа
    if quarter:
        period_start, period_end = get_quarter_dates(year, quarter)
    else:
        period_start, period_end = get_year_dates(year)

    usn_response = None
    vat_response = None
    ip_response = None
    total_payable = Decimal("0")
    warnings: list[str] = []

    # УСН
    if tax_type is None or tax_type == TaxType.USN:
        if quarter:
            usn_result = await service.calculate_usn_advance(year, quarter)
        else:
            usn_result = await service.calculate_usn(year, period_type=PeriodType.YEAR)

        # Сохраняем в БД
        await service.save_calculation(
            tax_type=TaxType.USN,
            period_type=PeriodType.QUARTER if quarter else PeriodType.YEAR,
            period_start=period_start,
            period_end=period_end,
            result_data=usn_result,
        )

        usn_response = UsnResultResponse(
            income_total=usn_result.income_total,
            expense_total=usn_result.expense_total,
            tax_base=usn_result.tax_base,
            tax_rate=usn_result.tax_rate,
            tax_amount=usn_result.tax_amount,
            min_tax_amount=usn_result.min_tax_amount,
            is_minimum_tax=usn_result.is_minimum_tax,
            insurance_deduction=usn_result.insurance_deduction,
            previous_advances=usn_result.previous_advances,
            tax_to_pay=usn_result.tax_to_pay,
            warnings=usn_result.warnings,
            details=usn_result.details,
        )
        total_payable += usn_result.tax_to_pay
        warnings.extend(usn_result.warnings)

    # НДС
    if tax_type is None or tax_type == TaxType.VAT:
        target_quarter = quarter or 4
        vat_result = await service.calculate_vat(year, target_quarter)

        # Сохраняем в БД
        q_start, q_end = get_quarter_dates(year, target_quarter)
        await service.save_calculation(
            tax_type=TaxType.VAT,
            period_type=PeriodType.QUARTER,
            period_start=q_start,
            period_end=q_end,
            result_data=vat_result,
        )

        vat_response = VatResultResponse(
            quarter=target_quarter,
            year=year,
            vat_charged=vat_result.vat_charged,
            vat_deductible=vat_result.vat_deductible,
            vat_payable=vat_result.vat_payable,
            monthly_payments=vat_result.monthly_payments,
            warnings=vat_result.warnings,
            details=vat_result.details,
        )
        if vat_result.vat_payable > Decimal("0"):
            total_payable += vat_result.vat_payable
        warnings.extend(vat_result.warnings)

    # Взносы ИП за себя
    if tax_type is None or tax_type == TaxType.INSURANCE_IP:
        ip_result = await service.calculate_ip_fixed_contributions(year)

        # Сохраняем в БД
        y_start, y_end = get_year_dates(year)
        await service.save_calculation(
            tax_type=TaxType.INSURANCE_IP,
            period_type=PeriodType.YEAR,
            period_start=y_start,
            period_end=y_end,
            result_data=ip_result,
        )

        ip_response = IpContributionsResultResponse(
            fixed_amount=ip_result.fixed_amount,
            additional_amount=ip_result.additional_amount,
            total_amount=ip_result.total_amount,
            income_for_calculation=ip_result.income_for_calculation,
            already_paid=ip_result.already_paid,
            remaining=ip_result.remaining,
            warnings=ip_result.warnings,
            details=ip_result.details,
        )
        total_payable += ip_result.remaining
        warnings.extend(ip_result.warnings)

    await db.commit()

    return TaxSummaryResponse(
        period_start=period_start,
        period_end=period_end,
        usn=usn_response,
        vat=vat_response,
        ip_contributions=ip_response,
        total_payable=total_payable,
        warnings=warnings,
    )


# ─── GET /taxes/summary — сводка за период ────────────────────


@router.get(
    "/summary",
    response_model=TaxSummaryResponse,
    summary="Сводка по налогам за период",
    description="Получить последние расчёты по всем налогам за указанный год/квартал.",
)
async def get_tax_summary(
    year: int = Query(..., ge=2020, le=2030, description="Год"),
    quarter: int | None = Query(None, ge=1, le=4, description="Квартал"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaxSummaryResponse:
    """Получить сводку по налогам (без пересчёта — из последних сохранённых)."""
    if quarter:
        period_start, period_end = get_quarter_dates(year, quarter)
    else:
        period_start, period_end = get_year_dates(year)

    # Ищем последние расчёты в БД
    usn_response = None
    vat_response = None
    ip_response = None
    total_payable = Decimal("0")
    warnings: list[str] = []

    # УСН
    usn_calc = await _get_latest_calculation(
        db, current_user.id, TaxType.USN, period_start, period_end
    )
    if usn_calc:
        details = usn_calc.details_json or {}
        usn_response = UsnResultResponse(
            income_total=usn_calc.income_total,
            expense_total=usn_calc.expense_total,
            tax_base=usn_calc.tax_base,
            tax_rate=usn_calc.tax_rate,
            tax_amount=usn_calc.tax_amount,
            min_tax_amount=usn_calc.min_tax_amount or Decimal("0"),
            is_minimum_tax=bool(
                usn_calc.min_tax_amount
                and usn_calc.min_tax_amount > Decimal("0")
                and usn_calc.tax_amount == usn_calc.min_tax_amount
            ),
            insurance_deduction=usn_calc.insurance_deduction or Decimal("0"),
            previous_advances=Decimal("0"),
            tax_to_pay=usn_calc.tax_amount,
            warnings=[],
            details=details,
        )
        total_payable += usn_calc.tax_amount
    else:
        warnings.append("Расчёт УСН за этот период не найден. Выполните расчёт.")

    # НДС
    target_quarter = quarter or 4
    q_start, q_end = get_quarter_dates(year, target_quarter)
    vat_calc = await _get_latest_calculation(
        db, current_user.id, TaxType.VAT, q_start, q_end
    )
    if vat_calc:
        details = vat_calc.details_json or {}
        vat_response = VatResultResponse(
            quarter=target_quarter,
            year=year,
            vat_charged=vat_calc.vat_charged or Decimal("0"),
            vat_deductible=vat_calc.vat_deductible or Decimal("0"),
            vat_payable=vat_calc.vat_payable or Decimal("0"),
            monthly_payments=details.get("monthly_payments", []),
            warnings=[],
            details=details,
        )
        if vat_calc.vat_payable and vat_calc.vat_payable > Decimal("0"):
            total_payable += vat_calc.vat_payable
    else:
        warnings.append("Расчёт НДС за этот период не найден. Выполните расчёт.")

    # Взносы ИП
    y_start, y_end = get_year_dates(year)
    ip_calc = await _get_latest_calculation(
        db, current_user.id, TaxType.INSURANCE_IP, y_start, y_end
    )
    if ip_calc:
        details = ip_calc.details_json or {}
        ip_response = IpContributionsResultResponse(
            fixed_amount=Decimal(details.get("fixed", "0")),
            additional_amount=Decimal(details.get("additional", "0")),
            total_amount=ip_calc.tax_amount,
            income_for_calculation=ip_calc.income_total,
            already_paid=Decimal(details.get("already_paid", "0")),
            remaining=Decimal(details.get("remaining", "0")),
            warnings=[],
            details=details,
        )
        remaining = Decimal(details.get("remaining", "0"))
        total_payable += remaining
    else:
        warnings.append("Расчёт взносов ИП за этот период не найден. Выполните расчёт.")

    return TaxSummaryResponse(
        period_start=period_start,
        period_end=period_end,
        usn=usn_response,
        vat=vat_response,
        ip_contributions=ip_response,
        total_payable=total_payable,
        warnings=warnings,
    )


# ─── GET /taxes/ — список расчётов ────────────────────────────


@router.get(
    "/",
    response_model=list[TaxCalculationResponse],
    summary="Список сохранённых расчётов",
)
async def list_calculations(
    year: int | None = Query(None, ge=2020, le=2030, description="Фильтр по году"),
    tax_type: TaxType | None = Query(None, description="Фильтр по типу налога"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[TaxCalculationResponse]:
    """Получить список сохранённых расчётов налогов."""
    query = select(TaxCalculation).where(
        TaxCalculation.user_id == current_user.id
    )

    if year:
        query = query.where(
            TaxCalculation.period_start >= f"{year}-01-01",
            TaxCalculation.period_end <= f"{year}-12-31",
        )

    if tax_type:
        query = query.where(TaxCalculation.tax_type == tax_type)

    query = query.order_by(desc(TaxCalculation.created_at)).offset(skip).limit(limit)

    result = await db.execute(query)
    calculations = list(result.scalars().all())

    return [TaxCalculationResponse.model_validate(c) for c in calculations]


# ─── GET /taxes/history — история расчётов ─────────────────────


@router.get(
    "/history",
    response_model=list[TaxCalculationResponse],
    summary="История расчётов",
    description="Все расчёты, упорядоченные по дате создания.",
)
async def get_calculations_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[TaxCalculationResponse]:
    """История всех расчётов."""
    result = await db.execute(
        select(TaxCalculation)
        .where(TaxCalculation.user_id == current_user.id)
        .order_by(desc(TaxCalculation.created_at))
        .offset(skip)
        .limit(limit)
    )
    calculations = list(result.scalars().all())
    return [TaxCalculationResponse.model_validate(c) for c in calculations]


# ─── POST /taxes/ndfl — расчёт НДФЛ ──────────────────────────


@router.post(
    "/ndfl",
    response_model=NdflResultResponse,
    summary="Рассчитать НДФЛ за сотрудника",
    description="Расчёт НДФЛ за одного сотрудника за месяц (13%/15%).",
)
async def calculate_ndfl(
    request: NdflCalculationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NdflResultResponse:
    """Рассчитать НДФЛ за сотрудника."""
    service = TaxCalculationService(db, current_user)
    result = await service.calculate_ndfl_employee(
        gross_salary=request.gross_salary,
        cumulative_income=request.cumulative_income,
    )

    return NdflResultResponse(
        gross_salary=result.gross_salary,
        ndfl_amount=result.ndfl_amount,
        net_salary=result.net_salary,
        rate_applied=result.rate_applied,
        details=result.details,
    )


# ─── POST /taxes/insurance — расчёт страховых взносов ─────────


@router.post(
    "/insurance",
    response_model=InsuranceResultResponse,
    summary="Рассчитать страховые взносы за сотрудника",
    description="Расчёт страховых взносов за одного сотрудника за месяц (30%/15.1%).",
)
async def calculate_insurance(
    request: InsuranceCalculationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InsuranceResultResponse:
    """Рассчитать страховые взносы за сотрудника."""
    service = TaxCalculationService(db, current_user)
    result = await service.calculate_insurance_contributions_employee(
        gross_salary=request.gross_salary,
        cumulative_base=request.cumulative_base,
    )

    return InsuranceResultResponse(
        gross_salary=result.gross_salary,
        contributions_total=result.contributions_total,
        rate_applied=result.rate_applied,
        cumulative_base=result.cumulative_base,
        details=result.details,
    )


# ─── Вспомогательные функции ──────────────────────────────────


async def _get_latest_calculation(
    db: AsyncSession,
    user_id,
    tax_type: TaxType,
    period_start,
    period_end,
) -> TaxCalculation | None:
    """Получить последний расчёт указанного типа за период."""
    result = await db.execute(
        select(TaxCalculation)
        .where(
            and_(
                TaxCalculation.user_id == user_id,
                TaxCalculation.tax_type == tax_type,
                TaxCalculation.period_start == period_start,
                TaxCalculation.period_end == period_end,
            )
        )
        .order_by(desc(TaxCalculation.updated_at))
        .limit(1)
    )
    return result.scalar_one_or_none()