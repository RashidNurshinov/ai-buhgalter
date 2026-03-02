/**
 * Страница авторизации.
 */
import { useState } from 'react';
import { Card, Form, Input, Button, Typography, Alert, Space } from 'antd';
import { MailOutlined, LockOutlined } from '@ant-design/icons';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';

const { Title, Text } = Typography;

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, isLoading, error, clearError } = useAuthStore();
  const [form] = Form.useForm();

  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/';

  const [localError, setLocalError] = useState<string | null>(null);

  const handleSubmit = async (values: { email: string; password: string }) => {
    setLocalError(null);
    clearError();
    try {
      await login(values.email, values.password);
      navigate(from, { replace: true });
    } catch {
      // Ошибка уже обрабатывается стором
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        padding: 16,
      }}
    >
      <Card
        style={{ width: '100%', maxWidth: 420 }}
        styles={{ body: { padding: 32 } }}
      >
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <Title level={3} style={{ marginBottom: 4 }}>
            💼 ИИ-Бухгалтер
          </Title>
          <Text type="secondary">Войдите в систему</Text>
        </div>

        {(error || localError) && (
          <Alert
            type="error"
            message={error || localError}
            showIcon
            closable
            onClose={() => {
              clearError();
              setLocalError(null);
            }}
            style={{ marginBottom: 16 }}
          />
        )}

        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
          autoComplete="off"
          size="large"
        >
          <Form.Item
            name="email"
            rules={[
              { required: true, message: 'Введите email' },
              { type: 'email', message: 'Некорректный email' },
            ]}
          >
            <Input prefix={<MailOutlined />} placeholder="Email" />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[{ required: true, message: 'Введите пароль' }]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="Пароль" />
          </Form.Item>

          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              loading={isLoading}
              block
            >
              Войти
            </Button>
          </Form.Item>
        </Form>

        <Space
          direction="vertical"
          style={{ width: '100%', textAlign: 'center' }}
        >
          <Text>
            Нет аккаунта?{' '}
            <Link to="/auth/register">Зарегистрируйтесь</Link>
          </Text>
        </Space>
      </Card>
    </div>
  );
}