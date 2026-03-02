/**
 * Страница КУДиР — просмотр записей и генерация книги.
 */
import { useState } from 'react';
import {
  Typography,
  Card,
  Table,
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
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { kudirApi } from '@/api/endpoints';
import { formatDate, formatMoney } from '@/utils/format';
import dayjs from 'dayjs';
import type { ColumnsType } from 'antd/es/table';

const { Title } = Typography;

interface KudirEntry {
  id: string;
  entry_number: number;
  operation_date: string;
  document_info: string;
  description: string;
  income_amount: number | null;
  expense_amount: number | null;
  created_at: string;
}

const currentYear = dayjs().year();
const yearOptions = Array.from({ length: 5 }, (_, i) => ({
  value: currentYear - i,
  label: String(currentYear - i),
}));

const quarterOptions = [
  { value: undefined, label: 'Весь год' },
  { value: 1, label: 'I квартал' },
  { value: 2, label: 'II квартал' },
  { value: 3, label: 'III квартал' },
  { value: 4, label: 'IV квартал' },
];

export default function KudirPage() {
  const queryClient = useQueryClient();
  const [year, setYear] = useState(currentYear);
  const [quarter, setQuarter] = useState<number | undefined>();

  const { data, isLoading, error } = useQuery({
    queryKey: ['kudir', year, quarter],
    queryFn: () => kudirApi.getEntries({ year, quarter }),
    select: (res) => res.data,
  });

  const generateMutation = useMutation({
    mutationFn: (params: { year: number; quarter: number }) =>
      kudirApi.generate(params),
    onSuccess: () => {
      message.success('КУДиР сформирована');
      queryClient.invalidateQueries({ queryKey: ['kudir'] });
    },
    onError: () => message.error('Ошибка формирования КУДиР'),
  });

  const entries: KudirEntry[] = Array.isArray(data)
    ? data
    : data?.entries || [];

  const totalIncome = entries.reduce(
    (sum, e) => sum + (e.income_amount || 0),
    0,
  );
  const totalExpense = entries.reduce(
    (sum, e) => sum + (e.expense_amount || 0),
    0,
  );

  const columns: ColumnsType<KudirEntry> = [
    {
      title: '№',
      dataIndex: 'entry_number',
      key: 'num',
      width: 60,
      align: 'center',
    },
    {
      title: 'Дата',
      dataIndex: 'operation_date',
      key: 'date',
      width: 110,
      render: (d: string) => formatDate(d),
    },
    {
      title: 'Документ',
      dataIndex: 'document_info',
      key: 'document',
      width: 200,
      ellipsis: true,
    },
    {
      title: 'Содержание операции',
      dataIndex: 'description',
      key: 'desc',
      ellipsis: true,
    },
    {
      title: 'Доход',
      dataIndex: 'income_amount',
      key: 'income',
      width: 150,
      align: 'right',
      render: (v: number | null) =>
        v ? (
          <span style={{ color: '#3f8600' }}>{formatMoney(v)}</span>
        ) : (
          '—'
        ),
    },
    {
      title: 'Расход',
      dataIndex: 'expense_amount',
      key: 'expense',
      width: 150,
      align: 'right',
      render: (v: number | null) =>
        v ? (
          <span style={{ color: '#cf1322' }}>{formatMoney(v)}</span>
        ) : (
          '—'
        ),
    },
  ];

  return (
    <div>
      <Title level={3}>Книга учета доходов и расходов</Title>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="Итого доходы"
              value={totalIncome}
              formatter={(val) => formatMoney(val as number)}
              valueStyle={{ color: '#3f8600' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="Итого расходы"
              value={totalExpense}
              formatter={(val) => formatMoney(val as number)}
              valueStyle={{ color: '#cf1322' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title="Налоговая база"
              value={totalIncome - totalExpense}
              formatter={(val) => formatMoney(val as number)}
              valueStyle={{
                color:
                  totalIncome - totalExpense >= 0 ? '#3f8600' : '#cf1322',
              }}
            />
          </Card>
        </Col>
      </Row>

      <Card>
        <Space wrap style={{ marginBottom: 16 }}>
          <Select
            value={year}
            onChange={setYear}
            style={{ width: 100 }}
            options={yearOptions}
          />
          <Select
            value={quarter}
            onChange={setQuarter}
            style={{ width: 150 }}
            options={quarterOptions}
            placeholder="Квартал"
            allowClear
          />
          <Button
            icon={<ReloadOutlined />}
            onClick={() =>
              queryClient.invalidateQueries({ queryKey: ['kudir'] })
            }
          >
            Обновить
          </Button>
          <Button
            type="primary"
            icon={<BookOutlined />}
            loading={generateMutation.isPending}
            onClick={() => {
              if (!quarter) {
                message.info('Выберите квартал для генерации');
                return;
              }
              generateMutation.mutate({ year, quarter });
            }}
          >
            Сформировать КУДиР
          </Button>
        </Space>

        {error && (
          <Alert
            type="error"
            message="Ошибка загрузки КУДиР"
            style={{ marginBottom: 16 }}
          />
        )}

        <Table<KudirEntry>
          rowKey="id"
          columns={columns}
          dataSource={entries}
          loading={isLoading}
          scroll={{ x: 900 }}
          size="middle"
          locale={{ emptyText: 'Нет записей в КУДиР' }}
          pagination={{
            pageSize: 50,
            showSizeChanger: true,
            pageSizeOptions: ['25', '50', '100'],
            showTotal: (t) => `Записей: ${t}`,
          }}
          summary={() =>
            entries.length > 0 ? (
              <Table.Summary fixed>
                <Table.Summary.Row>
                  <Table.Summary.Cell index={0} colSpan={4} align="right">
                    <strong>ИТОГО:</strong>
                  </Table.Summary.Cell>
                  <Table.Summary.Cell index={4} align="right">
                    <strong style={{ color: '#3f8600' }}>
                      {formatMoney(totalIncome)}
                    </strong>
                  </Table.Summary.Cell>
                  <Table.Summary.Cell index={5} align="right">
                    <strong style={{ color: '#cf1322' }}>
                      {formatMoney(totalExpense)}
                    </strong>
                  </Table.Summary.Cell>
                </Table.Summary.Row>
              </Table.Summary>
            ) : null
          }
        />
      </Card>
    </div>
  );
}