/**
 * Боковая навигация с адаптивностью (Drawer на мобильных).
 * Пункт плана: 1.17.6, 1.17.7
 */
import { useMemo } from 'react';
import { Layout, Menu, Drawer } from 'antd';
import {
  DashboardOutlined,
  UploadOutlined,
  FileTextOutlined,
  SwapOutlined,
  CalendarOutlined,
  CalculatorOutlined,
  AuditOutlined,
  RobotOutlined,
  BookOutlined,
  ShoppingCartOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';
import useBreakpoint from '@/hooks/useBreakpoint';

const { Sider } = Layout;

interface Props {
  collapsed: boolean;
  mobileOpen: boolean;
  onMobileClose: () => void;
}

const menuItems = [
  {
    key: '/dashboard',
    icon: <DashboardOutlined />,
    label: 'Дашборд',
  },
  {
    key: '/upload',
    icon: <UploadOutlined />,
    label: 'Загрузка файлов',
  },
  {
    key: '/documents',
    icon: <FileTextOutlined />,
    label: 'Документы',
  },
  {
    key: '/operations',
    icon: <SwapOutlined />,
    label: 'Операции',
  },
  {
    key: '/kudir',
    icon: <BookOutlined />,
    label: 'КУДиР',
  },
  {
    key: '/calendar',
    icon: <CalendarOutlined />,
    label: 'Календарь',
  },
  {
    key: '/taxes',
    icon: <CalculatorOutlined />,
    label: 'Налоги',
  },
  {
    key: '/declarations',
    icon: <AuditOutlined />,
    label: 'Декларации',
  },
  {
    key: '/assistant',
    icon: <RobotOutlined />,
    label: 'ИИ-Ассистент',
  },
  { type: 'divider' as const },
  {
    key: '/books',
    icon: <ShoppingCartOutlined />,
    label: 'Книги покупок/продаж',
  },
  {
    key: '/settings',
    icon: <SettingOutlined />,
    label: 'Настройки',
  },
];

export default function AppSidebar({ collapsed, mobileOpen, onMobileClose }: Props) {
  const navigate = useNavigate();
  const location = useLocation();
  const { isMobile } = useBreakpoint();

  const selectedKeys = useMemo(() => {
    // Находим самый длинный совпадающий путь (пропускаем divider-ы)
    const matched = menuItems
      .filter((item): item is typeof item & { key: string } => 'key' in item && typeof item.key === 'string')
      .filter((item) => location.pathname.startsWith(item.key))
      .sort((a, b) => b.key.length - a.key.length);
    return matched.length > 0 ? [matched[0].key] : ['/'];
  }, [location.pathname]);

  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(key);
    if (isMobile) onMobileClose();
  };

  const menuContent = (
    <Menu
      theme="dark"
      mode="inline"
      selectedKeys={selectedKeys}
      items={menuItems}
      onClick={handleMenuClick}
    />
  );

  const logo = (
    <div
      style={{
        height: 64,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: '#fff',
        fontWeight: 700,
        fontSize: collapsed && !isMobile ? 16 : 18,
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        borderBottom: '1px solid rgba(255,255,255,0.1)',
      }}
    >
      {collapsed && !isMobile ? '💼' : '💼 ИИ-Бухгалтер'}
    </div>
  );

  // Мобильная версия — Drawer
  if (isMobile) {
    return (
      <Drawer
        placement="left"
        open={mobileOpen}
        onClose={onMobileClose}
        width={256}
        styles={{ body: { padding: 0, background: '#001529' } }}
        closable={false}
      >
        {logo}
        {menuContent}
      </Drawer>
    );
  }

  // Десктоп — фиксированный Sider
  return (
    <Sider
      trigger={null}
      collapsible
      collapsed={collapsed}
      width={240}
      style={{
        overflow: 'auto',
        height: '100vh',
        position: 'fixed',
        left: 0,
        top: 0,
        bottom: 0,
        zIndex: 100,
      }}
    >
      {logo}
      {menuContent}
    </Sider>
  );
}