/**
 * Верхний хедер — переключение сайдбара, уведомления, профиль.
 * Пункт плана: 1.17.6
 */
import { Layout, Button, Dropdown, Space, Avatar, Badge, Typography } from 'antd';
import {
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  MenuOutlined,
  BellOutlined,
  UserOutlined,
  LogoutOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import useBreakpoint from '@/hooks/useBreakpoint';
import type { MenuProps } from 'antd';

const { Header } = Layout;
const { Text } = Typography;

interface Props {
  collapsed: boolean;
  onToggleCollapse: () => void;
  onMobileMenuOpen: () => void;
}

export default function AppHeader({
  collapsed,
  onToggleCollapse,
  onMobileMenuOpen,
}: Props) {
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();
  const { isMobile } = useBreakpoint();

  const handleLogout = () => {
    logout();
    navigate('/auth/login');
  };

  const profileMenuItems: MenuProps['items'] = [
    {
      key: 'profile',
      icon: <SettingOutlined />,
      label: 'Настройки профиля',
      onClick: () => navigate('/settings'),
    },
    {
      type: 'divider',
    },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: 'Выйти',
      danger: true,
      onClick: handleLogout,
    },
  ];

  return (
    <Header
      style={{
        padding: '0 24px',
        background: '#fff',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        borderBottom: '1px solid #f0f0f0',
        position: 'sticky',
        top: 0,
        zIndex: 99,
        boxShadow: '0 1px 4px rgba(0,0,0,0.05)',
      }}
    >
      {/* Левая часть: кнопка меню */}
      <div>
        {isMobile ? (
          <Button
            type="text"
            icon={<MenuOutlined />}
            onClick={onMobileMenuOpen}
            style={{ fontSize: 18 }}
          />
        ) : (
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={onToggleCollapse}
            style={{ fontSize: 18 }}
          />
        )}
      </div>

      {/* Правая часть: уведомления + профиль */}
      <Space size="middle">
        <Badge count={0} size="small">
          <Button
            type="text"
            icon={<BellOutlined />}
            style={{ fontSize: 18 }}
            onClick={() => navigate('/calendar')}
          />
        </Badge>

        <Dropdown menu={{ items: profileMenuItems }} placement="bottomRight">
          <Space style={{ cursor: 'pointer' }}>
            <Avatar size="small" icon={<UserOutlined />} />
            {!isMobile && (
              <Text style={{ maxWidth: 150 }} ellipsis>
                {user?.full_name || user?.email || 'Пользователь'}
              </Text>
            )}
          </Space>
        </Dropdown>
      </Space>
    </Header>
  );
}