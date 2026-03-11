/**
 * Страница загрузки файлов — drag-n-drop, список загруженных.
 */
import { useState } from 'react';
import {
  Typography,
  Card,
  Upload,
  Button,
  Table,
  Tag,
  Space,
  message,
  Popconfirm,
  Alert,
} from 'antd';
import {
  InboxOutlined,
  DeleteOutlined,
  ReloadOutlined,
  PlayCircleOutlined,
  FileTextOutlined,
  FilePdfOutlined,
  FileExcelOutlined,
  FileImageOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { filesApi } from '@/api/endpoints';
import { formatDateTime } from '@/utils/format';
import type { UploadedFile } from '@/types';
import type { ColumnsType } from 'antd/es/table';
import type { UploadFile, RcFile } from 'antd/es/upload';

const { Title } = Typography;
const { Dragger } = Upload;

function fileIcon(fileType: string) {
  if (fileType.includes('pdf')) return <FilePdfOutlined style={{ color: '#e74c3c' }} />;
  if (fileType.includes('excel') || fileType.includes('spreadsheet') || fileType.includes('csv'))
    return <FileExcelOutlined style={{ color: '#27ae60' }} />;
  if (fileType.includes('image') || fileType.includes('png') || fileType.includes('jpeg'))
    return <FileImageOutlined style={{ color: '#3498db' }} />;
  return <FileTextOutlined />;
}

function statusTag(status: string) {
  const map: Record<string, { color: string; label: string }> = {
    uploaded: { color: 'blue', label: 'Загружен' },
    queued: { color: 'blue', label: 'В очереди' },
    processing: { color: 'processing', label: 'Обработка…' },
    recognized: { color: 'green', label: 'Распознан' },
    completed: { color: 'green', label: 'Обработан' },
    done: { color: 'green', label: 'Готов' },
    error: { color: 'red', label: 'Ошибка' },
  };
  const s = map[status] || { color: 'default', label: status };
  return <Tag color={s.color}>{s.label}</Tag>;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
}

/**
 * Извлекает массив из ответа API, который может быть:
 * - массивом напрямую
 * - PaginatedResponse { data: [...] }
 * - объектом с полем items/results
 */
function extractArray<T>(data: unknown): T[] {
  if (Array.isArray(data)) return data;
  if (data && typeof data === 'object') {
    const obj = data as Record<string, unknown>;
    if (Array.isArray(obj.data)) return obj.data;
    if (Array.isArray(obj.items)) return obj.items;
    if (Array.isArray(obj.results)) return obj.results;
  }
  return [];
}

export default function UploadPage() {
  const queryClient = useQueryClient();
  const [fileList, setFileList] = useState<UploadFile[]>([]);

  // ---- Queries ----
  const {
    data: files,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['files'],
    queryFn: () => filesApi.list(),
    select: (res) => extractArray<UploadedFile>(res.data),
  });

  // ---- Mutations ----
  const uploadMutation = useMutation({
    mutationFn: (rawFiles: File[]) => filesApi.upload(rawFiles),
    onSuccess: () => {
      message.success('Файлы загружены и отправлены на обработку');
      setFileList([]);
      queryClient.invalidateQueries({ queryKey: ['files'] });
    },
    onError: () => {
      message.error('Ошибка загрузки файлов');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => filesApi.delete(id),
    onSuccess: () => {
      message.success('Файл удален');
      queryClient.invalidateQueries({ queryKey: ['files'] });
    },
    onError: () => {
      message.error('Не удалось удалить файл');
    },
  });

  const reprocessMutation = useMutation({
    mutationFn: (id: string) => filesApi.reprocess(id),
    onSuccess: () => {
      message.success('Файл отправлен на обработку');
      queryClient.invalidateQueries({ queryKey: ['files'] });
    },
    onError: () => {
      message.error('Не удалось запустить обработку');
    },
  });

  // ---- Upload handler ----
  const handleUpload = () => {
    const rawFiles = fileList
      .map((f) => f.originFileObj)
      .filter(Boolean) as File[];
    if (rawFiles.length === 0) {
      message.warning('Выберите хотя бы один файл');
      return;
    }
    uploadMutation.mutate(rawFiles);
  };

  // ---- Table columns ----
  const columns: ColumnsType<UploadedFile> = [
    {
      title: '',
      dataIndex: 'file_type',
      key: 'icon',
      width: 40,
      render: (ft: string) => fileIcon(ft || ''),
    },
    {
      title: 'Файл',
      dataIndex: 'original_filename',
      key: 'name',
      ellipsis: true,
    },
    {
      title: 'Размер',
      dataIndex: 'file_size',
      key: 'size',
      width: 100,
      render: (v: number) => formatFileSize(v || 0),
    },
    {
      title: 'Статус',
      dataIndex: 'processing_status',
      key: 'status',
      width: 140,
      render: (s: string) => statusTag(s || 'uploaded'),
    },
    {
      title: 'Загружен',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (d: string) => (d ? formatDateTime(d) : '—'),
    },
    {
      title: '',
      key: 'actions',
      width: 100,
      render: (_: unknown, record: UploadedFile) => (
        <Space size={4}>
          <Button
            type="text"
            icon={<PlayCircleOutlined />}
            size="small"
            title="Обработать"
            loading={reprocessMutation.isPending}
            onClick={() => reprocessMutation.mutate(record.id)}
          />
          <Popconfirm
            title="Удалить файл?"
            onConfirm={() => deleteMutation.mutate(record.id)}
            okText="Да"
            cancelText="Нет"
          >
            <Button
              type="text"
              danger
              icon={<DeleteOutlined />}
              size="small"
              loading={deleteMutation.isPending}
            />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Title level={3}>📤 Загрузка файлов</Title>

      {/* Drag-n-drop zone */}
      <Card style={{ marginBottom: 16 }}>
        <Dragger
          multiple
          fileList={fileList}
          beforeUpload={(_file: RcFile) => false}
          onChange={({ fileList: fl }) => setFileList(fl)}
          accept=".pdf,.xlsx,.xls,.csv,.jpg,.jpeg,.png,.tiff,.bmp"
        >
          <p className="ant-upload-drag-icon">
            <InboxOutlined />
          </p>
          <p className="ant-upload-text">
            Перетащите файлы сюда или нажмите для выбора
          </p>
          <p className="ant-upload-hint">
            PDF, Excel (xlsx/xls/csv), изображения (jpg, png, tiff). До 20 МБ каждый.
          </p>
        </Dragger>

        {fileList.length > 0 && (
          <div style={{ marginTop: 16, textAlign: 'right' }}>
            <Space>
              <Button onClick={() => setFileList([])}>Очистить</Button>
              <Button
                type="primary"
                onClick={handleUpload}
                loading={uploadMutation.isPending}
              >
                Загрузить {fileList.length} файл(ов)
              </Button>
            </Space>
          </div>
        )}
      </Card>

      {/* Uploaded files list */}
      <Card
        title="Загруженные файлы"
        extra={
          <Button
            icon={<ReloadOutlined />}
            onClick={() => queryClient.invalidateQueries({ queryKey: ['files'] })}
            size="small"
          >
            Обновить
          </Button>
        }
      >
        {error && (
          <Alert
            type="error"
            message="Ошибка загрузки списка файлов"
            style={{ marginBottom: 16 }}
          />
        )}
        <Table<UploadedFile>
          rowKey="id"
          columns={columns}
          dataSource={files || []}
          loading={isLoading}
          pagination={{ pageSize: 20, showSizeChanger: false }}
          size="middle"
          locale={{ emptyText: 'Нет загруженных файлов' }}
        />
      </Card>
    </div>
  );
}