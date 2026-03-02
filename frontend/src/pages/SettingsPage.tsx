/**
 * Страница настроек — профиль, банковские счета, уведомления, налоговые ставки.
 */
import { useState } from 'react';
import {
  Typography,
  Card,
  Tabs,
  Form,
  Input,
  Select,
  Button,
  Switch,
  Space,
  message,
  Divider,
  InputNumber,
  Alert,
  Descriptions,
  Tag,
} from 'antd';
import {
  UserOutlined,
  BankOutlined,
  BellOutlined,
  PercentageOutlined,
  SaveOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { userApi } from '@/api/endpoints';
import { useAuthStore } from '@/store/authStore';
import { taxSystemLabel } from '@/utils/format';
import type { User, UserUpdate } from '@/types';

const { Title, Text } = Typography;

const TAX_SYSTEMS = [
  { value: 'usn_income', label: 'УСН Доходы (6%)' },
  { value: 'usn_income_expense', label: 'УСН Доходы−Расходы (15%)' },
  { value: 'osno', label: 'ОСНО' },
  { value: 'patent', label: 'Патент (ПСН)' },
  { value: 'eshn', label: 'ЕСХН' },
  { value: 'auto', label: 'Самозанятый (НПД)' },
];

/* ==================== Profile Tab ==================== */
function ProfileTab() {
  const queryClient = useQueryClient();
  const { user, setUser } = useAuthStore();
  const [form] = Form.useForm();

  const { data: userData } = useQuery({
    queryKey: ['user-me'],
    queryFn: () => userApi.getMe(),
    select: (res) => res.data as User,
  });

  const updateMutation = useMutation({
    mutationFn: (values: UserUpdate) => userApi.updateMe(values),
    onSuccess: (res) => {
      message.success('Профиль обновлён');
      const updated = res.data as User;
      setUser(updated);
      queryClient.invalidateQueries({ queryKey: ['user-me'] });
    },
    onError: () => message.error('Ошибка сохранения'),
  });

  const initialValues = userData || user;

  return (
    <div>
      <Text type="secondary" style={{ display: 'block', marginBottom: 16 }}>
        Основные данные вашего бизнеса. ИНН используется для формирования деклараций.
      </Text>

      <Form
        form={form}
        layout="vertical"
        initialValues={{
          full_name: initialValues?.full_name || '',
          inn: initialValues?.inn || '',
          business_name: initialValues?.business_name || '',
          tax_system: initialValues?.tax_system || 'usn_income_expense',
        }}
        onFinish={(values) => updateMutation.mutate(values)}
        style={{ maxWidth: 600 }}
      >
        <Form.Item
          name="full_name"
          label="ФИО / Наименование ИП"
          rules={[{ required: true, message: 'Укажите имя' }]}
        >
          <Input placeholder="Иванов Иван Иванович" />
        </Form.Item>

        <Form.Item
          name="inn"
          label="ИНН"
          rules={[
            { pattern: /^\d{10}$|^\d{12}$/, message: 'ИНН должен быть 10 или 12 цифр' },
          ]}
        >
          <Input placeholder="1234567890" maxLength={12} />
        </Form.Item>

        <Form.Item name="business_name" label="Название бизнеса">
          <Input placeholder="ИП Иванов И.И." />
        </Form.Item>

        <Form.Item
          name="tax_system"
          label="Система налогообложения"
          rules={[{ required: true, message: 'Выберите систему' }]}
        >
          <Select options={TAX_SYSTEMS} />
        </Form.Item>

        <Form.Item>
          <Button
            type="primary"
            htmlType="submit"
            icon={<SaveOutlined />}
            loading={updateMutation.isPending}
          >
            Сохранить
          </Button>
        </Form.Item>
      </Form>

      {/* Current data */}
      {initialValues && (
        <>
          <Divider />
          <Descriptions title="Текущие данные" column={1} size="small">
            <Descriptions.Item label="Email">{initialValues.email}</Descriptions.Item>
            <Descriptions.Item label="ФИО">{initialValues.full_name || '—'}</Descriptions.Item>
            <Descriptions.Item label="ИНН">{initialValues.inn || '—'}</Descriptions.Item>
            <Descriptions.Item label="Бизнес">{initialValues.business_name || '—'}</Descriptions.Item>
            <Descriptions.Item label="Система НО">
              <Tag color="blue">{taxSystemLabel(initialValues.tax_system)}</Tag>
            </Descriptions.Item>
          </Descriptions>
        </>
      )}
    </div>
  );
}

/* ==================== Bank Accounts Tab ==================== */
function BankAccountsTab() {
  return (
    <div>
      <Text type="secondary" style={{ display: 'block', marginBottom: 16 }}>
        Банковские счета для автоматической загрузки выписок.
      </Text>

      <Alert
        type="info"
        message="В разработке"
        description="Подключение банковских API (Сбер, Тинькофф) будет доступно в следующей версии. 
Сейчас вы можете загружать выписки вручную на странице «Загрузка»."
        showIcon
        style={{ marginBottom: 24 }}
      />

      <Card size="small" title="Добавить банковский счёт" style={{ maxWidth: 500 }}>
        <Form layout="vertical">
          <Form.Item label="Название банка">
            <Input placeholder="Сбербанк" disabled />
          </Form.Item>
          <Form.Item label="Номер счёта">
            <Input placeholder="40802810XXXXXXXXXX" disabled />
          </Form.Item>
          <Form.Item label="БИК">
            <Input placeholder="044525225" disabled />
          </Form.Item>
          <Form.Item>
            <Button type="primary" disabled>
              Добавить (скоро)
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}

/* ==================== Notifications Tab ==================== */
function NotificationsTab() {
  const [emailEnabled, setEmailEnabled] = useState(true);
  const [telegramEnabled, setTelegramEnabled] = useState(false);

  return (
    <div>
      <Text type="secondary" style={{ display: 'block', marginBottom: 16 }}>
        Настройте уведомления о налоговых сроках и важных событиях.
      </Text>

      <Card size="small" style={{ maxWidth: 500, marginBottom: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }} size="large">
          {/* Email */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <Text strong>📧 Email-уведомления</Text>
                <br />
                <Text type="secondary" style={{ fontSize: 12 }}>
                  Напоминания о дедлайнах и отчёты
                </Text>
              </div>
              <Switch checked={emailEnabled} onChange={setEmailEnabled} />
            </div>
            {emailEnabled && (
              <div style={{ marginTop: 8 }}>
                <Input placeholder="email@example.com" style={{ maxWidth: 300 }} />
              </div>
            )}
          </div>

          <Divider style={{ margin: '8px 0' }} />

          {/* Telegram */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <Text strong>📱 Telegram-уведомления</Text>
                <br />
                <Text type="secondary" style={{ fontSize: 12 }}>
                  Мгновенные уведомления через бот
                </Text>
              </div>
              <Switch checked={telegramEnabled} onChange={setTelegramEnabled} />
            </div>
            {telegramEnabled && (
              <Alert
                type="info"
                message="Telegram-бот будет доступен позже"
                style={{ marginTop: 8 }}
                showIcon
              />
            )}
          </div>

          <Divider style={{ margin: '8px 0' }} />

          {/* Reminder settings */}
          <div>
            <Text strong>⏰ Напоминания о сроках</Text>
            <div style={{ marginTop: 8 }}>
              <Space direction="vertical" size="small">
                <Switch defaultChecked size="small" /> <Text style={{ fontSize: 13 }}>За 14 дней до дедлайна</Text>
                <br />
                <Switch defaultChecked size="small" /> <Text style={{ fontSize: 13 }}>За 7 дней до дедлайна</Text>
                <br />
                <Switch defaultChecked size="small" /> <Text style={{ fontSize: 13 }}>За 3 дня до дедлайна</Text>
                <br />
                <Switch defaultChecked size="small" /> <Text style={{ fontSize: 13 }}>В день дедлайна</Text>
              </Space>
            </div>
          </div>
        </Space>
      </Card>

      <Button type="primary" icon={<SaveOutlined />} disabled>
        Сохранить настройки (скоро)
      </Button>
    </div>
  );
}

/* ==================== Tax Rates Tab ==================== */
function TaxRatesTab() {
  return (
    <div>
      <Text type="secondary" style={{ display: 'block', marginBottom: 16 }}>
        Ставки налогов применяемые для расчётов. Значения по умолчанию соответствуют НК РФ 2026.
      </Text>

      <Card size="small" style={{ maxWidth: 600 }}>
        <Form layout="vertical">
          <Title level={5}>УСН</Title>
          <Space wrap>
            <Form.Item label="Ставка УСН «Доходы»">
              <InputNumber
                defaultValue={6}
                min={0}
                max={8}
                suffix="%"
                style={{ width: 120 }}
                disabled
              />
            </Form.Item>
            <Form.Item label="Ставка УСН «Д−Р»">
              <InputNumber
                defaultValue={15}
                min={0}
                max={20}
                suffix="%"
                style={{ width: 120 }}
                disabled
              />
            </Form.Item>
            <Form.Item label="Минимальный налог">
              <InputNumber
                defaultValue={1}
                suffix="%"
                style={{ width: 120 }}
                disabled
              />
            </Form.Item>
          </Space>

          <Divider />

          <Title level={5}>НДС (с 01.01.2026)</Title>
          <Space wrap>
            <Form.Item label="Основная ставка НДС">
              <InputNumber
                defaultValue={22}
                suffix="%"
                style={{ width: 120 }}
                disabled
              />
            </Form.Item>
            <Form.Item label="Расчётная ставка">
              <Input defaultValue="22/122" style={{ width: 120 }} disabled />
            </Form.Item>
          </Space>

          <Divider />

          <Title level={5}>НДФЛ</Title>
          <Space wrap>
            <Form.Item label="Базовая ставка">
              <InputNumber
                defaultValue={13}
                suffix="%"
                style={{ width: 120 }}
                disabled
              />
            </Form.Item>
            <Form.Item label="Повышенная (свыше 5 млн)">
              <InputNumber
                defaultValue={15}
                suffix="%"
                style={{ width: 120 }}
                disabled
              />
            </Form.Item>
          </Space>

          <Divider />

          <Title level={5}>Страховые взносы ИП (2026)</Title>
          <Space wrap>
            <Form.Item label="Фиксированные взносы">
              <InputNumber
                defaultValue={53658}
                formatter={(v) => `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, ' ')}
                suffix="₽"
                style={{ width: 160 }}
                disabled
              />
            </Form.Item>
            <Form.Item label="1% с превышения 300 000 ₽">
              <InputNumber
                defaultValue={1}
                suffix="%"
                style={{ width: 120 }}
                disabled
              />
            </Form.Item>
          </Space>

          <Divider />

          <Alert
            type="info"
            message="Ставки устанавливаются автоматически на основе НК РФ 2026"
            description="В будущих версиях можно будет настраивать региональные ставки УСН."
            showIcon
          />
        </Form>
      </Card>
    </div>
  );
}

/* ==================== Main Settings Page ==================== */
export default function SettingsPage() {
  return (
    <div>
      <Title level={3}>⚙️ Настройки</Title>

      <Card>
        <Tabs
          defaultActiveKey="profile"
          tabPosition="left"
          items={[
            {
              key: 'profile',
              label: (
                <span>
                  <UserOutlined /> Профиль
                </span>
              ),
              children: <ProfileTab />,
            },
            {
              key: 'bank',
              label: (
                <span>
                  <BankOutlined /> Банковские счета
                </span>
              ),
              children: <BankAccountsTab />,
            },
            {
              key: 'notifications',
              label: (
                <span>
                  <BellOutlined /> Уведомления
                </span>
              ),
              children: <NotificationsTab />,
            },
            {
              key: 'tax_rates',
              label: (
                <span>
                  <PercentageOutlined /> Ставки налогов
                </span>
              ),
              children: <TaxRatesTab />,
            },
          ]}
        />
      </Card>
    </div>
  );
}