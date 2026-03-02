"""
Сервис экспорта данных в Excel и PDF.
Пункт плана: 1.11

Методы:
- export_kudir_excel() — КУДиР в Excel (формат по приказу ФНС ЕА-7-3/816@)
- export_kudir_pdf() — КУДиР в PDF
- export_purchase_book_excel() — Книга покупок в Excel
- export_sales_book_excel() — Книга продаж в Excel
- export_declaration_pdf_preview() — PDF-предпросмотр декларации

Зависимости: openpyxl, reportlab (уже в requirements.txt)
"""

import io
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import (
    Alignment,
    Border,
    Font,
    PatternFill,
    Side,
)
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.models.book_entry import PurchaseBookEntry, SalesBookEntry
from app.models.kudir_entry import KudirEntry

logger = logging.getLogger(__name__)


# ─── Стили Excel ────────────────────────────────────────────

_HEADER_FONT = Font(name="Arial", bold=True, size=10)
_HEADER_FILL = PatternFill(start_color="D9E2F3", end_color="D9E2F3", fill_type="solid")
_TITLE_FONT = Font(name="Arial", bold=True, size=12)
_SUBTITLE_FONT = Font(name="Arial", bold=True, size=10, italic=True)
_DATA_FONT = Font(name="Arial", size=9)
_MONEY_FORMAT = '#,##0.00'
_DATE_FORMAT = 'DD.MM.YYYY'
_THIN_BORDER = Border(
    left=Side(style="thin"),
    right=Side(style="thin"),
    top=Side(style="thin"),
    bottom=Side(style="thin"),
)
_CENTER_ALIGN = Alignment(horizontal="center", vertical="center", wrap_text=True)
_LEFT_ALIGN = Alignment(horizontal="left", vertical="center", wrap_text=True)
_RIGHT_ALIGN = Alignment(horizontal="right", vertical="center")


def _format_money(value: Decimal | None) -> str:
    """Форматирование суммы для отображения."""
    if value is None:
        return "0.00"
    return f"{value:,.2f}".replace(",", " ").replace(".", ",")


def _setup_reportlab_fonts():
    """Регистрация шрифтов для PDF (кириллица)."""
    try:
        # Пробуем стандартные пути
        import os
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/dejavu/DejaVuSans.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/calibri.ttf",
        ]
        for path in font_paths:
            if os.path.exists(path):
                font_name = os.path.splitext(os.path.basename(path))[0]
                pdfmetrics.registerFont(TTFont(font_name, path))
                bold_path = path.replace(".ttf", "Bold.ttf").replace("Sans.", "Sans-Bold.")
                if os.path.exists(bold_path):
                    pdfmetrics.registerFont(TTFont(f"{font_name}-Bold", bold_path))
                return font_name
    except Exception as e:
        logger.warning("Не удалось зарегистрировать шрифт для PDF: %s", e)
    return "Helvetica"


# ═══════════════════════════════════════════════════════════════
# ЭКСПОРТ КУДиР
# ═══════════════════════════════════════════════════════════════


def export_kudir_excel(
    entries: list[KudirEntry],
    totals: dict[str, Any],
    year: int,
    quarter: int | None = None,
    user_name: str = "",
    inn: str = "",
) -> bytes:
    """
    Экспорт КУДиР в Excel (формат по приказу ФНС ЕА-7-3/816@).

    Args:
        entries: Список записей КУДиР
        totals: Итоги (total_income, total_expense, net_result)
        year: Год
        quarter: Квартал (опционально)
        user_name: ФИО/наименование ИП
        inn: ИНН

    Returns:
        Байты Excel-файла
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "КУДиР"

    # ── Заголовок ──
    period_str = f"за {year} год" + (f", {quarter} квартал" if quarter else "")
    ws.merge_cells("A1:F1")
    title_cell = ws["A1"]
    title_cell.value = "КНИГА УЧЁТА ДОХОДОВ И РАСХОДОВ"
    title_cell.font = _TITLE_FONT
    title_cell.alignment = _CENTER_ALIGN

    ws.merge_cells("A2:F2")
    ws["A2"].value = f"организаций и индивидуальных предпринимателей, применяющих УСН"
    ws["A2"].font = Font(name="Arial", size=9, italic=True)
    ws["A2"].alignment = _CENTER_ALIGN

    ws.merge_cells("A3:F3")
    ws["A3"].value = period_str
    ws["A3"].font = _SUBTITLE_FONT
    ws["A3"].alignment = _CENTER_ALIGN

    if user_name or inn:
        ws.merge_cells("A4:F4")
        info = []
        if user_name:
            info.append(f"ИП {user_name}")
        if inn:
            info.append(f"ИНН {inn}")
        ws["A4"].value = ", ".join(info)
        ws["A4"].font = Font(name="Arial", size=9)
        ws["A4"].alignment = _CENTER_ALIGN

    # ── Раздел I. Доходы и расходы ──
    ws.merge_cells("A6:F6")
    ws["A6"].value = "I. ДОХОДЫ И РАСХОДЫ"
    ws["A6"].font = _SUBTITLE_FONT

    # Заголовки таблицы
    headers = [
        ("№\nп/п", 6),
        ("Дата и номер\nпервичного документа", 25),
        ("Содержание\nоперации", 40),
        ("Доходы, учитываемые\nпри исчислении\nналоговой базы\n(руб.)", 18),
        ("Расходы, учитываемые\nпри исчислении\nналоговой базы\n(руб.)", 18),
    ]

    row = 7
    for col_idx, (header, width) in enumerate(headers, 1):
        cell = ws.cell(row=row, column=col_idx, value=header)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.border = _THIN_BORDER
        cell.alignment = _CENTER_ALIGN
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    # Подзаголовки номеров граф
    row = 8
    for col_idx, num in enumerate(["1", "2", "3", "4", "5"], 1):
        cell = ws.cell(row=row, column=col_idx, value=num)
        cell.font = Font(name="Arial", size=8, italic=True)
        cell.fill = _HEADER_FILL
        cell.border = _THIN_BORDER
        cell.alignment = _CENTER_ALIGN

    # ── Данные ──
    row = 9
    current_quarter = None
    quarter_income = Decimal("0")
    quarter_expense = Decimal("0")

    for entry in entries:
        # Итог предыдущего квартала
        if current_quarter is not None and entry.quarter != current_quarter:
            row = _write_kudir_quarter_total(
                ws, row, current_quarter, quarter_income, quarter_expense
            )
            quarter_income = Decimal("0")
            quarter_expense = Decimal("0")

        current_quarter = entry.quarter

        ws.cell(row=row, column=1, value=entry.entry_number).font = _DATA_FONT
        ws.cell(row=row, column=1).border = _THIN_BORDER
        ws.cell(row=row, column=1).alignment = _CENTER_ALIGN

        doc_ref = entry.document_ref or ""
        ws.cell(row=row, column=2, value=doc_ref).font = _DATA_FONT
        ws.cell(row=row, column=2).border = _THIN_BORDER
        ws.cell(row=row, column=2).alignment = _LEFT_ALIGN

        ws.cell(row=row, column=3, value=entry.description or "").font = _DATA_FONT
        ws.cell(row=row, column=3).border = _THIN_BORDER
        ws.cell(row=row, column=3).alignment = _LEFT_ALIGN

        income_cell = ws.cell(row=row, column=4)
        income_cell.value = float(entry.income_amount) if entry.income_amount else 0
        income_cell.font = _DATA_FONT
        income_cell.border = _THIN_BORDER
        income_cell.number_format = _MONEY_FORMAT
        income_cell.alignment = _RIGHT_ALIGN

        expense_cell = ws.cell(row=row, column=5)
        expense_cell.value = float(entry.expense_amount) if entry.expense_amount else 0
        expense_cell.font = _DATA_FONT
        expense_cell.border = _THIN_BORDER
        expense_cell.number_format = _MONEY_FORMAT
        expense_cell.alignment = _RIGHT_ALIGN

        quarter_income += entry.income_amount or Decimal("0")
        quarter_expense += entry.expense_amount or Decimal("0")
        row += 1

    # Итог последнего квартала
    if current_quarter is not None:
        row = _write_kudir_quarter_total(
            ws, row, current_quarter, quarter_income, quarter_expense
        )

    # ── Итого за год ──
    row += 1
    ws.merge_cells(f"A{row}:C{row}")
    total_cell = ws.cell(row=row, column=1, value=f"Итого {period_str}")
    total_cell.font = Font(name="Arial", bold=True, size=10)
    total_cell.border = _THIN_BORDER

    income_total_cell = ws.cell(row=row, column=4)
    income_total_cell.value = float(totals.get("total_income", 0))
    income_total_cell.font = Font(name="Arial", bold=True, size=10)
    income_total_cell.border = _THIN_BORDER
    income_total_cell.number_format = _MONEY_FORMAT
    income_total_cell.alignment = _RIGHT_ALIGN

    expense_total_cell = ws.cell(row=row, column=5)
    expense_total_cell.value = float(totals.get("total_expense", 0))
    expense_total_cell.font = Font(name="Arial", bold=True, size=10)
    expense_total_cell.border = _THIN_BORDER
    expense_total_cell.number_format = _MONEY_FORMAT
    expense_total_cell.alignment = _RIGHT_ALIGN

    # Сохраняем
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()


def _write_kudir_quarter_total(ws, row: int, quarter: int, income: Decimal, expense: Decimal) -> int:
    """Записать итог квартала в КУДиР."""
    ws.merge_cells(f"A{row}:C{row}")
    cell = ws.cell(row=row, column=1, value=f"Итого за {quarter} квартал")
    cell.font = Font(name="Arial", bold=True, size=9)
    cell.border = _THIN_BORDER

    income_cell = ws.cell(row=row, column=4)
    income_cell.value = float(income)
    income_cell.font = Font(name="Arial", bold=True, size=9)
    income_cell.border = _THIN_BORDER
    income_cell.number_format = _MONEY_FORMAT
    income_cell.alignment = _RIGHT_ALIGN

    expense_cell = ws.cell(row=row, column=5)
    expense_cell.value = float(expense)
    expense_cell.font = Font(name="Arial", bold=True, size=9)
    expense_cell.border = _THIN_BORDER
    expense_cell.number_format = _MONEY_FORMAT
    expense_cell.alignment = _RIGHT_ALIGN

    return row + 1


def export_kudir_pdf(
    entries: list[KudirEntry],
    totals: dict[str, Any],
    year: int,
    quarter: int | None = None,
    user_name: str = "",
    inn: str = "",
) -> bytes:
    """
    Экспорт КУДиР в PDF.

    Returns:
        Байты PDF-файла
    """
    buffer = io.BytesIO()
    font_name = _setup_reportlab_fonts()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleRus", parent=styles["Title"],
        fontName=font_name, fontSize=14, alignment=1,
    )
    subtitle_style = ParagraphStyle(
        "SubtitleRus", parent=styles["Normal"],
        fontName=font_name, fontSize=10, alignment=1, spaceAfter=6,
    )
    normal_style = ParagraphStyle(
        "NormalRus", parent=styles["Normal"],
        fontName=font_name, fontSize=8,
    )

    elements = []

    # Заголовок
    period_str = f"за {year} год" + (f", {quarter} квартал" if quarter else "")
    elements.append(Paragraph("КНИГА УЧЁТА ДОХОДОВ И РАСХОДОВ", title_style))
    elements.append(Paragraph(period_str, subtitle_style))

    if user_name or inn:
        info_parts = []
        if user_name:
            info_parts.append(f"ИП {user_name}")
        if inn:
            info_parts.append(f"ИНН {inn}")
        elements.append(Paragraph(", ".join(info_parts), subtitle_style))

    elements.append(Spacer(1, 10 * mm))

    # Таблица
    table_data = [
        ["№", "Дата и номер документа", "Содержание операции", "Доход (руб.)", "Расход (руб.)"],
    ]

    for entry in entries:
        table_data.append([
            str(entry.entry_number),
            entry.document_ref or "",
            entry.description or "",
            _format_money(entry.income_amount),
            _format_money(entry.expense_amount),
        ])

    # Итого
    table_data.append([
        "",
        "",
        f"ИТОГО {period_str}",
        _format_money(totals.get("total_income", Decimal("0"))),
        _format_money(totals.get("total_expense", Decimal("0"))),
    ])

    col_widths = [25 * mm, 60 * mm, 90 * mm, 45 * mm, 45 * mm]

    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        # Заголовок
        ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.85, 0.89, 0.95)),
        ("FONTNAME", (0, 0), (-1, 0), font_name),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTNAME", (0, 0), (-1, 0), font_name),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        # Данные
        ("FONTNAME", (0, 1), (-1, -1), font_name),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ALIGN", (0, 1), (0, -1), "CENTER"),
        ("ALIGN", (3, 1), (4, -1), "RIGHT"),
        # Итого — жирный
        ("FONTNAME", (0, -1), (-1, -1), font_name),
        ("BACKGROUND", (0, -1), (-1, -1), colors.Color(0.92, 0.92, 0.92)),
        # Сетка
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.Color(0.97, 0.97, 0.97)]),
    ]))

    elements.append(table)

    # Результат
    net_result = totals.get("net_result", Decimal("0"))
    elements.append(Spacer(1, 5 * mm))
    elements.append(Paragraph(
        f"Чистый результат (доходы - расходы): {_format_money(net_result)} руб.",
        subtitle_style,
    ))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


# ═══════════════════════════════════════════════════════════════
# ЭКСПОРТ КНИГИ ПОКУПОК
# ═══════════════════════════════════════════════════════════════


def export_purchase_book_excel(
    entries: list[PurchaseBookEntry],
    totals: dict[str, Any],
    year: int,
    quarter: int,
    user_name: str = "",
    inn: str = "",
) -> bytes:
    """Экспорт книги покупок в Excel."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Книга покупок"

    # Заголовок
    ws.merge_cells("A1:I1")
    ws["A1"].value = "КНИГА ПОКУПОК"
    ws["A1"].font = _TITLE_FONT
    ws["A1"].alignment = _CENTER_ALIGN

    ws.merge_cells("A2:I2")
    ws["A2"].value = f"за {quarter} квартал {year} года"
    ws["A2"].font = _SUBTITLE_FONT
    ws["A2"].alignment = _CENTER_ALIGN

    if user_name or inn:
        ws.merge_cells("A3:I3")
        info = []
        if user_name:
            info.append(f"ИП {user_name}")
        if inn:
            info.append(f"ИНН {inn}")
        ws["A3"].value = ", ".join(info)
        ws["A3"].font = Font(name="Arial", size=9)
        ws["A3"].alignment = _CENTER_ALIGN

    # Заголовки
    headers = [
        ("№\nп/п", 6),
        ("Дата\nсчёт-фактуры", 14),
        ("Номер\nсчёт-фактуры", 14),
        ("Наименование\nпродавца", 30),
        ("ИНН\nпродавца", 14),
        ("КПП\nпродавца", 12),
        ("Стоимость покупок\nбез НДС (руб.)", 18),
        ("Сумма НДС\n(руб.)", 16),
        ("Стоимость покупок\nс НДС (руб.)", 18),
    ]

    row = 5
    for col_idx, (header, width) in enumerate(headers, 1):
        cell = ws.cell(row=row, column=col_idx, value=header)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.border = _THIN_BORDER
        cell.alignment = _CENTER_ALIGN
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    # Данные
    row = 6
    for entry in entries:
        ws.cell(row=row, column=1, value=entry.entry_number).font = _DATA_FONT
        ws.cell(row=row, column=1).border = _THIN_BORDER
        ws.cell(row=row, column=1).alignment = _CENTER_ALIGN

        date_cell = ws.cell(row=row, column=2)
        date_cell.value = entry.invoice_date
        date_cell.font = _DATA_FONT
        date_cell.border = _THIN_BORDER
        date_cell.number_format = _DATE_FORMAT
        date_cell.alignment = _CENTER_ALIGN

        ws.cell(row=row, column=3, value=entry.invoice_number or "").font = _DATA_FONT
        ws.cell(row=row, column=3).border = _THIN_BORDER

        ws.cell(row=row, column=4, value=entry.counterparty_name or "").font = _DATA_FONT
        ws.cell(row=row, column=4).border = _THIN_BORDER

        ws.cell(row=row, column=5, value=entry.counterparty_inn or "").font = _DATA_FONT
        ws.cell(row=row, column=5).border = _THIN_BORDER

        ws.cell(row=row, column=6, value=entry.counterparty_kpp or "").font = _DATA_FONT
        ws.cell(row=row, column=6).border = _THIN_BORDER

        for col, val in [
            (7, entry.total_without_vat),
            (8, entry.vat_amount),
            (9, entry.total_with_vat),
        ]:
            c = ws.cell(row=row, column=col, value=float(val or 0))
            c.font = _DATA_FONT
            c.border = _THIN_BORDER
            c.number_format = _MONEY_FORMAT
            c.alignment = _RIGHT_ALIGN

        row += 1

    # Итого
    ws.merge_cells(f"A{row}:F{row}")
    ws.cell(row=row, column=1, value="ИТОГО").font = Font(name="Arial", bold=True, size=10)
    ws.cell(row=row, column=1).border = _THIN_BORDER

    for col, key in [
        (7, "total_without_vat"),
        (8, "total_vat"),
        (9, "total_with_vat"),
    ]:
        c = ws.cell(row=row, column=col, value=float(totals.get(key, 0)))
        c.font = Font(name="Arial", bold=True, size=10)
        c.border = _THIN_BORDER
        c.number_format = _MONEY_FORMAT
        c.alignment = _RIGHT_ALIGN

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()


# ═══════════════════════════════════════════════════════════════
# ЭКСПОРТ КНИГИ ПРОДАЖ
# ═══════════════════════════════════════════════════════════════


def export_sales_book_excel(
    entries: list[SalesBookEntry],
    totals: dict[str, Any],
    year: int,
    quarter: int,
    user_name: str = "",
    inn: str = "",
) -> bytes:
    """Экспорт книги продаж в Excel."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Книга продаж"

    # Заголовок
    ws.merge_cells("A1:I1")
    ws["A1"].value = "КНИГА ПРОДАЖ"
    ws["A1"].font = _TITLE_FONT
    ws["A1"].alignment = _CENTER_ALIGN

    ws.merge_cells("A2:I2")
    ws["A2"].value = f"за {quarter} квартал {year} года"
    ws["A2"].font = _SUBTITLE_FONT
    ws["A2"].alignment = _CENTER_ALIGN

    if user_name or inn:
        ws.merge_cells("A3:I3")
        info = []
        if user_name:
            info.append(f"ИП {user_name}")
        if inn:
            info.append(f"ИНН {inn}")
        ws["A3"].value = ", ".join(info)
        ws["A3"].font = Font(name="Arial", size=9)
        ws["A3"].alignment = _CENTER_ALIGN

    # Заголовки
    headers = [
        ("№\nп/п", 6),
        ("Дата\nсчёт-фактуры", 14),
        ("Номер\nсчёт-фактуры", 14),
        ("Наименование\nпокупателя", 30),
        ("ИНН\nпокупателя", 14),
        ("КПП\nпокупателя", 12),
        ("Стоимость продаж\nбез НДС (руб.)", 18),
        ("Сумма НДС\n(руб.)", 16),
        ("Стоимость продаж\nс НДС (руб.)", 18),
    ]

    row = 5
    for col_idx, (header, width) in enumerate(headers, 1):
        cell = ws.cell(row=row, column=col_idx, value=header)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.border = _THIN_BORDER
        cell.alignment = _CENTER_ALIGN
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    # Данные
    row = 6
    for entry in entries:
        ws.cell(row=row, column=1, value=entry.entry_number).font = _DATA_FONT
        ws.cell(row=row, column=1).border = _THIN_BORDER
        ws.cell(row=row, column=1).alignment = _CENTER_ALIGN

        date_cell = ws.cell(row=row, column=2)
        date_cell.value = entry.invoice_date
        date_cell.font = _DATA_FONT
        date_cell.border = _THIN_BORDER
        date_cell.number_format = _DATE_FORMAT
        date_cell.alignment = _CENTER_ALIGN

        ws.cell(row=row, column=3, value=entry.invoice_number or "").font = _DATA_FONT
        ws.cell(row=row, column=3).border = _THIN_BORDER

        ws.cell(row=row, column=4, value=entry.buyer_name or "").font = _DATA_FONT
        ws.cell(row=row, column=4).border = _THIN_BORDER

        ws.cell(row=row, column=5, value=entry.buyer_inn or "").font = _DATA_FONT
        ws.cell(row=row, column=5).border = _THIN_BORDER

        ws.cell(row=row, column=6, value=entry.buyer_kpp or "").font = _DATA_FONT
        ws.cell(row=row, column=6).border = _THIN_BORDER

        for col, val in [
            (7, entry.total_without_vat),
            (8, entry.vat_amount),
            (9, entry.total_with_vat),
        ]:
            c = ws.cell(row=row, column=col, value=float(val or 0))
            c.font = _DATA_FONT
            c.border = _THIN_BORDER
            c.number_format = _MONEY_FORMAT
            c.alignment = _RIGHT_ALIGN

        row += 1

    # Итого
    ws.merge_cells(f"A{row}:F{row}")
    ws.cell(row=row, column=1, value="ИТОГО").font = Font(name="Arial", bold=True, size=10)
    ws.cell(row=row, column=1).border = _THIN_BORDER

    for col, key in [
        (7, "total_without_vat"),
        (8, "total_vat"),
        (9, "total_with_vat"),
    ]:
        c = ws.cell(row=row, column=col, value=float(totals.get(key, 0)))
        c.font = Font(name="Arial", bold=True, size=10)
        c.border = _THIN_BORDER
        c.number_format = _MONEY_FORMAT
        c.alignment = _RIGHT_ALIGN

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()


# ═══════════════════════════════════════════════════════════════
# PDF-ПРЕДПРОСМОТР ДЕКЛАРАЦИЙ
# ═══════════════════════════════════════════════════════════════


def export_declaration_pdf_preview(
    xml_content: str,
    declaration_type: str,
    period: str,
    year: int,
    user_name: str = "",
    inn: str = "",
) -> bytes:
    """
    Генерация PDF-предпросмотра декларации из XML.

    Рендерит основные данные из XML в «человеческий» вид.
    """
    import xml.etree.ElementTree as ET

    buffer = io.BytesIO()
    font_name = _setup_reportlab_fonts()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleRus", parent=styles["Title"],
        fontName=font_name, fontSize=16, alignment=1, spaceAfter=10,
    )
    subtitle_style = ParagraphStyle(
        "SubtitleRus", parent=styles["Normal"],
        fontName=font_name, fontSize=11, alignment=1, spaceAfter=6,
    )
    heading_style = ParagraphStyle(
        "HeadingRus", parent=styles["Heading2"],
        fontName=font_name, fontSize=12, spaceBefore=10, spaceAfter=6,
    )
    normal_style = ParagraphStyle(
        "NormalRus", parent=styles["Normal"],
        fontName=font_name, fontSize=10, spaceAfter=4,
    )

    elements = []

    # Определяем название декларации
    type_names = {
        "vat": "НАЛОГОВАЯ ДЕКЛАРАЦИЯ ПО НДС",
        "usn": "НАЛОГОВАЯ ДЕКЛАРАЦИЯ ПО УСН",
        "ndfl_6": "РАСЧЁТ 6-НДФЛ",
        "rsv": "РАСЧЁТ ПО СТРАХОВЫМ ВЗНОСАМ (РСВ)",
    }
    knd_map = {
        "vat": "1151001",
        "usn": "1152017",
        "ndfl_6": "1151100",
        "rsv": "1151111",
    }

    title = type_names.get(declaration_type, "НАЛОГОВАЯ ДЕКЛАРАЦИЯ")
    knd = knd_map.get(declaration_type, "")

    elements.append(Paragraph(title, title_style))
    elements.append(Paragraph(f"Период: {period} | Год: {year}", subtitle_style))
    if knd:
        elements.append(Paragraph(f"Форма по КНД {knd}", subtitle_style))

    if user_name or inn:
        info_parts = []
        if user_name:
            info_parts.append(f"Налогоплательщик: ИП {user_name}")
        if inn:
            info_parts.append(f"ИНН: {inn}")
        elements.append(Paragraph(" | ".join(info_parts), subtitle_style))

    elements.append(Spacer(1, 10 * mm))

    # Парсим XML и извлекаем данные
    try:
        root = ET.fromstring(xml_content)
        doc_el = root.find("Документ")
        if doc_el is not None:
            elements.append(Paragraph("Данные декларации:", heading_style))

            # Собираем все атрибуты и подэлементы
            table_data = [["Показатель", "Значение"]]

            for child in doc_el:
                tag = child.tag
                # Атрибуты элемента
                if child.attrib:
                    elements.append(Paragraph(f"<b>{tag}</b>", normal_style))
                    for attr_name, attr_value in child.attrib.items():
                        table_data.append([
                            _translate_xml_attr(attr_name),
                            attr_value,
                        ])
                # Подэлементы
                for subchild in child:
                    if subchild.attrib:
                        for attr_name, attr_value in subchild.attrib.items():
                            table_data.append([
                                f"  {_translate_xml_attr(attr_name)}",
                                attr_value,
                            ])

            if len(table_data) > 1:
                table = Table(table_data, colWidths=[100 * mm, 60 * mm])
                table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.85, 0.89, 0.95)),
                    ("FONTNAME", (0, 0), (-1, -1), font_name),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                ]))
                elements.append(table)
    except ET.ParseError:
        elements.append(Paragraph(
            "Не удалось распарсить XML для предпросмотра",
            normal_style,
        ))

    elements.append(Spacer(1, 10 * mm))
    elements.append(Paragraph(
        f"Документ сформирован: {datetime.now().strftime('%d.%m.%Y %H:%M')} | AI-Buhgalter v1.0",
        ParagraphStyle("Footer", parent=styles["Normal"], fontName=font_name, fontSize=8, textColor=colors.grey),
    ))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


def _translate_xml_attr(name: str) -> str:
    """Перевод атрибута XML в человекочитаемую форму."""
    translations = {
        "ДоходВсего": "Доходы всего",
        "РасходВсего": "Расходы всего",
        "НалБаза": "Налоговая база",
        "Ставка": "Ставка (%)",
        "НалИсчисл": "Налог исчисленный",
        "МинНалог": "Минимальный налог",
        "СтрахВзносВычет": "Вычет страховых взносов",
        "НДСНачисл": "НДС начисленный",
        "НДСВычет": "НДС к вычету",
        "НДСУплате": "НДС к уплате",
        "Доход": "Доход",
        "Расход": "Расход",
        "Сумма": "Сумма",
        "ИННФЛ": "ИНН",
        "ИНН": "ИНН",
        "ФИО": "ФИО",
        "НаимОрг": "Наименование",
        "НачислДоход": "Начисленный доход",
        "ИсчислНДФЛ": "Исчисленный НДФЛ",
        "БазаВзносов": "База для взносов",
        "ИсчислВзнос": "Исчисленные взносы",
    }
    return translations.get(name, name)