/**
 * Страница книг покупок и продаж — НДС-учёт.
 */
import { useState } from 'react';
import {
  Typography,
  Card,
  Table,
  Tabs,
  Button,
  Select,
  Space,
  message,
  Alert,
  Row,
  Col,
  Statistic,
} from 'antd';
import {
  ReloadOutlined,
  BookOutlined,
  ShoppingCartOutlined,
  ShopOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { booksApi } from '@/api/endpoints';
import { formatDate, formatMoney } from '@/utils/format';
import dayjs from 'dayjs';
import type { ColumnsType } from 'antd/es/table';

const { Title, Text } = Typography;

interface BookEntry {
  id: string;
  entry_number?: number;
  entry_date: string;
  document_number?: string;
  document_date?: string;
  counterparty_name?: string;
  counterparty_inn?: string;
  total_without_vat: number;
  vat_amount: number;
  total_with_vat: number;
  vat_rate?: number;
  created_at: string;
}

interface BookData {
  entries?: BookEntry[];
  items?: BookEntry[];
  totals?: {
    total_without_vat: number;
    vat_amount: number;
    total_with_vat: number;
  };
}

const currentYear = dayjs().year();
const currentQuarter = Math.ceil((dayjs().month() + 1) / 3);

const yearOptions = Array.from({ length: 5 }, (_, i) => ({
  value: currentYear - i,
  label: String(currentYear - i),
}));

const quarterOptions = [
  { value: 1, label: 'I квартал' },
  { value: 2, label: 'II квартал' },
  { value: 3, label: 'III квартал' },
  { value: 4, label: 'IV квартал' },
];

function PurchaseBookTab() {
  const queryClient = useQueryClient();
  const [year, setYear] = useState(currentYear);
  const [quarter, setQuarter] = useState(currentQuarter);

  const { data, isLoading, error } = useQuery({
    queryKey: ['purchase-book', year, quarter],
    queryFn: () => booksApi.getPurchaseBook({ year, quarter }),
    select: (res) => res.data as BookData,
  });

  const generateMutation = useMutation({
    mutationFn: () => booksApi.generatePurchaseBook({ year, quarter }),
    onSuccess: () => {
      message.success('Книга покупок сформирована');
      queryClient.invalidateQueries({ queryKey: ['purchase-book'] });
    },
    onError: () => message.error('Ошибка формирования'),
  });

  const entries: BookEntry[] = data?.entries || data?.items || [];
  const totals = data?.totals || {
    total_without_vat: entries.reduce((s, e) => s + (e.total_without_vat || 0), 0),
    vat_amount: entries.reduce((s, e) => s + (e.vat_amount || 0), 0),
    total_with_vat: entries.reduce((s, e) => s + (e.total_with_vat || 0), 0),
  };

  const columns: ColumnsType<BookEntry> = [
    {
      title: '№',
      dataIndex: 'entry_number',
      key: 'num',
      width: 50,
      align: 'center',
      render: (v: number | undefined, _: BookEntry, idx: number) => v || idx + 1,
    },
    {
      title: 'Дата записи',
      dataIndex: 'entry_date',
      key: 'date',
      width: 110,
      render: (d: string) => formatDate(d),
    },
    {
      title: 'Счёт-фактура',
      key: 'invoice',
      width: 160,
      render: (_: unknown, r: BookEntry) => (
        <span>
          {r.document_number || '—'}
          {r.document_date && (
            <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>
              от {formatDate(r.document_date)}
            </Text>
          )}
        </span>
      ),
    },
    {
      title: 'Продавец',
      key: 'seller',
      ellipsis: true,
      render: (_: unknown, r: BookEntry) => (
        <span>
          {r.counterparty_name || '—'}
          {r.counterparty_inn && (
            <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>
              ИНН {r.counterparty_inn}
            </Text>
          )}
        </span>
      ),
    },
    {
      title: 'Сумма без НДС',
      dataIndex: 'total_without_vat',
      key: 'without_vat',
      width: 140,
      align: 'right',
      render: (v: number) => formatMoney(v),
    },
    {
      title: 'НДС',
      dataIndex: 'vat_amount',
      key: 'vat',
      width: 120,
      align: 'right',
      render: (v: number) => formatMoney(v),
    },
    {
      title: 'Сумма с НДС',
      dataIndex: 'total_with_vat',
      key: 'with_vat',
      width: 140,
      align: 'right',
      render: (v: number) => (
        <strong>{formatMoney(v)}</strong>
      ),
    },
  ];

  return (
    <div>
      {/* Summary */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={8}>
          <Card size="small">
            <Statistic
              title="Итого без НДС"
              value={totals.total_without_vat}
              formatter={(v) => formatMoney(v as number)}
              valueStyle={{ fontSize: 18 }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card size="small">
            <Statistic
              title="НДС к вычету"
              value={totals.vat_amount}
              formatter={(v) => formatMoney(v as number)}
              valueStyle={{ fontSize: 18, color: '#3f8600' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card size="small">
            <Statistic
              title="Итого с НДС"
              value={totals.total_with_vat}
              formatter={(v) => formatMoney(v as number)}
              valueStyle={{ fontSize: 18 }}
            />
          </Card>
        </Col>
      </Row>

      {/* Filters */}
      <Space wrap style={{ marginBottom: 16 }}>
        <Select value={year} onChange={setYear} style={{ width: 100 }} options={yearOptions} />
        <Select value={quarter} onChange={setQuarter} style={{ width: 140 }} options={quarterOptions} />
        <Button
          icon={<ReloadOutlined />}
          onClick={() => queryClient.invalidateQueries({ queryKey: ['purchase-book'] })}
        >
          Обновить
        </Button>
        <Button
          type="primary"
          icon={<BookOutlined />}
          loading={generateMutation.isPending}
          onClick={() => generateMutation.mutate()}
        >
          Сформировать
        </Button>
      </Space>

      {error && <Alert type="error" message="Ошибка загрузки книги покупок" style={{ marginBottom: 16 }} />}

      <Table<BookEntry>
        rowKey="id"
        columns={columns}
        dataSource={entries}
        loading={isLoading}
        scroll={{ x: 900 }}
        size="middle"
        locale={{ emptyText: 'Нет записей в книге покупок' }}
        pagination={{ pageSize: 50, showTotal: (t) => `Записей: ${t}` }}
        summary={() =>
          entries.length > 0 ? (
            <Table.Summary fixed>
              <Table.Summary.Row>
                <Table.Summary.Cell index={0} colSpan={4} align="right">
                  <strong>ИТОГО:</strong>
                </Table.Summary.Cell>
                <Table.Summary.Cell index={4} align="right">
                  <strong>{formatMoney(totals.total_without_vat)}</strong>
                </Table.Summary.Cell>
                <Table.Summary.Cell index={5} align="right">
                  <strong style={{ color: '#3f8600' }}>{formatMoney(totals.vat_amount)}</strong>
                </Table.Summary.Cell>
                <Table.Summary.Cell index={6} align="right">
                  <strong>{formatMoney(totals.total_with_vat)}</strong>
                </Table.Summary.Cell>
              </Table.Summary.Row>
            </Table.Summary>
          ) : null
        }
      />
    </div>
  );
}

function SalesBookTab() {
  const queryClient = useQueryClient();
  const [year, setYear] = useState(currentYear);
  const [quarter, setQuarter] = useState(currentQuarter);

  const { data, isLoading, error } = useQuery({
    queryKey: ['sales-book', year, quarter],
    queryFn: () => booksApi.getSalesBook({ year, quarter }),
    select: (res) => res.data as BookData,
  });

  const generateMutation = useMutation({
    mutationFn: () => booksApi.generateSalesBook({ year, quarter }),
    onSuccess: () => {
      message.success('Книга продаж сформирована');
      queryClient.invalidateQueries({ queryKey: ['sales-book'] });
    },
    onError: () => message.error('Ошибка формирования'),
  });

  const entries: BookEntry[] = data?.entries || data?.items || [];
  const totals = data?.totals || {
    total_without_vat: entries.reduce((s, e) => s + (e.total_without_vat || 0), 0),
    vat_amount: entries.reduce((s, e) => s + (e.vat_amount || 0), 0),
    total_with_vat: entries.reduce((s, e) => s + (e.total_with_vat || 0), 0),
  };

  const columns: ColumnsType<BookEntry> = [
    {
      title: '№',
      dataIndex: 'entry_number',
      key: 'num',
      width: 50,
      align: 'center',
      render: (v: number | undefined, _: BookEntry, idx: number) => v || idx + 1,
    },
    {
      title: 'Дата записи',
      dataIndex: 'entry_date',
      key: 'date',
      width: 110,
      render: (d: string) => formatDate(d),
    },
    {
      title: 'Счёт-фактура',
      key: 'invoice',
      width: 160,
      render: (_: unknown, r: BookEntry) => (
        <span>
          {r.document_number || '—'}
          {r.document_date && (
            <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>
              от {formatDate(r.document_date)}
            </Text>
          )}
        </span>
      ),
    },
    {
      title: 'Покупатель',
      key: 'buyer',
      ellipsis: true,
      render: (_: unknown, r: BookEntry) => (
        <span>
          {r.counterparty_name || '—'}
          {r.counterparty_inn && (
            <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>
              ИНН {r.counterparty_inn}
            </Text>
          )}
        </span>
      ),
    },
    {
      title: 'Сумма без НДС',
      dataIndex: 'total_without_vat',
      key: 'without_vat',
      width: 140,
      align: 'right',
      render: (v: number) => formatMoney(v),
    },
    {
      title: 'НДС',
      dataIndex: 'vat_amount',
      key: 'vat',
      width: 120,
      align: 'right',
      render: (v: number) => formatMoney(v),
    },
    {
      title: 'Сумма с НДС',
      dataIndex: 'total_with_vat',
      key: 'with_vat',
      width: 140,
      align: 'right',
      render: (v: number) => (
        <strong>{formatMoney(v)}</strong>
      ),
    },
  ];

  return (
    <div>
      {/* Summary */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={8}>
          <Card size="small">
            <Statistic
              title="Итого без НДС"
              value={totals.total_without_vat}
              formatter={(v) => formatMoney(v as number)}
              valueStyle={{ fontSize: 18 }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card size="small">
            <Statistic
              title="НДС начисленный"
              value={totals.vat_amount}
              formatter={(v) => formatMoney(v as number)}
              valueStyle={{ fontSize: 18, color: '#cf1322' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card size="small">
            <Statistic
              title="Итого с НДС"
              value={totals.total_with_vat}
              formatter={(v) => formatMoney(v as number)}
              valueStyle={{ fontSize: 18 }}
            />
          </Card>
        </Col>
      </Row>

      {/* Filters */}
      <Space wrap style={{ marginBottom: 16 }}>
        <Select value={year} onChange={setYear} style={{ width: 100 }} options={yearOptions} />
        <Select value={quarter} onChange={setQuarter} style={{ width: 140 }} options={quarterOptions} />
        <Button
          icon={<ReloadOutlined />}
          onClick={() => queryClient.invalidateQueries({ queryKey: ['sales-book'] })}
        >
          Обновить
        </Button>
        <Button
          type="primary"
          icon={<BookOutlined />}
          loading={generateMutation.isPending}
          onClick={() => generateMutation.mutate()}
        >
          Сформировать
        </Button>
      </Space>

      {error && <Alert type="error" message="Ошибка загрузки книги продаж" style={{ marginBottom: 16 }} />}

      <Table<BookEntry>
        rowKey="id"
        columns={columns}
        dataSource={entries}
        loading={isLoading}
        scroll={{ x: 900 }}
        size="middle"
        locale={{ emptyText: 'Нет записей в книге продаж' }}
        pagination={{ pageSize: 50, showTotal: (t) => `Записей: ${t}` }}
        summary={() =>
          entries.length > 0 ? (
            <Table.Summary fixed>
              <Table.Summary.Row>
                <Table.Summary.Cell index={0} colSpan={4} align="right">
                  <strong>ИТОГО:</strong>
                </Table.Summary.Cell>
                <Table.Summary.Cell index={4} align="right">
                  <strong>{formatMoney(totals.total_without_vat)}</strong>
                </Table.Summary.Cell>
                <Table.Summary.Cell index={5} align="right">
                  <strong style={{ color: '#cf1322' }}>{formatMoney(totals.vat_amount)}</strong>
                </Table.Summary.Cell>
                <Table.Summary.Cell index={6} align="right">
                  <strong>{formatMoney(totals.total_with_vat)}</strong>
                </Table.Summary.Cell>
              </Table.Summary.Row>
            </Table.Summary>
          ) : null
        }
      />
    </div>
  );
}

export default function BooksPage() {
  return (
    <div>
      <Title level={3}>📚 Книги покупок и продаж</Title>

      <Card>
        <Tabs
          defaultActiveKey="purchase"
          items={[
            {
              key: 'purchase',
              label: (
                <span>
                  <ShoppingCartOutlined /> Книга покупок
                </span>
              ),
              children: <PurchaseBookTab />,
            },
            {
              key: 'sales',
              label: (
                <span>
                  <ShopOutlined /> Книга продаж
                </span>
              ),
              children: <SalesBookTab />,
            },
          ]}
        />
      </Card>
    </div>
  );
}