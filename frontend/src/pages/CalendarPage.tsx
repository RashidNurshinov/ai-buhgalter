/**
 * Страница налогового календаря — список событий, ближайшие, просроченные.
 */
import { useState } from 'react';
import {
  Typography,
  Card,
  Table,
  Tag,
  Button,
  Space,
  message,
  Alert,
  Select,
  Tabs,
  Badge,
  Tooltip,
  Row,
  Col,
  Statistic,
} from 'antd';
import {
  CheckCircleOutlined,
  ReloadOutlined,
  CalendarOutlined,
  WarningOutlined,
  ClockCircleOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { calendarApi } from '@/api/endpoints';
import { formatDate } from '@/utils/format';
import dayjs from 'dayjs';
import type { CalendarEvent } from '@/types';
import type { ColumnsType } from 'antd/es/table';

const { Title } = Typography;

const currentYear = dayjs().year();
const yearOptions = Array.from({ length: 5 }, (_, i) => ({
  value: currentYear - i,
  label: String(currentYear - i),
}));

function statusTag(status: string) {
  const map: Record<string, { color: string; label: string }> = {
    pending: { color: 'blue', label: 'Ожидается' },
    upcoming: { color: 'orange', label: 'Скоро' },
    overdue: { color: 'red', label: 'Просрочено' },
    completed: { color: 'green', label: 'Выполнено' },
  };
  const s = map[status] || { color: 'default', label: status };
  return <Tag color={s.color}>{s.label}</Tag>;
}

function eventTypeTag(eventType: string) {
  const map: Record<string, { color: string; label: string }> = {
    tax_payment: { color: 'red', label: 'Уплата налога' },
    declaration: { color: 'blue', label: 'Декларация' },
    report: { color: 'purple', label: 'Отчёт' },
    insurance: { color: 'orange', label: 'Страховые взносы' },
    other: { color: 'default', label: 'Другое' },
  };
  const s = map[eventType] || { color: 'default', label: eventType };
  return <Tag color={s.color}>{s.label}</Tag>;
}

function daysUntil(dateStr: string): number {
  return dayjs(dateStr).diff(dayjs(), 'day');
}

function daysLabel(dateStr: string): React.ReactNode {
  const d = daysUntil(dateStr);
  if (d < 0)
    return (
      <span style={{ color: '#cf1322', fontWeight: 600 }}>
        Просрочено на {Math.abs(d)} дн.
      </span>
    );
  if (d === 0)
    return <span style={{ color: '#faad14', fontWeight: 600 }}>Сегодня!</span>;
  if (d <= 7)
    return (
      <span style={{ color: '#faad14' }}>
        Через {d} дн.
      </span>
    );
  return <span style={{ color: '#999' }}>Через {d} дн.</span>;
}

/**
 * Извлекает массив из ответа API.
 * Поддержка: массив напрямую, { events: [...] }, { data: [...] }, { items: [...] }
 */
function extractArray<T>(data: unknown): T[] {
  if (Array.isArray(data)) return data;
  if (data && typeof data === 'object') {
    const obj = data as Record<string, unknown>;
    if (Array.isArray(obj.events)) return obj.events;
    if (Array.isArray(obj.data)) return obj.data;
    if (Array.isArray(obj.items)) return obj.items;
    if (Array.isArray(obj.results)) return obj.results;
  }
  return [];
}

export default function CalendarPage() {
  const queryClient = useQueryClient();
  const [year, setYear] = useState(currentYear);
  const [filterStatus, setFilterStatus] = useState<string | undefined>();

  // All events for the year
  // Backend returns TaxCalendarListResponse { events: [...], upcoming_count, overdue_count }
  const {
    data: events,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['calendar', year, filterStatus],
    queryFn: () => calendarApi.getEvents({ year, status: filterStatus }),
    select: (res) => extractArray<CalendarEvent>(res.data),
  });

  // Upcoming — returns CalendarEvent[] directly
  const { data: upcoming } = useQuery({
    queryKey: ['calendar-upcoming'],
    queryFn: () => calendarApi.getUpcoming(30),
    select: (res) => extractArray<CalendarEvent>(res.data),
  });

  // Overdue — returns CalendarEvent[] directly
  const { data: overdue } = useQuery({
    queryKey: ['calendar-overdue'],
    queryFn: () => calendarApi.getOverdue(),
    select: (res) => extractArray<CalendarEvent>(res.data),
  });

  const completeMutation = useMutation({
    mutationFn: (id: string) => calendarApi.complete(id),
    onSuccess: () => {
      message.success('Событие отмечено как выполненное');
      queryClient.invalidateQueries({ queryKey: ['calendar'] });
      queryClient.invalidateQueries({ queryKey: ['calendar-upcoming'] });
      queryClient.invalidateQueries({ queryKey: ['calendar-overdue'] });
    },
    onError: () => message.error('Ошибка обновления'),
  });

  const populateMutation = useMutation({
    mutationFn: (y: number) => calendarApi.populate(y),
    onSuccess: () => {
      message.success('Календарь заполнен');
      queryClient.invalidateQueries({ queryKey: ['calendar'] });
    },
    onError: () => message.error('Ошибка заполнения'),
  });

  const allEvents: CalendarEvent[] = events || [];
  const upcomingList: CalendarEvent[] = upcoming || [];
  const overdueList: CalendarEvent[] = overdue || [];

  const columns: ColumnsType<CalendarEvent> = [
    {
      title: 'Дата',
      dataIndex: 'deadline',
      key: 'deadline',
      width: 110,
      sorter: (a: CalendarEvent, b: CalendarEvent) =>
        dayjs(a.deadline).unix() - dayjs(b.deadline).unix(),
      render: (d: string) => formatDate(d),
    },
    {
      title: 'Осталось',
      key: 'remaining',
      width: 160,
      render: (_: unknown, r: CalendarEvent) =>
        r.status === 'completed' ? (
          <Tag color="green">✓ Выполнено</Tag>
        ) : (
          daysLabel(r.deadline)
        ),
    },
    {
      title: 'Тип',
      dataIndex: 'event_type',
      key: 'type',
      width: 160,
      render: (t: string) => eventTypeTag(t),
    },
    {
      title: 'Описание',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
    },
    {
      title: 'Статус',
      dataIndex: 'status',
      key: 'status',
      width: 130,
      render: (s: string) => statusTag(s),
    },
    {
      title: '',
      key: 'actions',
      width: 60,
      render: (_: unknown, record: CalendarEvent) =>
        record.status !== 'completed' ? (
          <Tooltip title="Отметить выполненным">
            <Button
              type="text"
              icon={<CheckCircleOutlined style={{ color: '#52c41a' }} />}
              size="small"
              onClick={() => completeMutation.mutate(record.id)}
            />
          </Tooltip>
        ) : null,
    },
  ];

  const tabItems = [
    {
      key: 'all',
      label: (
        <span>
          <CalendarOutlined /> Все события
        </span>
      ),
      children: (
        <div>
          <Space wrap style={{ marginBottom: 16 }}>
            <Select
              value={year}
              onChange={setYear}
              style={{ width: 100 }}
              options={yearOptions}
            />
            <Select
              placeholder="Статус"
              allowClear
              style={{ width: 150 }}
              value={filterStatus}
              onChange={setFilterStatus}
              options={[
                { value: 'pending', label: 'Ожидается' },
                { value: 'upcoming', label: 'Скоро' },
                { value: 'overdue', label: 'Просрочено' },
                { value: 'completed', label: 'Выполнено' },
              ]}
            />
            <Button
              icon={<ReloadOutlined />}
              onClick={() =>
                queryClient.invalidateQueries({ queryKey: ['calendar'] })
              }
            >
              Обновить
            </Button>
            <Button
              icon={<PlusOutlined />}
              onClick={() => populateMutation.mutate(year)}
              loading={populateMutation.isPending}
            >
              Заполнить календарь
            </Button>
          </Space>

          {error && (
            <Alert
              type="error"
              message="Ошибка загрузки календаря"
              style={{ marginBottom: 16 }}
            />
          )}

          <Table<CalendarEvent>
            rowKey="id"
            columns={columns}
            dataSource={allEvents}
            loading={isLoading}
            size="middle"
            locale={{ emptyText: 'Нет событий' }}
            pagination={{ pageSize: 30, showTotal: (t) => `Всего: ${t}` }}
          />
        </div>
      ),
    },
    {
      key: 'upcoming',
      label: (
        <Badge count={upcomingList.length} offset={[10, 0]} size="small">
          <span>
            <ClockCircleOutlined /> Ближайшие (30 дн.)
          </span>
        </Badge>
      ),
      children: (
        <Table<CalendarEvent>
          rowKey="id"
          columns={columns}
          dataSource={upcomingList}
          size="middle"
          locale={{ emptyText: 'Нет ближайших событий' }}
          pagination={false}
        />
      ),
    },
    {
      key: 'overdue',
      label: (
        <Badge count={overdueList.length} offset={[10, 0]} size="small">
          <span>
            <WarningOutlined /> Просроченные
          </span>
        </Badge>
      ),
      children: (
        <div>
          {overdueList.length === 0 ? (
            <Alert
              type="success"
              message="Нет просроченных событий"
              showIcon
            />
          ) : (
            <Table<CalendarEvent>
              rowKey="id"
              columns={columns}
              dataSource={overdueList}
              size="middle"
              pagination={false}
            />
          )}
        </div>
      ),
    },
  ];

  return (
    <div>
      <Title level={3}>📅 Налоговый календарь</Title>

      {/* Quick stats */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="Всего событий"
              value={allEvents.length}
              prefix={<CalendarOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="Ближайшие (30 дн.)"
              value={upcomingList.length}
              prefix={<ClockCircleOutlined />}
              valueStyle={{
                color: upcomingList.length > 0 ? '#faad14' : undefined,
              }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="Просроченные"
              value={overdueList.length}
              prefix={<WarningOutlined />}
              valueStyle={{
                color: overdueList.length > 0 ? '#cf1322' : '#3f8600',
              }}
            />
          </Card>
        </Col>
      </Row>

      <Card>
        <Tabs items={tabItems} />
      </Card>
    </div>
  );
}