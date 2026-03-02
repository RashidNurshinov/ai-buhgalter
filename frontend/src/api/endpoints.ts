/**
 * API-эндпоинты — функции-обёртки над apiClient.
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
  UploadedFile,
  AgentChatRequest,
  AgentChatResponse,
  AgentConfirmation,
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
  getEvents: (params?: { year?: number; status?: string }) =>
    apiClient.get<CalendarEvent[]>('/calendar/', { params }),

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

  confirm: (id: string) =>
    apiClient.put(`/documents/${id}/confirm`),
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

  confirm: (id: string) =>
    apiClient.put(`/operations/${id}/confirm`),

  reclassify: (id: string, category: string) =>
    apiClient.put(`/operations/${id}/reclassify`, { category }),

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
  chat: (data: AgentChatRequest) =>
    apiClient.post<AgentChatResponse>('/agent/chat', data),

  command: (data: { command: string; params?: Record<string, unknown> }) =>
    apiClient.post<AgentChatResponse>('/agent/command', data),

  confirm: (confirmationId: string, approved: boolean) =>
    apiClient.post(`/agent/confirm`, {
      confirmation_id: confirmationId,
      approved,
    }),

  getEvents: (params?: { limit?: number; offset?: number }) =>
    apiClient.get('/agent/events', { params }),

  getEvent: (id: string) => apiClient.get(`/agent/events/${id}`),

  getConfirmations: () =>
    apiClient.get<AgentConfirmation[]>('/agent/confirmations'),

  getStats: () => apiClient.get('/agent/stats'),
};