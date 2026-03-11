/**
 * Страница документов — таблица, фильтры (дата, контрагент, тип, статус), карточка документа.
 * Пункт плана: 1.18.4
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
  Input,
  DatePicker,
  Drawer,
  Descriptions,
  Divider,
  Statistic,
  Row,
  Col,
} from 'antd';
import {
  CheckCircleOutlined,
  ReloadOutlined,
  EyeOutlined,
  SearchOutlined,
  FilterOutlined,
  FileTextOutlined,
  CloseOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { documentsApi } from '@/api/endpoints';
import { formatDate, formatMoney, documentStatusLabel } from '@/utils/format';
import type { Document, DocumentType, DocumentStatus } from '@/types';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;

const DOC_TYPE_LABELS: Record<string, string> = {
  invoice: 'Счёт-фактура',
  act: 'Акт',
  upd: 'УПД',
  torg12: 'ТОРГ-12',
  bank_statement: 'Выписка',
  cash_receipt: 'Кассовый чек',
  contract: 'Договор',
  unknown: 'Неизвестный',
};

function docTypeTag(dt: DocumentType) {
  const colorMap: Record<string, string> = {
    invoice: 'blue',
    act: 'green',
    upd: 'purple',
    torg12: 'orange',
    bank_statement: 'cyan',
    cash_receipt: 'gold',
    contract: 'geekblue',
    unknown: 'default',
  };
  return <Tag color={colorMap[dt] || 'default'}>{DOC_TYPE_LABELS[dt] || dt}</Tag>;
}

function statusTag(status: DocumentStatus) {
  const colorMap: Record<string, string> = {
    uploading: 'default',
    uploaded: 'blue',
    processing: 'processing',
    recognized: 'green',
    confirmed: 'success',
    rejected: 'volcano',
    error: 'red',
  };
  return <Tag color={colorMap[status] || 'default'}>{documentStatusLabel(status)}</Tag>;
}

/* ==================== Document Detail Drawer ==================== */
function DocumentDrawer({
  doc,
  open,
  onClose,
  onConfirm,
  confirmLoading,
}: {
  doc: Document | null;
  open: boolean;
  onClose: () => void;
  onConfirm: (id: string) => void;
  confirmLoading: boolean;
}) {
  if (!doc) return null;

  return (
    <Drawer
      title={
        <Space>
          <FileTextOutlined />
          <span>Документ {doc.doc_number || '(без номера)'}</span>
        </Space>
      }
      open={open}
      onClose={onClose}
      width={520}
      extra={
        <Space>
          {doc.status === 'recognized' && (
            <Button
              type="primary"
              icon={<CheckCircleOutlined />}
              onClick={() => onConfirm(doc.id)}
              loading={confirmLoading}
            >
              Подтвердить
            </Button>
          )}
          <Button icon={<CloseOutlined />} onClick={onClose} />
        </Space>
      }
    >
      {/* Status badge */}
      <div style={{ marginBottom: 16 }}>
        {statusTag(doc.status)}
        {doc.confidence_score != null && (
          <Tag
            color={doc.confidence_score >= 0.8 ? 'green' : doc.confidence_score >= 0.5 ? 'orange' : 'red'}
            style={{ marginLeft: 8 }}
          >
            Точность: {(doc.confidence_score * 100).toFixed(0)}%
          </Tag>
        )}
      </div>

      <Descriptions column={1} size="small" bordered>
        <Descriptions.Item label="Тип документа">
          {docTypeTag(doc.doc_type)}
        </Descriptions.Item>
        <Descriptions.Item label="Номер">
          {doc.doc_number || '—'}
        </Descriptions.Item>
        <Descriptions.Item label="Дата документа">
          {formatDate(doc.doc_date)}
        </Descriptions.Item>
        <Descriptions.Item label="Контрагент">
          <div>
            <Text strong>{doc.counterparty_name || '—'}</Text>
            {doc.counterparty_inn && (
              <div>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  ИНН: {doc.counterparty_inn}
                </Text>
              </div>
            )}
          </div>
        </Descriptions.Item>
      </Descriptions>

      <Divider>Суммы</Divider>

      <Row gutter={16}>
        <Col span={8}>
          <Statistic
            title="Без НДС"
            value={doc.total_without_vat || 0}
            formatter={(val) => formatMoney(val as number)}
            valueStyle={{ fontSize: 16 }}
          />
        </Col>
        <Col span={8}>
          <Statistic
            title="НДС"
            value={doc.vat_amount || 0}
            formatter={(val) => formatMoney(val as number)}
            valueStyle={{ fontSize: 16, color: '#1677ff' }}
          />
        </Col>
        <Col span={8}>
          <Statistic
            title="Итого"
            value={doc.total_with_vat || 0}
            formatter={(val) => formatMoney(val as number)}
            valueStyle={{ fontSize: 16, fontWeight: 700 }}
          />
        </Col>
      </Row>

      <Divider>Служебная информация</Divider>

      <Descriptions column={1} size="small">
        <Descriptions.Item label="ID">{doc.id}</Descriptions.Item>
        <Descriptions.Item label="Загружен">{formatDate(doc.created_at)}</Descriptions.Item>
      </Descriptions>
    </Drawer>
  );
}

/* ==================== Main Page ==================== */
export default function DocumentsPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [perPage] = useState(20);
  const [filterType, setFilterType] = useState<string | undefined>();
  const [filterStatus, setFilterStatus] = useState<string | undefined>();
  const [searchCounterparty, setSearchCounterparty] = useState('');
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null] | null>(null);
  const [selectedDoc, setSelectedDoc] = useState<Document | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [showFilters, setShowFilters] = useState(false);

  const { data, isLoading, error } = useQuery({
    queryKey: ['documents', page, perPage, filterType, filterStatus],
    queryFn: () =>
      documentsApi.list({
        page,
        per_page: perPage,
        doc_type: filterType,
        status: filterStatus,
      }),
    select: (res) => res.data,
  });

  const confirmMutation = useMutation({
    mutationFn: (id: string) => documentsApi.confirm(id),
    onSuccess: () => {
      message.success('Документ подтверждён');
      queryClient.invalidateQueries({ queryKey: ['documents'] });
      setDrawerOpen(false);
    },
    onError: () => {
      message.error('Ошибка подтверждения');
    },
  });

  // Support both paginated and array response
  let items: Document[] = Array.isArray(data) ? data : data?.items || [];
  const total: number = Array.isArray(data) ? data.length : data?.total || 0;

  // Client-side filtering for counterparty search and date range
  if (searchCounterparty.trim()) {
    const q = searchCounterparty.toLowerCase();
    items = items.filter(
      (d) =>
        (d.counterparty_name || '').toLowerCase().includes(q) ||
        (d.counterparty_inn || '').includes(q),
    );
  }

  if (dateRange && dateRange[0] && dateRange[1]) {
    const start = dateRange[0].startOf('day');
    const end = dateRange[1].endOf('day');
    items = items.filter((d) => {
      if (!d.doc_date) return false;
      const docDate = dayjs(d.doc_date);
      return docDate.isAfter(start) && docDate.isBefore(end);
    });
  }

  const openDrawer = (doc: Document) => {
    setSelectedDoc(doc);
    setDrawerOpen(true);
  };

  // Stats
  const recognizedCount = items.filter((d) => d.status === 'recognized').length;
  const totalVat = items.reduce((sum, d) => sum + (d.vat_amount || 0), 0);

  const columns: ColumnsType<Document> = [
    {
      title: 'Тип',
      dataIndex: 'doc_type',
      key: 'doc_type',
      width: 140,
      render: (dt: DocumentType) => docTypeTag(dt),
    },
    {
      title: '№',
      dataIndex: 'doc_number',
      key: 'doc_number',
      width: 120,
      render: (v: string | null) => v || '—',
    },
    {
      title: 'Дата',
      dataIndex: 'doc_date',
      key: 'doc_date',
      width: 110,
      sorter: (a: Document, b: Document) =>
        (a.doc_date || '').localeCompare(b.doc_date || ''),
      render: (d: string | null) => formatDate(d),
    },
    {
      title: 'Контрагент',
      dataIndex: 'counterparty_name',
      key: 'counterparty',
      ellipsis: true,
      render: (name: string | null, record: Document) => (
        <span>
          {name || '—'}
          {record.counterparty_inn && (
            <span style={{ color: '#999', marginLeft: 4, fontSize: 12 }}>
              ИНН {record.counterparty_inn}
            </span>
          )}
        </span>
      ),
    },
    {
      title: 'Сумма без НДС',
      dataIndex: 'total_without_vat',
      key: 'total_without_vat',
      width: 140,
      align: 'right',
      sorter: (a: Document, b: Document) =>
        (a.total_without_vat || 0) - (b.total_without_vat || 0),
      render: (v: number | null) => formatMoney(v),
    },
    {
      title: 'НДС',
      dataIndex: 'vat_amount',
      key: 'vat_amount',
      width: 120,
      align: 'right',
      render: (v: number | null) => formatMoney(v),
    },
    {
      title: 'Итого',
      dataIndex: 'total_with_vat',
      key: 'total_with_vat',
      width: 140,
      align: 'right',
      sorter: (a: Document, b: Document) =>
        (a.total_with_vat || 0) - (b.total_with_vat || 0),
      render: (v: number | null) => <strong>{formatMoney(v)}</strong>,
    },
    {
      title: 'Точность',
      dataIndex: 'confidence_score',
      key: 'confidence',
      width: 90,
      align: 'center',
      render: (v: number | null) =>
        v != null ? (
          <Tag color={v >= 0.8 ? 'green' : v >= 0.5 ? 'orange' : 'red'}>
            {(v * 100).toFixed(0)}%
          </Tag>
        ) : (
          '—'
        ),
    },
    {
      title: 'Статус',
      dataIndex: 'status',
      key: 'status',
      width: 130,
      render: (s: DocumentStatus) => statusTag(s),
    },
    {
      title: '',
      key: 'actions',
      width: 100,
      render: (_: unknown, record: Document) => (
        <Space size="small">
          <Tooltip title="Просмотр">
            <Button
              type="text"
              icon={<EyeOutlined />}
              size="small"
              onClick={() => openDrawer(record)}
            />
          </Tooltip>
          {record.status === 'recognized' && (
            <Tooltip title="Подтвердить">
              <Button
                type="text"
                icon={<CheckCircleOutlined style={{ color: '#52c41a' }} />}
                size="small"
                onClick={() => confirmMutation.mutate(record.id)}
                loading={confirmMutation.isPending}
              />
            </Tooltip>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Title level={3}>📄 Документы</Title>

      {/* Summary stats */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic title="Всего" value={total} />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title="Ожидают подтверждения"
              value={recognizedCount}
              valueStyle={{ color: recognizedCount > 0 ? '#faad14' : undefined }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title="Итого НДС"
              value={totalVat}
              formatter={(val) => formatMoney(val as number)}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small">
            <Statistic
              title="На странице"
              value={items.length}
            />
          </Card>
        </Col>
      </Row>

      <Card>
        {/* Primary filters row */}
        <Space wrap style={{ marginBottom: 16 }}>
          <Input
            placeholder="Поиск по контрагенту / ИНН"
            prefix={<SearchOutlined />}
            allowClear
            style={{ width: 260 }}
            value={searchCounterparty}
            onChange={(e) => setSearchCounterparty(e.target.value)}
          />
          <Select
            placeholder="Тип документа"
            allowClear
            style={{ width: 180 }}
            value={filterType}
            onChange={(v) => {
              setFilterType(v);
              setPage(1);
            }}
            options={Object.entries(DOC_TYPE_LABELS).map(([value, label]) => ({
              value,
              label,
            }))}
          />
          <Select
            placeholder="Статус"
            allowClear
            style={{ width: 160 }}
            value={filterStatus}
            onChange={(v) => {
              setFilterStatus(v);
              setPage(1);
            }}
            options={[
              { value: 'uploading', label: 'Загружается' },
              { value: 'uploaded', label: 'Загружен' },
              { value: 'processing', label: 'Обработка' },
              { value: 'recognized', label: 'Распознан' },
              { value: 'confirmed', label: 'Подтверждён' },
              { value: 'rejected', label: 'Отклонён' },
              { value: 'error', label: 'Ошибка' },
            ]}
          />
          <Button
            icon={<FilterOutlined />}
            onClick={() => setShowFilters(!showFilters)}
            type={showFilters ? 'primary' : 'default'}
          >
            Фильтры
          </Button>
          <Button
            icon={<ReloadOutlined />}
            onClick={() =>
              queryClient.invalidateQueries({ queryKey: ['documents'] })
            }
          >
            Обновить
          </Button>
        </Space>

        {/* Extended filters */}
        {showFilters && (
          <div
            style={{
              marginBottom: 16,
              padding: 12,
              background: '#fafafa',
              borderRadius: 8,
              border: '1px solid #f0f0f0',
            }}
          >
            <Space wrap>
              <div>
                <Text type="secondary" style={{ display: 'block', fontSize: 12, marginBottom: 4 }}>
                  Дата документа
                </Text>
                <RangePicker
                  value={dateRange as [dayjs.Dayjs, dayjs.Dayjs] | null}
                  onChange={(vals) => setDateRange(vals)}
                  format="DD.MM.YYYY"
                  placeholder={['От', 'До']}
                />
              </div>
              <Button
                size="small"
                onClick={() => {
                  setSearchCounterparty('');
                  setFilterType(undefined);
                  setFilterStatus(undefined);
                  setDateRange(null);
                  setPage(1);
                }}
              >
                Сбросить все фильтры
              </Button>
            </Space>
          </div>
        )}

        {error && (
          <Alert
            type="error"
            message="Ошибка загрузки документов"
            style={{ marginBottom: 16 }}
          />
        )}

        <Table<Document>
          rowKey="id"
          columns={columns}
          dataSource={items}
          loading={isLoading}
          scroll={{ x: 1200 }}
          size="middle"
          locale={{ emptyText: 'Нет документов' }}
          onRow={(record) => ({
            onClick: () => openDrawer(record),
            style: { cursor: 'pointer' },
          })}
          rowClassName={(record) =>
            record.status === 'recognized' ? 'ant-table-row-light-warning' : ''
          }
          pagination={{
            current: page,
            pageSize: perPage,
            total,
            showTotal: (t) => `Всего: ${t}`,
            showSizeChanger: false,
            onChange: (p) => setPage(p),
          }}
        />
      </Card>

      {/* Document Detail Drawer */}
      <DocumentDrawer
        doc={selectedDoc}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        onConfirm={(id) => confirmMutation.mutate(id)}
        confirmLoading={confirmMutation.isPending}
      />
    </div>
  );
}