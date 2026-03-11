/**
 * API-эндпоинты — функции-обёртки над apiClient.
 *
 * ВАЖНО: Все типы и имена полей синхронизированы с backend Pydantic-схемами.
 * При изменении backend-схем — обновить соответствующие типы в @/types/index.ts
 */
import apiClient from './client';
import type {
  LoginRequest,
  RegisterRequest,
  TokenResponse,
  User,
  UserUpdate,
  DashboardResponse,
  CalendarEvent,
  CalendarListResponse,
  UploadedFile,
  AgentChatRequest,
  AgentChatResponse,
  AgentConfirmation,
  AgentConfirmRequest,
} from '@/types';

// ==================== Auth ====================

export const authApi = {
  login: (data: LoginRequest) =>
    apiClient.post<TokenResponse>('/auth/login', data),

  register: (data: RegisterRequest) =>
    apiClient.post<TokenResponse>('/auth/register', data),

  refresh: (refreshToken: string) =>
    apiClient.post<TokenResponse>('/auth/refresh', {
      refresh_token: refreshToken,
    }),
};

// ==================== User ====================

export const userApi = {
  getMe: () => apiClient.get<User>('/users/me'),

  updateMe: (data: UserUpdate) =>
    apiClient.put<User>('/users/me', data),
};

// ==================== Dashboard ====================

export const dashboardApi = {
  get: (params?: {
    period_start?: string;
    period_end?: string;
    include_monthly?: boolean;
  }) => apiClient.get<DashboardResponse>('/dashboard/', { params }),
};

// ==================== Calendar ====================

export const calendarApi = {
  /**
   * Список событий с фильтрацией.
   * Backend возвращает CalendarListResponse (events + counts), а НЕ массив.
   */
  getEvents: (params?: { year?: number; status?: string; type?: string }) =>
    apiClient.get<CalendarListResponse>('/calendar/', { params }),

  getUpcoming: (days?: number) =>
    apiClient.get<CalendarEvent[]>('/calendar/upcoming', {
      params: { days },
    }),

  getOverdue: () => apiClient.get<CalendarEvent[]>('/calendar/overdue'),

  complete: (id: string) =>
    apiClient.post<CalendarEvent>(`/calendar/${id}/complete`),

  populate: (year?: number) =>
    apiClient.post('/calendar/populate', null, { params: { year } }),
};

// ==================== Files ====================

export const filesApi = {
  upload: (files: File[]) => {
    const formData = new FormData();
    files.forEach((file) => formData.append('files', file));
    return apiClient.post<UploadedFile[]>('/files/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  list: () => apiClient.get<UploadedFile[]>('/files/'),

  get: (id: string) => apiClient.get<UploadedFile>(`/files/${id}`),

  delete: (id: string) => apiClient.delete(`/files/${id}`),

  reprocess: (id: string) => apiClient.post(`/files/${id}/reprocess`),
};

// ==================== Documents ====================

export const documentsApi = {
  list: (params?: {
    page?: number;
    per_page?: number;
    doc_type?: string;
    status?: string;
  }) => apiClient.get('/documents/', { params }),

  get: (id: string) => apiClient.get(`/documents/${id}`),

  /**
   * Подтвердить документ.
   * Backend: POST /documents/{id}/confirm (НЕ PUT!)
   */
  confirm: (id: string) =>
    apiClient.post(`/documents/${id}/confirm`),

  /**
   * Отклонить документ.
   * Backend: POST /documents/{id}/reject
   */
  reject: (id: string) =>
    apiClient.post(`/documents/${id}/reject`),
};

// ==================== Operations ====================

export const operationsApi = {
  list: (params?: {
    page?: number;
    per_page?: number;
    status?: string;
    is_income?: boolean;
  }) => apiClient.get('/operations/', { params }),

  get: (id: string) => apiClient.get(`/operations/${id}`),

  /**
   * Подтвердить операцию.
   * Backend: POST /operations/{id}/confirm (НЕ PUT!)
   */
  confirm: (id: string) =>
    apiClient.post(`/operations/${id}/confirm`),

  reclassify: (id: string, category: string) =>
    apiClient.post(`/operations/${id}/reclassify`, { category }),

  unconfirmed: () => apiClient.get('/operations/unconfirmed'),
};

// ==================== KUDiR ====================

export const kudirApi = {
  getEntries: (params: { year: number; quarter?: number }) =>
    apiClient.get('/kudir/', { params }),

  generate: (params: { year: number; quarter: number }) =>
    apiClient.post('/kudir/generate', null, { params }),
};

// ==================== Purchase / Sales Book ====================

export const booksApi = {
  getPurchaseBook: (params: { year: number; quarter: number }) =>
    apiClient.get('/purchase-book/', { params }),

  generatePurchaseBook: (params: { year: number; quarter: number }) =>
    apiClient.post('/purchase-book/generate', null, { params }),

  getSalesBook: (params: { year: number; quarter: number }) =>
    apiClient.get('/sales-book/', { params }),

  generateSalesBook: (params: { year: number; quarter: number }) =>
    apiClient.post('/sales-book/generate', null, { params }),
};

// ==================== Taxes ====================

export const taxesApi = {
  calculate: (period: string) =>
    apiClient.get('/taxes/calculate', { params: { period } }),

  summary: (year: number) =>
    apiClient.get('/taxes/summary', { params: { year } }),

  history: () => apiClient.get('/taxes/history'),
};

// ==================== Declarations ====================

export const declarationsApi = {
  list: () => apiClient.get('/declarations/'),

  get: (id: string) => apiClient.get(`/declarations/${id}`),

  generate: (data: {
    declaration_type: string;
    year: number;
    quarter?: number;
  }) => apiClient.post('/declarations/generate', data),

  getXml: (id: string) => apiClient.get(`/declarations/${id}/xml`),

  validate: (id: string) =>
    apiClient.post(`/declarations/${id}/validate`),
};

// ==================== Agent ====================

export const agentApi = {
  /**
   * Отправить сообщение в чат с AI-агентом.
   * Backend: POST /agent/chat → AgentChatResponse
   */
  chat: (data: AgentChatRequest) =>
    apiClient.post<AgentChatResponse>('/agent/chat', data),

  /**
   * Отправить прямую команду AI-агенту.
   * Backend: POST /agent/command → AgentChatResponse
   */
  command: (data: { command: string }) =>
    apiClient.post<AgentChatResponse>('/agent/command', data),

  /**
   * Ответить на запрос подтверждения от агента.
   * Backend: POST /agent/confirm → AgentChatResponse
   *
   * ИСПРАВЛЕНО: Backend ожидает { confirmation_id, action, user_response?, modified_data? }
   * а НЕ { confirmation_id, approved }.
   */
  confirm: (data: AgentConfirmRequest) =>
    apiClient.post<AgentChatResponse>('/agent/confirm', data),

  /**
   * Список событий агента.
   * Backend: GET /agent/events → AgentEventOut[]
   */
  getEvents: (params?: { limit?: number; offset?: number }) =>
    apiClient.get('/agent/events', { params }),

  /**
   * История сообщений чата.
   * Backend: GET /agent/messages → Array<{id, role, content, created_at}>
   */
  getMessages: (params?: { limit?: number }) =>
    apiClient.get('/agent/messages', { params }),

  /**
   * Детали события с логом действий.
   * Backend: GET /agent/events/{id} → AgentEventDetailOut
   */
  getEvent: (id: string) => apiClient.get(`/agent/events/${id}`),

  /**
   * Список ожидающих подтверждений.
   * Backend: GET /agent/confirmations → AgentConfirmationOut[]
   */
  getConfirmations: () =>
    apiClient.get<AgentConfirmation[]>('/agent/confirmations'),

  /**
   * Статистика AI-агента.
   * Backend: GET /agent/stats → AgentStatsOut
   */
  getStats: (days?: number) =>
    apiClient.get('/agent/stats', { params: days ? { days } : undefined }),
};