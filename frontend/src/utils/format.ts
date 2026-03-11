/**
 * Утилиты форматирования для отображения данных.
 */
import dayjs from 'dayjs';
import 'dayjs/locale/ru';

dayjs.locale('ru');

/**
 * Форматировать сумму в рублях: 1 234 567.89 ₽
 */
export function formatMoney(amount: number | null | undefined): string {
  if (amount == null) return '—';
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

/**
 * Форматировать число с разделителями: 1 234 567
 */
export function formatNumber(num: number | null | undefined): string {
  if (num == null) return '—';
  return new Intl.NumberFormat('ru-RU').format(num);
}

/**
 * Форматировать дату: 01.03.2026
 */
export function formatDate(date: string | null | undefined): string {
  if (!date) return '—';
  return dayjs(date).format('DD.MM.YYYY');
}

/**
 * Форматировать дату и время: 01.03.2026 15:30
 */
export function formatDateTime(date: string | null | undefined): string {
  if (!date) return '—';
  return dayjs(date).format('DD.MM.YYYY HH:mm');
}

/**
 * Сокращённое название системы налогообложения.
 */
export function taxSystemLabel(sys: string | null | undefined): string {
  const map: Record<string, string> = {
    usn_income: 'УСН Доходы',
    usn_income_expense: 'УСН Доходы−Расходы',
    osno: 'ОСНО',
    patent: 'Патент',
    eshn: 'ЕСХН',
    auto: 'Самозанятый (НПД)',
  };
  return map[sys || ''] || sys || '—';
}

/**
 * Статус документа — человекочитаемый.
 */
export function documentStatusLabel(status: string): string {
  const map: Record<string, string> = {
    uploading: 'Загружается',
    uploaded: 'Загружен',
    processing: 'Обработка',
    recognized: 'Распознан',
    confirmed: 'Подтверждён',
    rejected: 'Отклонён',
    error: 'Ошибка',
  };
  return map[status] || status;
}

/**
 * Статус операции — человекочитаемый.
 */
export function operationStatusLabel(status: string): string {
  const map: Record<string, string> = {
    new: 'Новая',
    classified: 'Классифицирована',
    confirmed: 'Подтверждена',
    rejected: 'Отклонена',
  };
  return map[status] || status;
}

/**
 * Статус события календаря — человекочитаемый.
 */
export function calendarStatusLabel(status: string): string {
  const map: Record<string, string> = {
    upcoming: 'Предстоит',
    overdue: 'Просрочено',
    completed: 'Выполнено',
  };
  return map[status] || status;
}

/**
 * Цвет для статуса события календаря (Ant Design Tag color).
 */
export function calendarStatusColor(status: string): string {
  const map: Record<string, string> = {
    upcoming: 'blue',
    overdue: 'red',
    completed: 'green',
  };
  return map[status] || 'default';
}

/**
 * Процент → строка: 6% или 15%
 */
export function formatPercent(value: number | null | undefined): string {
  if (value == null) return '—';
  return `${value}%`;
}