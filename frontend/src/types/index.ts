/**
 * Общие типы проекта ИИ-Бухгалтер.
 * Соответствуют Pydantic-схемам backend.
 */

// ==================== Auth ====================

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  full_name: string;
  inn?: string;
  business_name?: string;
  tax_system?: TaxSystem;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

// ==================== Enums ====================

export type TaxSystem =
  | 'usn_income'
  | 'usn_income_expense'
  | 'osno'
  | 'patent'
  | 'eshn'
  | 'auto';

export type DocumentType =
  | 'invoice'
  | 'act'
  | 'upd'
  | 'torg12'
  | 'bank_statement'
  | 'cash_receipt'
  | 'contract'
  | 'unknown';

export type DocumentStatus =
  | 'uploaded'
  | 'processing'
  | 'recognized'
  | 'confirmed'
  | 'error';

export type OperationStatus =
  | 'new'
  | 'classified'
  | 'confirmed'
  | 'rejected';

export type CalendarEventStatus =
  | 'upcoming'
  | 'overdue'
  | 'completed';

export type CalendarEventType =
  | 'tax_payment'
  | 'declaration_submit'
  | 'advance_payment'
  | 'contribution_payment'
  | 'report_submit';

export type DeclarationStatus =
  | 'draft'
  | 'generated'
  | 'validated'
  | 'submitted'
  | 'accepted'
  | 'rejected';

// ==================== User ====================

export interface User {
  id: string;
  email: string;
  full_name: string;
  inn: string | null;
  business_name: string | null;
  tax_system: TaxSystem;
  is_active: boolean;
  tax_region: string;
  usn_rate: number;
  vat_rate: number;
  has_employees: boolean;
  employee_count: number;
  created_at: string;
}

export interface UserUpdate {
  full_name?: string;
  inn?: string;
  business_name?: string;
  tax_system?: TaxSystem;
  tax_region?: string;
  usn_rate?: number;
  vat_rate?: number;
  has_employees?: boolean;
  employee_count?: number;
}

// ==================== Dashboard ====================

export interface DashboardResponse {
  period_start: string;
  period_end: string;
  total_income: number;
  total_expense: number;
  net_profit: number;
  estimated_usn: number;
  estimated_vat: number;
  unconfirmed_operations: number;
  unprocessed_documents: number;
  upcoming_events: number;
  overdue_events: number;
  monthly_breakdown: MonthlyAmount[] | null;
}

export interface MonthlyAmount {
  month: string;
  income: number;
  expense: number;
}

// ==================== Calendar ====================

export interface CalendarEvent {
  id: string;
  user_id: string;
  event_type: CalendarEventType;
  title: string;
  description: string | null;
  deadline: string;
  status: CalendarEventStatus;
  reminded_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface CalendarListResponse {
  events: CalendarEvent[];
  upcoming_count: number;
  overdue_count: number;
}

// ==================== Documents ====================

export interface Document {
  id: string;
  user_id: string;
  doc_type: DocumentType;
  doc_number: string | null;
  doc_date: string | null;
  counterparty_name: string | null;
  counterparty_inn: string | null;
  total_without_vat: number | null;
  vat_amount: number | null;
  total_with_vat: number | null;
  status: DocumentStatus;
  confidence_score: number | null;
  created_at: string;
}

// ==================== Operations ====================

export interface BankOperation {
  id: string;
  user_id: string;
  operation_date: string;
  amount: number;
  counterparty_name: string | null;
  counterparty_inn: string | null;
  purpose: string | null;
  category: string | null;
  is_income: boolean;
  is_expense: boolean;
  vat_amount: number | null;
  status: OperationStatus;
  classification_confidence: number | null;
  created_at: string;
}

// ==================== KUDiR ====================

export interface KudirEntry {
  id: string;
  entry_date: string;
  document_ref: string | null;
  description: string;
  income_amount: number;
  expense_amount: number;
  quarter: number;
  year: number;
}

export interface KudirTotals {
  total_income: number;
  total_expense: number;
  net: number;
}

// ==================== Taxes ====================

export interface TaxCalculation {
  id: string;
  tax_type: string;
  period_type: string;
  period_start: string;
  period_end: string;
  income_total: number;
  expense_total: number;
  tax_base: number;
  tax_rate: number;
  tax_amount: number;
  vat_charged: number | null;
  vat_deductible: number | null;
  vat_payable: number | null;
  status: string;
  created_at: string;
}

// ==================== Declarations ====================

export interface Declaration {
  id: string;
  declaration_type: string;
  period: string;
  year: number;
  status: DeclarationStatus;
  xml_content: string | null;
  validation_result: ValidationResult | null;
  created_at: string;
}

export interface ValidationResult {
  is_valid: boolean;
  xsd_valid: boolean;
  control_ratios_valid: boolean;
  errors: string[];
  warnings: string[];
}

// ==================== Agent / Chat ====================

export interface AgentChatRequest {
  message: string;
  context?: Record<string, unknown>;
}

export interface AgentChatResponse {
  event_id: string;
  response: string;
  actions_taken: AgentAction[];
  confirmations_requested: AgentConfirmation[];
}

export interface AgentAction {
  id: string;
  action_type: string;
  tool_name: string | null;
  tool_input: Record<string, unknown> | null;
  tool_output: Record<string, unknown> | null;
  status: string;
  created_at: string;
}

export interface AgentConfirmation {
  id: string;
  question: string;
  context: Record<string, unknown> | null;
  status: string;
  user_response: boolean | null;
  created_at: string;
}

// ==================== Files ====================

export interface UploadedFile {
  id: string;
  original_filename: string;
  file_type: string;
  file_size: number;
  processing_status: string;
  processing_result: Record<string, unknown> | null;
  created_at: string;
}

// ==================== Pagination ====================

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

// ==================== API Errors ====================

export interface ApiError {
  detail: string;
  status_code?: number;
}