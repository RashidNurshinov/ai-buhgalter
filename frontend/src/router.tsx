/**
 * React Router v6 — конфигурация маршрутов.
 * Пункт плана: 1.17.2
 */
import { createBrowserRouter, Navigate } from 'react-router-dom';
import { lazy, Suspense } from 'react';
import { Spin } from 'antd';
import AppLayout from '@/components/layout/AppLayout';
import ProtectedRoute from '@/components/auth/ProtectedRoute';

/* ----------- Lazy pages ----------- */
const LoginPage = lazy(() => import('@/pages/auth/LoginPage'));
const RegisterPage = lazy(() => import('@/pages/auth/RegisterPage'));
const DashboardPage = lazy(() => import('@/pages/DashboardPage'));
const UploadPage = lazy(() => import('@/pages/UploadPage'));
const DocumentsPage = lazy(() => import('@/pages/DocumentsPage'));
const OperationsPage = lazy(() => import('@/pages/OperationsPage'));
const KudirPage = lazy(() => import('@/pages/KudirPage'));
const CalendarPage = lazy(() => import('@/pages/CalendarPage'));
const TaxesPage = lazy(() => import('@/pages/TaxesPage'));
const DeclarationsPage = lazy(() => import('@/pages/DeclarationsPage'));
const AssistantPage = lazy(() => import('@/pages/AssistantPage'));
const BooksPage = lazy(() => import('@/pages/BooksPage'));
const SettingsPage = lazy(() => import('@/pages/SettingsPage'));
const NotFoundPage = lazy(() => import('@/pages/NotFoundPage'));

/* ----------- Fallback ----------- */
const PageLoader = (
  <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}>
    <Spin size="large" />
  </div>
);

function Lazy({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={PageLoader}>{children}</Suspense>;
}

/* ----------- Router ----------- */
const router = createBrowserRouter([
  /* Публичные маршруты */
  {
    path: '/auth/login',
    element: (
      <Lazy>
        <LoginPage />
      </Lazy>
    ),
  },
  {
    path: '/auth/register',
    element: (
      <Lazy>
        <RegisterPage />
      </Lazy>
    ),
  },

  /* Защищённые маршруты внутри MainLayout */
  {
    path: '/',
    element: (
      <ProtectedRoute>
        <AppLayout />
      </ProtectedRoute>
    ),
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      {
        path: 'dashboard',
        element: (
          <Lazy>
            <DashboardPage />
          </Lazy>
        ),
      },
      {
        path: 'upload',
        element: (
          <Lazy>
            <UploadPage />
          </Lazy>
        ),
      },
      {
        path: 'documents',
        element: (
          <Lazy>
            <DocumentsPage />
          </Lazy>
        ),
      },
      {
        path: 'operations',
        element: (
          <Lazy>
            <OperationsPage />
          </Lazy>
        ),
      },
      {
        path: 'kudir',
        element: (
          <Lazy>
            <KudirPage />
          </Lazy>
        ),
      },
      {
        path: 'calendar',
        element: (
          <Lazy>
            <CalendarPage />
          </Lazy>
        ),
      },
      {
        path: 'taxes',
        element: (
          <Lazy>
            <TaxesPage />
          </Lazy>
        ),
      },
      {
        path: 'declarations',
        element: (
          <Lazy>
            <DeclarationsPage />
          </Lazy>
        ),
      },
      {
        path: 'assistant',
        element: (
          <Lazy>
            <AssistantPage />
          </Lazy>
        ),
      },
      {
        path: 'books',
        element: (
          <Lazy>
            <BooksPage />
          </Lazy>
        ),
      },
      {
        path: 'settings',
        element: (
          <Lazy>
            <SettingsPage />
          </Lazy>
        ),
      },
    ],
  },

  /* 404 */
  {
    path: '*',
    element: (
      <Lazy>
        <NotFoundPage />
      </Lazy>
    ),
  },
]);

export default router;