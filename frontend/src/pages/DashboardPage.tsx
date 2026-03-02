/**
 * Страница дашборда — обзор финансов, месячный график, последние операции.
 * Пункт плана: 1.18.2
 */
import {
  Typography,
  Card,
  Row,
  Col,
  Statistic,
  Spin,
  Alert,
  Table,
  Tag,
  Empty,
  Badge,
  Space,
  Button,
} from 'antd';
import {
  ArrowUpOutlined,
  ArrowDownOutlined,
  WarningOutlined,
  CalendarOutlined,
  FileTextOutlined,
  SwapOutlined,
  RightOutlined,
} from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { dashboardApi, operationsApi, calendarApi } from '@/api/endpoints';
import { formatMoney, formatDate } from '@/utils/format';
import type { BankOperation, CalendarEvent, DashboardResponse } from '@/types';

const { Title, Text } = Typography;

interface MonthlyAmount {
  month: string;
  income: number;
  expense: number;
}

/**
 * Извлекает массив из ответа API.
 * Поддержка: массив, { items: [...] }, { data: [...] }, { events: [...] }
 */
function extractArray<T>(data: unknown): T[] {
  if (Array.isArray(data)) return data;
  if (data && typeof data === 'object') {
    const obj = data as Record<string, unknown>;
    if (Array.isArray(obj.items)) return obj.items;
    if (Array.isArray(obj.data)) return obj.data;
    if (Array.isArray(obj.events)) return obj.events;
    if (Array.isArray(obj.results)) return obj.results;
  }
  return [];
}

/* ---------- Monthly Bar Chart (pure CSS, no chart lib) ---------- */
function MonthlyChart({ data }: { data: MonthlyAmount[] | null | undefined }) {
  if (!data || data.length === 0) {
    return <Empty description="Нет данных за период" />;
  }

  const maxVal = Math.max(...data.map((m) => Math.max(m.income, m.expense)), 1);

  return (
    <div style={{ overflowX: 'auto' }}>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8, minHeight: 200, padding: '0 4px' }}>
        {data.map((m) => {
          const incomeH = Math.max((m.income / maxVal) * 160, 2);
          const expenseH = Math.max((m.expense / maxVal) * 160, 2);
          const label = m.month.length >= 7 ? m.month.slice(5) : m.month;
          return (
            <div
              key={m.month}
              style={{
                flex: 1,
                minWidth: 40,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 4,
              }}
            >
              <div style={{ display: 'flex', gap: 2, alignItems: 'flex-end' }}>
                <div
                  style={{
                    width: 14,
                    height: incomeH,
                    background: '#52c41a',
                    borderRadius: '3px 3px 0 0',
                  }}
                  title={`Доходы: ${formatMoney(m.income)}`}
                />
                <div
                  style={{
                    width: 14,
                    height: expenseH,
                    background: '#ff4d4f',
                    borderRadius: '3px 3px 0 0',
                  }}
                  title={`Расходы: ${formatMoney(m.expense)}`}
                />
              </div>
              <Text style={{ fontSize: 11 }}>{label}</Text>
            </div>
          );
        })}
      </div>
      <div style={{ display: 'flex', justifyContent: 'center', gap: 16, marginTop: 12 }}>
        <Space size={4}>
          <div style={{ width: 12, height: 12, background: '#52c41a', borderRadius: 2 }} />
          <Text type="secondary" style={{ fontSize: 12 }}>Доходы</Text>
        </Space>
        <Space size={4}>
          <div style={{ width: 12, height: 12, background: '#ff4d4f', borderRadius: 2 }} />
          <Text type="secondary" style={{ fontSize: 12 }}>Расходы</Text>
        </Space>
      </div>
    </div>
  );
}

/* ---------- Recent Operations Table ---------- */
function RecentOperations() {
  const navigate = useNavigate();

  const { data: opsData, isLoading } = useQuery({
    queryKey: ['operations-recent'],
    queryFn: () => operationsApi.list({ page: 1, per_page: 5 }),
    select: (res) => extractArray<BankOperation>(res.data),
  });

  const columns = [
    {
      title: 'Дата',
      dataIndex: 'operation_date',
      key: 'date',
      width: 100,
      render: (v: string) => formatDate(v),
    },
    {
      title: 'Контрагент',
      dataIndex: 'counterparty_name',
      key: 'counterparty',
      ellipsis: true,
      render: (v: string | null) => v || '—',
    },
    {
      title: 'Сумма',
      dataIndex: 'amount',
      key: 'amount',
      width: 130,
      render: (v: number, r: BankOperation) => (
        <Text style={{ color: r.is_income ? '#3f8600' : '#cf1322', fontWeight: 500 }}>
          {r.is_income ? '+' : '-'}{formatMoney(v)}
        </Text>
      ),
    },
    {
      title: 'Статус',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (s: string) => {
        const colors: Record<string, string> = {
          confirmed: 'green',
          classified: 'blue',
          new: 'orange',
          rejected: 'red',
        };
        return <Tag color={colors[s] || 'default'}>{s}</Tag>;
      },
    },
  ];

  return (
    <Card
      title={
        <Space>
          <SwapOutlined />
          <span>Последние операции</span>
        </Space>
      }
      extra={
        <Button type="link" size="small" onClick={() => navigate('/operations')}>
          Все <RightOutlined />
        </Button>
      }
    >
      <Table
        dataSource={opsData || []}
        columns={columns}
        loading={isLoading}
        rowKey="id"
        pagination={false}
        size="small"
        locale={{ emptyText: <Empty description="Нет операций" /> }}
      />
    </Card>
  );
}

/* ---------- Upcoming Events ---------- */
function UpcomingEvents() {
  const navigate = useNavigate();

  const { data: events, isLoading } = useQuery({
    queryKey: ['calendar-upcoming-dash'],
    queryFn: () => calendarApi.getUpcoming(14),
    select: (res) => extractArray<CalendarEvent>(res.data),
  });

  return (
    <Card
      title={
        <Space>
          <CalendarOutlined />
          <span>Ближайшие дедлайны</span>
        </Space>
      }
      extra={
        <Button type="link" size="small" onClick={() => navigate('/calendar')}>
          Календарь <RightOutlined />
        </Button>
      }
    >
      {isLoading ? (
        <Spin />
      ) : !events || events.length === 0 ? (
        <Empty description="Нет ближайших событий" />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {events.slice(0, 5).map((ev) => {
            const isOverdue = ev.status === 'overdue';
            return (
              <div
                key={ev.id}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '6px 8px',
                  borderRadius: 6,
                  background: isOverdue ? '#fff2f0' : '#f6ffed',
                }}
              >
                <div style={{ flex: 1 }}>
                  <Text style={{ fontSize: 13 }}>{ev.title}</Text>
                </div>
                <Badge
                  status={isOverdue ? 'error' : 'processing'}
                  text={
                    <Text style={{ fontSize: 12 }} type={isOverdue ? 'danger' : 'secondary'}>
                      {formatDate(ev.deadline)}
                    </Text>
                  }
                />
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}

/* ==================== Main Dashboard ==================== */
export default function DashboardPage() {
  const navigate = useNavigate();

  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => dashboardApi.get({ include_monthly: true }),
    select: (res) => res.data as DashboardResponse | undefined,
  });

  if (isLoading) {
    return (
      <div style={{ textAlign: 'center', padding: 80 }}>
        <Spin size="large" />
      </div>
    );
  }

  if (error) {
    return (
      <Alert
        type="error"
        message="Ошибка загрузки дашборда"
        description="Попробуйте обновить страницу"
        showIcon
      />
    );
  }

  return (
    <div>
      <Title level={3}>Дашборд</Title>

      {/* KPI Cards */}
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <Card hoverable onClick={() => navigate('/operations')}>
            <Statistic
              title="Доходы"
              value={data?.total_income || 0}
              formatter={(val) => formatMoney(val as number)}
              prefix={<ArrowUpOutlined />}
              valueStyle={{ color: '#3f8600' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card hoverable onClick={() => navigate('/operations')}>
            <Statistic
              title="Расходы"
              value={data?.total_expense || 0}
              formatter={(val) => formatMoney(val as number)}
              prefix={<ArrowDownOutlined />}
              valueStyle={{ color: '#cf1322' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card hoverable onClick={() => navigate('/operations')}>
            <Statistic
              title="Неподтверждённые"
              value={data?.unconfirmed_operations || 0}
              prefix={<WarningOutlined />}
              valueStyle={{
                color: (data?.unconfirmed_operations || 0) > 0 ? '#faad14' : undefined,
              }}
              suffix={
                (data?.unprocessed_documents || 0) > 0 ? (
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    + {data?.unprocessed_documents} док.
                  </Text>
                ) : undefined
              }
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card hoverable onClick={() => navigate('/calendar')}>
            <Statistic
              title="Ближайшие события"
              value={data?.upcoming_events || 0}
              prefix={<CalendarOutlined />}
              suffix={
                (data?.overdue_events || 0) > 0 ? (
                  <Text type="danger" style={{ fontSize: 12 }}>
                    {data?.overdue_events} просроч.
                  </Text>
                ) : undefined
              }
            />
          </Card>
        </Col>
      </Row>

      {/* Profit & Tax + Monthly Chart */}
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={8}>
          <Card title="Чистая прибыль" style={{ height: '100%' }}>
            <Statistic
              value={data?.net_profit || 0}
              formatter={(val) => formatMoney(val as number)}
              valueStyle={{
                color: (data?.net_profit || 0) >= 0 ? '#3f8600' : '#cf1322',
                fontSize: 28,
              }}
            />
            <div style={{ marginTop: 16 }}>
              <Row gutter={16}>
                <Col span={12}>
                  <Statistic
                    title="УСН"
                    value={data?.estimated_usn || 0}
                    formatter={(val) => formatMoney(val as number)}
                    valueStyle={{ fontSize: 16 }}
                  />
                </Col>
                <Col span={12}>
                  <Statistic
                    title="НДС"
                    value={data?.estimated_vat || 0}
                    formatter={(val) => formatMoney(val as number)}
                    valueStyle={{ fontSize: 16 }}
                  />
                </Col>
              </Row>
            </div>
          </Card>
        </Col>
        <Col xs={24} lg={16}>
          <Card
            title="Доходы и расходы по месяцам"
            style={{ height: '100%' }}
          >
            <MonthlyChart data={data?.monthly_breakdown as MonthlyAmount[] | null | undefined} />
          </Card>
        </Col>
      </Row>

      {/* Recent Operations & Upcoming Events */}
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={14}>
          <RecentOperations />
        </Col>
        <Col xs={24} lg={10}>
          <UpcomingEvents />
        </Col>
      </Row>

      {/* Quick actions */}
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24}>
          <Card title="Быстрые действия">
            <Space wrap>
              <Button
                type="primary"
                icon={<FileTextOutlined />}
                onClick={() => navigate('/upload')}
              >
                Загрузить документ
              </Button>
              <Button
                icon={<SwapOutlined />}
                onClick={() => navigate('/operations')}
              >
                Подтвердить операции
              </Button>
              <Button
                icon={<CalendarOutlined />}
                onClick={() => navigate('/calendar')}
              >
                Налоговый календарь
              </Button>
              <Button
                icon={<WarningOutlined />}
                onClick={() => navigate('/assistant')}
              >
                Спросить ИИ-ассистента
              </Button>
            </Space>
          </Card>
        </Col>
      </Row>
    </div>
  );
}