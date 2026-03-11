/**
 * Страница операций — таблица, карточка операции, вкладка «Ожидают подтверждения», пакетные действия.
 * Пункт плана: 1.18.5
 */
import { useState } from 'react';
import {
  Typography,
  Card,
  Table,
  Tag,
  Button,
  Select,
  Space,
  message,
  Alert,
  Tooltip,
  Modal,
  Input,
  Tabs,
  Drawer,
  Descriptions,
  Divider,
  Statistic,
  Row,
  Col,
  Badge,
  Empty,
} from 'antd';
import {
  CheckCircleOutlined,
  EditOutlined,
  ReloadOutlined,
  ArrowUpOutlined,
  ArrowDownOutlined,
  EyeOutlined,
  CloseOutlined,
  ExclamationCircleOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { operationsApi } from '@/api/endpoints';
import { formatDate, formatMoney, operationStatusLabel } from '@/utils/format';
import type { BankOperation, OperationStatus } from '@/types';
import type { ColumnsType } from 'antd/es/table';

const { Title, Text } = Typography;

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

/** Извлекает total из пагинированного ответа */
function extractTotal(data: unknown): number {
  if (Array.isArray(data)) return data.length;
  if (data && typeof data === 'object') {
    const obj = data as Record<string, unknown>;
    if (typeof obj.total === 'number') return obj.total;
  }
  return 0;
}

function statusTag(status: OperationStatus) {
  const colorMap: Record<string, string> = {
    new: 'blue',
    classified: 'orange',
    confirmed: 'green',
    rejected: 'red',
  };
  return (
    <Tag color={colorMap[status] || 'default'}>
      {operationStatusLabel(status)}
    </Tag>
  );
}

/* ==================== Operation Detail Drawer ==================== */
function OperationDrawer(props: {
  op: BankOperation | null;
  open: boolean;
  onClose: () => void;
  onConfirm: (id: string) => void;
  onReclassify: (id: string, category: string) => void;
  confirmLoading: boolean;
}) {
  const { op, open, onClose, onConfirm, confirmLoading } = props;
  if (!op) return null;

  const canEdit = op.status === ('new' as OperationStatus) || op.status === 'pending' || op.status === 'classified';

  return (
    <Drawer
      title={
        <Space>
          {op.is_income ? (
            <ArrowUpOutlined style={{ color: '#3f8600' }} />
          ) : (
            <ArrowDownOutlined style={{ color: '#cf1322' }} />
          )}
          <span>Операция от {formatDate(op.operation_date)}</span>
        </Space>
      }
      open={open}
      onClose={onClose}
      width={520}
      extra={
        <Space>
          {canEdit && (
            <Button
              type="primary"
              icon={<CheckCircleOutlined />}
              onClick={() => onConfirm(op.id)}
              loading={confirmLoading}
            >
              Подтвердить
            </Button>
          )}
          <Button icon={<CloseOutlined />} onClick={onClose} />
        </Space>
      }
    >
      {/* Amount */}
      <div style={{ textAlign: 'center', marginBottom: 24 }}>
        <Statistic
          value={op.amount}
          formatter={(val) => formatMoney(val as number)}
          prefix={op.is_income ? '+' : '-'}
          valueStyle={{
            color: op.is_income ? '#3f8600' : '#cf1322',
            fontSize: 32,
          }}
        />
        <div style={{ marginTop: 8 }}>
          {statusTag(op.status)}
          {op.classification_confidence != null && (
            <Tag
              color={
                op.classification_confidence >= 0.8
                  ? 'green'
                  : op.classification_confidence >= 0.5
                    ? 'orange'
                    : 'red'
              }
              style={{ marginLeft: 4 }}
            >
              AI: {(op.classification_confidence * 100).toFixed(0)}%
            </Tag>
          )}
        </div>
      </div>

      <Descriptions column={1} size="small" bordered>
        <Descriptions.Item label="Дата">{formatDate(op.operation_date)}</Descriptions.Item>
        <Descriptions.Item label="Направление">
          <Tag color={op.is_income ? 'green' : 'red'}>
            {op.is_income ? 'Доход' : 'Расход'}
          </Tag>
        </Descriptions.Item>
        <Descriptions.Item label="Контрагент">
          <div>
            <Text strong>{op.counterparty_name || '—'}</Text>
            {op.counterparty_inn && (
              <div>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  ИНН: {op.counterparty_inn}
                </Text>
              </div>
            )}
          </div>
        </Descriptions.Item>
        <Descriptions.Item label="Назначение платежа">
          <Text style={{ fontSize: 13 }}>{op.purpose || '—'}</Text>
        </Descriptions.Item>
        <Descriptions.Item label="Категория">
          <Text strong>{op.category || '—'}</Text>
        </Descriptions.Item>
        <Descriptions.Item label="НДС">
          {formatMoney(op.vat_amount)}
        </Descriptions.Item>
      </Descriptions>

      <Divider>Служебная информация</Divider>

      <Descriptions column={1} size="small">
        <Descriptions.Item label="ID">{op.id}</Descriptions.Item>
        <Descriptions.Item label="Создано">{formatDate(op.created_at)}</Descriptions.Item>
      </Descriptions>
    </Drawer>
  );
}

/* ==================== Operations Table (reusable) ==================== */
function OperationsTable(props: {
  items: BankOperation[];
  loading: boolean;
  total: number;
  page: number;
  perPage: number;
  onPageChange: (p: number) => void;
  onOpenDrawer: (op: BankOperation) => void;
  onConfirm: (id: string) => void;
  onOpenReclassify: (op: BankOperation) => void;
  confirmLoading: boolean;
  selectedRowKeys?: string[];
  onSelectChange?: (keys: string[]) => void;
  showSelection?: boolean;
}) {
  const {
    items, loading, total, page, perPage,
    onPageChange, onOpenDrawer, onConfirm, onOpenReclassify,
    selectedRowKeys, onSelectChange, showSelection,
  } = props;

  const columns: ColumnsType<BankOperation> = [
    {
      title: 'Дата',
      dataIndex: 'operation_date',
      key: 'date',
      width: 110,
      sorter: (a, b) => (a.operation_date || '').localeCompare(b.operation_date || ''),
      render: (d: string) => formatDate(d),
    },
    {
      title: '',
      key: 'direction',
      width: 40,
      render: (_: unknown, r: BankOperation) =>
        r.is_income ? (
          <ArrowUpOutlined style={{ color: '#3f8600' }} />
        ) : (
          <ArrowDownOutlined style={{ color: '#cf1322' }} />
        ),
    },
    {
      title: 'Сумма',
      dataIndex: 'amount',
      key: 'amount',
      width: 150,
      align: 'right',
      sorter: (a, b) => a.amount - b.amount,
      render: (v: number, r: BankOperation) => (
        <Text style={{ color: r.is_income ? '#3f8600' : '#cf1322', fontWeight: 600 }}>
          {r.is_income ? '+' : '-'} {formatMoney(v)}
        </Text>
      ),
    },
    {
      title: 'Контрагент',
      dataIndex: 'counterparty_name',
      key: 'counterparty',
      ellipsis: true,
      render: (name: string | null, r: BankOperation) => (
        <span>
          {name || '—'}
          {r.counterparty_inn && (
            <span style={{ color: '#999', marginLeft: 4, fontSize: 12 }}>
              ИНН {r.counterparty_inn}
            </span>
          )}
        </span>
      ),
    },
    {
      title: 'Назначение',
      dataIndex: 'purpose',
      key: 'purpose',
      ellipsis: true,
      render: (v: string | null) => v || '—',
    },
    {
      title: 'Категория',
      dataIndex: 'category',
      key: 'category',
      width: 160,
      render: (cat: string | null, r: BankOperation) => (
        <Space size="small">
          <span>{cat || '—'}</span>
          {r.classification_confidence != null && (
            <Tag
              color={
                r.classification_confidence >= 0.8
                  ? 'green'
                  : r.classification_confidence >= 0.5
                    ? 'orange'
                    : 'red'
              }
              style={{ fontSize: 10 }}
            >
              {(r.classification_confidence * 100).toFixed(0)}%
            </Tag>
          )}
        </Space>
      ),
    },
    {
      title: 'НДС',
      dataIndex: 'vat_amount',
      key: 'vat',
      width: 110,
      align: 'right',
      render: (v: number | null) => formatMoney(v),
    },
    {
      title: 'Статус',
      dataIndex: 'status',
      key: 'status',
      width: 130,
      render: (s: OperationStatus) => statusTag(s),
    },
    {
      title: '',
      key: 'actions',
      width: 120,
      render: (_: unknown, record: BankOperation) => (
        <Space size="small">
          <Tooltip title="Просмотр">
            <Button
              type="text"
              icon={<EyeOutlined />}
              size="small"
              onClick={(e) => {
                e.stopPropagation();
                onOpenDrawer(record);
              }}
            />
          </Tooltip>
          {(record.status === ('new' as OperationStatus) || record.status === 'pending' || record.status === 'classified') && (
            <>
              <Tooltip title="Подтвердить">
                <Button
                  type="text"
                  icon={<CheckCircleOutlined style={{ color: '#52c41a' }} />}
                  size="small"
                  onClick={(e) => {
                    e.stopPropagation();
                    onConfirm(record.id);
                  }}
                />
              </Tooltip>
              <Tooltip title="Изменить категорию">
                <Button
                  type="text"
                  icon={<EditOutlined />}
                  size="small"
                  onClick={(e) => {
                    e.stopPropagation();
                    onOpenReclassify(record);
                  }}
                />
              </Tooltip>
            </>
          )}
          {record.status === 'confirmed' && (
            <Tag color="green" style={{ margin: 0 }}>OK</Tag>
          )}
        </Space>
      ),
    },
  ];

  return (
    <Table<BankOperation>
      rowKey="id"
      columns={columns}
      dataSource={items}
      loading={loading}
      scroll={{ x: 1200 }}
      size="middle"
      locale={{ emptyText: <Empty description="Нет операций" /> }}
      onRow={(record) => ({
        onClick: () => onOpenDrawer(record),
        style: { cursor: 'pointer' },
      })}
      rowSelection={
        showSelection
          ? {
              selectedRowKeys,
              onChange: (keys) => onSelectChange?.(keys as string[]),
            }
          : undefined
      }
      pagination={{
        current: page,
        pageSize: perPage,
        total,
        showTotal: (t) => `Всего: ${t}`,
        showSizeChanger: false,
        onChange: (p) => onPageChange(p),
      }}
    />
  );
}

/* ==================== Main Page ==================== */
export default function OperationsPage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<string>('all');

  const [page, setPage] = useState(1);
  const [perPage] = useState(20);
  const [filterStatus, setFilterStatus] = useState<string | undefined>();
  const [filterDirection, setFilterDirection] = useState<'income' | 'expense' | undefined>();
  const [searchText, setSearchText] = useState('');

  const [selectedOp, setSelectedOp] = useState<BankOperation | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const [reclassifyModal, setReclassifyModal] = useState<{
    visible: boolean;
    operationId: string;
    currentCategory: string;
  }>({ visible: false, operationId: '', currentCategory: '' });
  const [newCategory, setNewCategory] = useState('');

  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([]);

  // Backend operations PaginatedResponse uses { items: [...], total, page, per_page, pages }
  const { data: rawData, isLoading, error } = useQuery({
    queryKey: ['operations', page, perPage, filterStatus, filterDirection],
    queryFn: () =>
      operationsApi.list({
        page,
        per_page: perPage,
        status: filterStatus,
        is_income:
          filterDirection === 'income' ? true : filterDirection === 'expense' ? false : undefined,
      }),
    select: (res) => res.data,
  });

  const { data: unconfirmedData, isLoading: unconfirmedLoading } = useQuery({
    queryKey: ['operations-unconfirmed'],
    queryFn: () => operationsApi.unconfirmed(),
    select: (res) => extractArray<BankOperation>(res.data),
  });

  const confirmMutation = useMutation({
    mutationFn: (id: string) => operationsApi.confirm(id),
    onSuccess: () => {
      message.success('Операция подтверждена');
      queryClient.invalidateQueries({ queryKey: ['operations'] });
      queryClient.invalidateQueries({ queryKey: ['operations-unconfirmed'] });
      setDrawerOpen(false);
    },
    onError: () => message.error('Ошибка подтверждения'),
  });

  const reclassifyMutation = useMutation({
    mutationFn: ({ id, category }: { id: string; category: string }) =>
      operationsApi.reclassify(id, category),
    onSuccess: () => {
      message.success('Категория изменена');
      setReclassifyModal({ visible: false, operationId: '', currentCategory: '' });
      queryClient.invalidateQueries({ queryKey: ['operations'] });
      queryClient.invalidateQueries({ queryKey: ['operations-unconfirmed'] });
    },
    onError: () => message.error('Ошибка переклассификации'),
  });

  // Extract items array from paginated response (handles both { items: [...] } and { data: [...] })
  let allItems: BankOperation[] = extractArray<BankOperation>(rawData);
  const allTotal: number = extractTotal(rawData);

  if (searchText.trim()) {
    const q = searchText.toLowerCase();
    allItems = allItems.filter(
      (op) =>
        (op.counterparty_name || '').toLowerCase().includes(q) ||
        (op.purpose || '').toLowerCase().includes(q) ||
        (op.counterparty_inn || '').includes(q),
    );
  }

  const unconfirmedItems = unconfirmedData || [];
  const unconfirmedCount = unconfirmedItems.length;

  const totalIncome = allItems.filter((o) => o.is_income).reduce((s, o) => s + o.amount, 0);
  const totalExpense = allItems.filter((o) => !o.is_income).reduce((s, o) => s + o.amount, 0);

  const openDrawer = (op: BankOperation) => {
    setSelectedOp(op);
    setDrawerOpen(true);
  };

  const openReclassify = (op: BankOperation) => {
    setNewCategory(op.category || '');
    setReclassifyModal({
      visible: true,
      operationId: op.id,
      currentCategory: op.category || '',
    });
  };

  const handleBatchConfirm = () => {
    if (selectedRowKeys.length === 0) return;
    Modal.confirm({
      title: `Подтвердить ${selectedRowKeys.length} операций?`,
      icon: <ExclamationCircleOutlined />,
      content: 'Все выбранные операции будут подтверждены.',
      okText: 'Подтвердить',
      cancelText: 'Отмена',
      onOk: async () => {
        try {
          await Promise.all(selectedRowKeys.map((id) => operationsApi.confirm(id)));
          message.success(`Подтверждено ${selectedRowKeys.length} операций`);
          setSelectedRowKeys([]);
          queryClient.invalidateQueries({ queryKey: ['operations'] });
          queryClient.invalidateQueries({ queryKey: ['operations-unconfirmed'] });
        } catch {
          message.error('Ошибка пакетного подтверждения');
        }
      },
    });
  };

  return (
    <div>
      <Title level={3}>Операции</Title>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic title="Всего" value={allTotal} />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title="Доходы (стр.)"
              value={totalIncome}
              formatter={(val) => formatMoney(val as number)}
              valueStyle={{ color: '#3f8600', fontSize: 16 }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title="Расходы (стр.)"
              value={totalExpense}
              formatter={(val) => formatMoney(val as number)}
              valueStyle={{ color: '#cf1322', fontSize: 16 }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title="Ожидают подтв."
              value={unconfirmedCount}
              valueStyle={{ color: unconfirmedCount > 0 ? '#faad14' : undefined }}
            />
          </Card>
        </Col>
      </Row>

      <Card>
        <Tabs
          activeKey={activeTab}
          onChange={(key) => {
            setActiveTab(key);
            setSelectedRowKeys([]);
          }}
          items={[
            {
              key: 'all',
              label: 'Все операции',
              children: (
                <>
                  <Space wrap style={{ marginBottom: 16 }}>
                    <Input
                      placeholder="Поиск по контрагенту / назначению"
                      prefix={<SearchOutlined />}
                      allowClear
                      style={{ width: 280 }}
                      value={searchText}
                      onChange={(e) => setSearchText(e.target.value)}
                    />
                    <Select
                      placeholder="Направление"
                      allowClear
                      style={{ width: 140 }}
                      value={filterDirection}
                      onChange={(v) => {
                        setFilterDirection(v);
                        setPage(1);
                      }}
                      options={[
                        { value: 'income', label: 'Доходы' },
                        { value: 'expense', label: 'Расходы' },
                      ]}
                    />
                    <Select
                      placeholder="Статус"
                      allowClear
                      style={{ width: 180 }}
                      value={filterStatus}
                      onChange={(v) => {
                        setFilterStatus(v);
                        setPage(1);
                      }}
                      options={[
                        { value: 'new', label: 'Новая' },
                        { value: 'classified', label: 'Классифицирована' },
                        { value: 'confirmed', label: 'Подтверждена' },
                        { value: 'rejected', label: 'Отклонена' },
                      ]}
                    />
                    <Button
                      icon={<ReloadOutlined />}
                      onClick={() =>
                        queryClient.invalidateQueries({ queryKey: ['operations'] })
                      }
                    >
                      Обновить
                    </Button>
                  </Space>

                  {error && (
                    <Alert type="error" message="Ошибка загрузки операций" style={{ marginBottom: 16 }} />
                  )}

                  <OperationsTable
                    items={allItems}
                    loading={isLoading}
                    total={allTotal}
                    page={page}
                    perPage={perPage}
                    onPageChange={setPage}
                    onOpenDrawer={openDrawer}
                    onConfirm={(id) => confirmMutation.mutate(id)}
                    onOpenReclassify={openReclassify}
                    confirmLoading={confirmMutation.isPending}
                  />
                </>
              ),
            },
            {
              key: 'unconfirmed',
              label: (
                <Badge count={unconfirmedCount} offset={[10, 0]} size="small">
                  <span>Ожидают подтверждения</span>
                </Badge>
              ),
              children: (
                <>
                  {selectedRowKeys.length > 0 && (
                    <Alert
                      type="info"
                      message={
                        <Space>
                          <Text>Выбрано: {selectedRowKeys.length}</Text>
                          <Button
                            type="primary"
                            size="small"
                            icon={<CheckCircleOutlined />}
                            onClick={handleBatchConfirm}
                          >
                            Подтвердить выбранные
                          </Button>
                        </Space>
                      }
                      style={{ marginBottom: 16 }}
                    />
                  )}

                  {unconfirmedCount === 0 && !unconfirmedLoading ? (
                    <Empty description="Все операции подтверждены!" />
                  ) : (
                    <OperationsTable
                      items={unconfirmedItems}
                      loading={unconfirmedLoading}
                      total={unconfirmedCount}
                      page={1}
                      perPage={100}
                      onPageChange={() => {}}
                      onOpenDrawer={openDrawer}
                      onConfirm={(id) => confirmMutation.mutate(id)}
                      onOpenReclassify={openReclassify}
                      confirmLoading={confirmMutation.isPending}
                      showSelection
                      selectedRowKeys={selectedRowKeys}
                      onSelectChange={setSelectedRowKeys}
                    />
                  )}
                </>
              ),
            },
          ]}
        />
      </Card>

      <OperationDrawer
        op={selectedOp}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        onConfirm={(id) => confirmMutation.mutate(id)}
        onReclassify={(id, cat) => reclassifyMutation.mutate({ id, category: cat })}
        confirmLoading={confirmMutation.isPending}
      />

      <Modal
        title="Изменить категорию операции"
        open={reclassifyModal.visible}
        onCancel={() =>
          setReclassifyModal({ visible: false, operationId: '', currentCategory: '' })
        }
        onOk={() =>
          reclassifyMutation.mutate({
            id: reclassifyModal.operationId,
            category: newCategory,
          })
        }
        confirmLoading={reclassifyMutation.isPending}
        okText="Сохранить"
        cancelText="Отмена"
      >
        <p>
          Текущая категория: <strong>{reclassifyModal.currentCategory || '—'}</strong>
        </p>
        <Input
          placeholder="Новая категория"
          value={newCategory}
          onChange={(e) => setNewCategory(e.target.value)}
        />
      </Modal>
    </div>
  );
}