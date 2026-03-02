/**
 * Страница расчёта налогов — калькулятор, сводка, история.
 */
import { useState } from 'react';
import {
  Typography,
  Card,
  Table,
  Select,
  Space,
  Alert,
  Row,
  Col,
  Statistic,
  Tag,
  Descriptions,
  Spin,
  Tabs,
} from 'antd';
import {
  CalculatorOutlined,
  HistoryOutlined,
} from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { taxesApi } from '@/api/endpoints';
import { formatMoney } from '@/utils/format';
import dayjs from 'dayjs';

const { Title } = Typography;

const currentYear = dayjs().year();
const yearOptions = Array.from({ length: 5 }, (_, i) => ({
  value: currentYear - i,
  label: String(currentYear - i),
}));

const periodOptions = [
  { value: `${currentYear}-Q1`, label: `${currentYear} — I квартал` },
  { value: `${currentYear}-Q2`, label: `${currentYear} — II квартал` },
  { value: `${currentYear}-Q3`, label: `${currentYear} — III квартал` },
  { value: `${currentYear}-Q4`, label: `${currentYear} — IV квартал` },
  { value: `${currentYear}`, label: `${currentYear} — Весь год` },
  { value: `${currentYear - 1}`, label: `${currentYear - 1} — Весь год` },
];

interface TaxCalculation {
  period: string;
  tax_system: string;
  total_income: number;
  total_expense: number;
  tax_base: number;
  tax_rate: number;
  tax_amount: number;
  insurance_contributions: number;
  tax_to_pay: number;
  details?: Record<string, unknown>;
}

interface TaxSummary {
  year: number;
  total_tax: number;
  total_paid: number;
  total_remaining: number;
  quarters: Array<{
    quarter: number;
    tax_amount: number;
    paid: boolean;
  }>;
}

interface TaxHistoryEntry {
  id: string;
  period: string;
  tax_type: string;
  amount: number;
  status: string;
  calculated_at: string;
}

export default function TaxesPage() {
  const [period, setPeriod] = useState(periodOptions[0].value);
  const [summaryYear, setSummaryYear] = useState(currentYear);

  const {
    data: calculation,
    isLoading: calcLoading,
    error: calcError,
  } = useQuery({
    queryKey: ['taxes-calc', period],
    queryFn: () => taxesApi.calculate(period),
    select: (res) => res.data as TaxCalculation,
  });

  const {
    data: summary,
    isLoading: summaryLoading,
    error: summaryError,
  } = useQuery({
    queryKey: ['taxes-summary', summaryYear],
    queryFn: () => taxesApi.summary(summaryYear),
    select: (res) => res.data as TaxSummary,
  });

  const {
    data: history,
    isLoading: historyLoading,
  } = useQuery({
    queryKey: ['taxes-history'],
    queryFn: () => taxesApi.history(),
    select: (res) => (res.data as TaxHistoryEntry[]) || [],
  });

  const tabItems = [
    {
      key: 'calc',
      label: (
        <span>
          <CalculatorOutlined /> Расчёт
        </span>
      ),
      children: (
        <div>
          <Space wrap style={{ marginBottom: 16 }}>
            <Select
              value={period}
              onChange={setPeriod}
              style={{ width: 260 }}
              options={periodOptions}
            />
          </Space>

          {calcError && (
            <Alert
              type="error"
              message="Ошибка расчёта налогов"
              style={{ marginBottom: 16 }}
            />
          )}

          {calcLoading ? (
            <div style={{ textAlign: 'center', padding: 40 }}>
              <Spin size="large" />
            </div>
          ) : calculation ? (
            <>
              <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
                <Col xs={24} sm={8}>
                  <Card>
                    <Statistic
                      title="Налоговая база"
                      value={calculation.tax_base}
                      formatter={(v) => formatMoney(v as number)}
                    />
                  </Card>
                </Col>
                <Col xs={24} sm={8}>
                  <Card>
                    <Statistic
                      title="Начисленный налог"
                      value={calculation.tax_amount}
                      formatter={(v) => formatMoney(v as number)}
                      valueStyle={{ color: '#cf1322' }}
                    />
                  </Card>
                </Col>
                <Col xs={24} sm={8}>
                  <Card>
                    <Statistic
                      title="К оплате"
                      value={calculation.tax_to_pay}
                      formatter={(v) => formatMoney(v as number)}
                      valueStyle={{
                        color: calculation.tax_to_pay > 0 ? '#cf1322' : '#3f8600',
                        fontSize: 28,
                      }}
                    />
                  </Card>
                </Col>
              </Row>

              <Card title="Детали расчёта">
                <Descriptions bordered column={1} size="small">
                  <Descriptions.Item label="Система налогообложения">
                    <Tag color="blue">{calculation.tax_system}</Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="Период">
                    {calculation.period}
                  </Descriptions.Item>
                  <Descriptions.Item label="Доходы">
                    <span style={{ color: '#3f8600' }}>
                      {formatMoney(calculation.total_income)}
                    </span>
                  </Descriptions.Item>
                  <Descriptions.Item label="Расходы">
                    <span style={{ color: '#cf1322' }}>
                      {formatMoney(calculation.total_expense)}
                    </span>
                  </Descriptions.Item>
                  <Descriptions.Item label="Налоговая база">
                    {formatMoney(calculation.tax_base)}
                  </Descriptions.Item>
                  <Descriptions.Item label="Ставка">
                    {(calculation.tax_rate * 100).toFixed(0)}%
                  </Descriptions.Item>
                  <Descriptions.Item label="Начисленный налог">
                    {formatMoney(calculation.tax_amount)}
                  </Descriptions.Item>
                  <Descriptions.Item label="Страховые взносы (вычет)">
                    <span style={{ color: '#3f8600' }}>
                      - {formatMoney(calculation.insurance_contributions)}
                    </span>
                  </Descriptions.Item>
                  <Descriptions.Item label="Итого к оплате">
                    <strong style={{ fontSize: 16 }}>
                      {formatMoney(calculation.tax_to_pay)}
                    </strong>
                  </Descriptions.Item>
                </Descriptions>
              </Card>
            </>
          ) : null}
        </div>
      ),
    },
    {
      key: 'summary',
      label: 'Годовая сводка',
      children: (
        <div>
          <Space style={{ marginBottom: 16 }}>
            <Select
              value={summaryYear}
              onChange={setSummaryYear}
              style={{ width: 100 }}
              options={yearOptions}
            />
          </Space>

          {summaryError && (
            <Alert type="error" message="Ошибка загрузки сводки" style={{ marginBottom: 16 }} />
          )}

          {summaryLoading ? (
            <div style={{ textAlign: 'center', padding: 40 }}>
              <Spin />
            </div>
          ) : summary ? (
            <>
              <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
                <Col xs={24} sm={8}>
                  <Card>
                    <Statistic
                      title="Начислено за год"
                      value={summary.total_tax}
                      formatter={(v) => formatMoney(v as number)}
                    />
                  </Card>
                </Col>
                <Col xs={24} sm={8}>
                  <Card>
                    <Statistic
                      title="Оплачено"
                      value={summary.total_paid}
                      formatter={(v) => formatMoney(v as number)}
                      valueStyle={{ color: '#3f8600' }}
                    />
                  </Card>
                </Col>
                <Col xs={24} sm={8}>
                  <Card>
                    <Statistic
                      title="Осталось"
                      value={summary.total_remaining}
                      formatter={(v) => formatMoney(v as number)}
                      valueStyle={{
                        color: summary.total_remaining > 0 ? '#cf1322' : '#3f8600',
                      }}
                    />
                  </Card>
                </Col>
              </Row>

              {summary.quarters && (
                <Card title="По кварталам">
                  <Table
                    rowKey="quarter"
                    dataSource={summary.quarters}
                    pagination={false}
                    size="middle"
                    columns={[
                      {
                        title: 'Квартал',
                        dataIndex: 'quarter',
                        render: (q: number) =>
                          ['I', 'II', 'III', 'IV'][q - 1] || q,
                      },
                      {
                        title: 'Сумма',
                        dataIndex: 'tax_amount',
                        align: 'right' as const,
                        render: (v: number) => formatMoney(v),
                      },
                      {
                        title: 'Статус',
                        dataIndex: 'paid',
                        render: (paid: boolean) =>
                          paid ? (
                            <Tag color="green">Оплачено</Tag>
                          ) : (
                            <Tag color="orange">Не оплачено</Tag>
                          ),
                      },
                    ]}
                  />
                </Card>
              )}
            </>
          ) : null}
        </div>
      ),
    },
    {
      key: 'history',
      label: (
        <span>
          <HistoryOutlined /> История
        </span>
      ),
      children: (
        <Table
          rowKey="id"
          dataSource={(history as TaxHistoryEntry[]) || []}
          loading={historyLoading}
          size="middle"
          locale={{ emptyText: 'Нет истории расчётов' }}
          pagination={{ pageSize: 20 }}
          columns={[
            {
              title: 'Период',
              dataIndex: 'period',
              width: 150,
            },
            {
              title: 'Тип',
              dataIndex: 'tax_type',
              width: 120,
            },
            {
              title: 'Сумма',
              dataIndex: 'amount',
              width: 150,
              align: 'right' as const,
              render: (v: number) => formatMoney(v),
            },
            {
              title: 'Статус',
              dataIndex: 'status',
              width: 120,
              render: (s: string) => {
                const colors: Record<string, string> = {
                  calculated: 'blue',
                  paid: 'green',
                  overdue: 'red',
                };
                return <Tag color={colors[s] || 'default'}>{s}</Tag>;
              },
            },
            {
              title: 'Рассчитано',
              dataIndex: 'calculated_at',
              width: 160,
              render: (d: string) =>
                d ? dayjs(d).format('DD.MM.YYYY HH:mm') : '—',
            },
          ]}
        />
      ),
    },
  ];

  return (
    <div>
      <Title level={3}>Расчёт налогов</Title>
      <Card>
        <Tabs items={tabItems} />
      </Card>
    </div>
  );
}