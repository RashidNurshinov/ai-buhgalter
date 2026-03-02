/**
 * Страница деклараций — список, генерация, валидация, скачивание XML.
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
  Modal,
  Select,
  InputNumber,
  Row,
  Col,
  Tooltip,
  Descriptions,
} from 'antd';
import {
  PlusOutlined,
  ReloadOutlined,
  DownloadOutlined,
  CheckCircleOutlined,
  FileTextOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { declarationsApi } from '@/api/endpoints';
import { formatDateTime } from '@/utils/format';
import dayjs from 'dayjs';
import type { ColumnsType } from 'antd/es/table';

const { Title } = Typography;

interface Declaration {
  id: string;
  declaration_type: string;
  year: number;
  quarter?: number;
  status: string;
  xml_url?: string;
  validation_result?: {
    valid: boolean;
    errors: string[];
  };
  created_at: string;
  updated_at: string;
}

const DECLARATION_TYPES: Record<string, string> = {
  usn: 'УСН (Декларация)',
  ndfl_3: '3-НДФЛ',
  nds: 'НДС',
  rsv: 'РСВ',
  '6ndfl': '6-НДФЛ',
};

function statusTag(status: string) {
  const map: Record<string, { color: string; label: string }> = {
    draft: { color: 'default', label: 'Черновик' },
    generated: { color: 'blue', label: 'Сформирована' },
    validated: { color: 'green', label: 'Проверена' },
    validation_error: { color: 'red', label: 'Ошибки' },
    submitted: { color: 'purple', label: 'Отправлена' },
  };
  const s = map[status] || { color: 'default', label: status };
  return <Tag color={s.color}>{s.label}</Tag>;
}

const currentYear = dayjs().year();

export default function DeclarationsPage() {
  const queryClient = useQueryClient();
  const [createModal, setCreateModal] = useState(false);
  const [detailModal, setDetailModal] = useState<Declaration | null>(null);

  // Form state for new declaration
  const [formType, setFormType] = useState<string>('usn');
  const [formYear, setFormYear] = useState(currentYear);
  const [formQuarter, setFormQuarter] = useState<number | undefined>();

  const { data, isLoading, error } = useQuery({
    queryKey: ['declarations'],
    queryFn: () => declarationsApi.list(),
    select: (res) => res.data,
  });

  const generateMutation = useMutation({
    mutationFn: (params: {
      declaration_type: string;
      year: number;
      quarter?: number;
    }) => declarationsApi.generate(params),
    onSuccess: () => {
      message.success('Декларация сформирована');
      setCreateModal(false);
      queryClient.invalidateQueries({ queryKey: ['declarations'] });
    },
    onError: () => message.error('Ошибка формирования'),
  });

  const validateMutation = useMutation({
    mutationFn: (id: string) => declarationsApi.validate(id),
    onSuccess: () => {
      message.success('Проверка завершена');
      queryClient.invalidateQueries({ queryKey: ['declarations'] });
    },
    onError: () => message.error('Ошибка проверки'),
  });

  const items: Declaration[] = Array.isArray(data)
    ? data
    : data?.items || [];

  const columns: ColumnsType<Declaration> = [
    {
      title: 'Тип',
      dataIndex: 'declaration_type',
      key: 'type',
      width: 160,
      render: (t: string) => (
        <Tag color="blue">{DECLARATION_TYPES[t] || t}</Tag>
      ),
    },
    {
      title: 'Год',
      dataIndex: 'year',
      key: 'year',
      width: 80,
    },
    {
      title: 'Квартал',
      dataIndex: 'quarter',
      key: 'quarter',
      width: 90,
      render: (q: number | undefined) =>
        q ? ['I', 'II', 'III', 'IV'][q - 1] || q : 'Год',
    },
    {
      title: 'Статус',
      dataIndex: 'status',
      key: 'status',
      width: 140,
      render: (s: string) => statusTag(s),
    },
    {
      title: 'Создана',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (d: string) => formatDateTime(d),
    },
    {
      title: '',
      key: 'actions',
      width: 160,
      render: (_: unknown, record: Declaration) => (
        <Space size="small">
          <Tooltip title="Подробнее">
            <Button
              type="text"
              icon={<FileTextOutlined />}
              size="small"
              onClick={() => setDetailModal(record)}
            />
          </Tooltip>
          {record.status === 'generated' && (
            <Tooltip title="Проверить">
              <Button
                type="text"
                icon={<CheckCircleOutlined style={{ color: '#1677ff' }} />}
                size="small"
                onClick={() => validateMutation.mutate(record.id)}
                loading={validateMutation.isPending}
              />
            </Tooltip>
          )}
          {(record.status === 'validated' || record.status === 'generated') && (
            <Tooltip title="Скачать XML">
              <Button
                type="text"
                icon={<DownloadOutlined style={{ color: '#52c41a' }} />}
                size="small"
                onClick={async () => {
                  try {
                    const res = await declarationsApi.getXml(record.id);
                    const blob = new Blob([JSON.stringify(res.data)], {
                      type: 'application/xml',
                    });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `declaration_${record.declaration_type}_${record.year}.xml`;
                    a.click();
                    URL.revokeObjectURL(url);
                  } catch {
                    message.error('Ошибка скачивания');
                  }
                }}
              />
            </Tooltip>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Title level={3}>📋 Декларации</Title>

      <Card>
        <Space style={{ marginBottom: 16 }}>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setCreateModal(true)}
          >
            Сформировать декларацию
          </Button>
          <Button
            icon={<ReloadOutlined />}
            onClick={() =>
              queryClient.invalidateQueries({ queryKey: ['declarations'] })
            }
          >
            Обновить
          </Button>
        </Space>

        {error && (
          <Alert
            type="error"
            message="Ошибка загрузки деклараций"
            style={{ marginBottom: 16 }}
          />
        )}

        <Table<Declaration>
          rowKey="id"
          columns={columns}
          dataSource={items}
          loading={isLoading}
          size="middle"
          locale={{ emptyText: 'Нет деклараций' }}
          pagination={{ pageSize: 20 }}
        />
      </Card>

      {/* Create Modal */}
      <Modal
        title="Сформировать декларацию"
        open={createModal}
        onCancel={() => setCreateModal(false)}
        onOk={() =>
          generateMutation.mutate({
            declaration_type: formType,
            year: formYear,
            quarter: formQuarter,
          })
        }
        confirmLoading={generateMutation.isPending}
        okText="Сформировать"
        cancelText="Отмена"
      >
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <div>
            <div style={{ marginBottom: 4, fontWeight: 500 }}>Тип декларации</div>
            <Select
              value={formType}
              onChange={setFormType}
              style={{ width: '100%' }}
              options={Object.entries(DECLARATION_TYPES).map(
                ([value, label]) => ({ value, label }),
              )}
            />
          </div>
          <Row gutter={16}>
            <Col span={12}>
              <div style={{ marginBottom: 4, fontWeight: 500 }}>Год</div>
              <InputNumber
                value={formYear}
                onChange={(v) => setFormYear(v || currentYear)}
                min={2020}
                max={currentYear + 1}
                style={{ width: '100%' }}
              />
            </Col>
            <Col span={12}>
              <div style={{ marginBottom: 4, fontWeight: 500 }}>
                Квартал (необязательно)
              </div>
              <Select
                value={formQuarter}
                onChange={setFormQuarter}
                style={{ width: '100%' }}
                allowClear
                placeholder="Годовая"
                options={[
                  { value: 1, label: 'I квартал' },
                  { value: 2, label: 'II квартал' },
                  { value: 3, label: 'III квартал' },
                  { value: 4, label: 'IV квартал' },
                ]}
              />
            </Col>
          </Row>
        </Space>
      </Modal>

      {/* Detail Modal */}
      <Modal
        title={`Декларация: ${
          detailModal
            ? DECLARATION_TYPES[detailModal.declaration_type] ||
              detailModal.declaration_type
            : ''
        }`}
        open={!!detailModal}
        onCancel={() => setDetailModal(null)}
        footer={null}
        width={600}
      >
        {detailModal && (
          <Descriptions bordered column={1} size="small">
            <Descriptions.Item label="Тип">
              {DECLARATION_TYPES[detailModal.declaration_type] ||
                detailModal.declaration_type}
            </Descriptions.Item>
            <Descriptions.Item label="Год">
              {detailModal.year}
            </Descriptions.Item>
            <Descriptions.Item label="Квартал">
              {detailModal.quarter
                ? ['I', 'II', 'III', 'IV'][detailModal.quarter - 1]
                : 'Годовая'}
            </Descriptions.Item>
            <Descriptions.Item label="Статус">
              {statusTag(detailModal.status)}
            </Descriptions.Item>
            <Descriptions.Item label="Создана">
              {formatDateTime(detailModal.created_at)}
            </Descriptions.Item>
            <Descriptions.Item label="Обновлена">
              {formatDateTime(detailModal.updated_at)}
            </Descriptions.Item>
            {detailModal.validation_result && (
              <Descriptions.Item label="Результат проверки">
                {detailModal.validation_result.valid ? (
                  <Tag color="green">✓ Валидна</Tag>
                ) : (
                  <div>
                    <Tag color="red">✗ Ошибки</Tag>
                    <ul style={{ marginTop: 8, paddingLeft: 16 }}>
                      {detailModal.validation_result.errors.map((e, i) => (
                        <li key={i} style={{ color: '#cf1322' }}>
                          {e}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </Descriptions.Item>
            )}
          </Descriptions>
        )}
      </Modal>
    </div>
  );
}