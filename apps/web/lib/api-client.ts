/** Typed browser client for the Market Twin API. */

import { clearAuthSession, getStoredToken } from "@/lib/auth-session";
import production from "@/deployment/production.json";

export function getApiBaseUrl(): string {
  return (process.env.NEXT_PUBLIC_API_URL || production.apiOrigin).replace(
    /\/$/,
    "",
  );
}

export const API_BASE_URL = getApiBaseUrl();

function requestHeaders(authenticated = true): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Request-ID":
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `${Date.now()}-${Math.random()}`,
  };
  if (authenticated) {
    const token = getStoredToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

async function responseError(resp: Response, action: string): Promise<Error> {
  let detail = resp.statusText || "请求失败";
  try {
    const payload = await resp.json();
    detail = payload.detail || detail;
  } catch {
    // Keep the HTTP status text when the body is not JSON.
  }
  if (resp.status === 401) clearAuthSession();
  return new Error(`${action}：${detail}`);
}

async function apiJson<T>(
  path: string,
  init: RequestInit = {},
  authenticated = true,
): Promise<T> {
  const baseUrl = getApiBaseUrl();
  const resp = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers: {
      ...requestHeaders(authenticated),
      ...(init.headers || {}),
    },
  });
  if (!resp.ok) throw await responseError(resp, "请求失败");
  return resp.json() as Promise<T>;
}

export interface UserProfile {
  id: string;
  email: string;
  name?: string;
  company?: string;
  plan_tier: string;
  credits_balance: number;
  free_preview_runs_balance: number;
  basic_decision_runs_balance: number;
  deep_decision_runs_balance: number;
  invite_status?: "VALID" | "INVALID" | "NOT_PROVIDED";
  invite_code?: string | null;
  acquisition_source?: string;
  invite_owner?: string | null;
  invite_commission_percent?: number;
  is_admin?: boolean;
}

export interface AuthConfig {
  email_verification_required: boolean;
  turnstile_site_key?: string | null;
}

export interface RegistrationPayload {
  email: string;
  password: string;
  name?: string;
  company?: string;
  invite_code?: string;
}

export interface StudyListItem {
  id: string;
  name: string;
  study_type: string;
  status: string;
  plan_code: string;
  category?: string;
  created_at: string;
  updated_at: string;
}

export interface StudyDetail extends StudyListItem {
  inputs: Record<string, unknown>;
  facts: Record<string, unknown>;
}

export interface CreateStudyPayload {
  name: string;
  study_type: string;
  language?: string;
  plan_code?: string;
  template_key?: string;
  product_name?: string;
  product_image_data_url?: string;
  category?: string;
  price?: number;
  reference_price?: number;
  variable_cost?: number;
  url?: string;
  research_urls?: string[];
  description?: string;
  selling_points?: string[];
  competitors?: string[];
  competitor_data?: Array<Record<string, unknown>>;
  observed_choice_data?: Array<Record<string, unknown>>;
  venue_history?: Array<Record<string, unknown>>;
  business_questions?: string[];
  venue_type?: string;
  average_check?: number;
  capacity?: number;
  opening_hours?: string;
  creative_format?: string;
  channel?: string;
  location?: Record<string, unknown>;
  candidate_locations?: Array<Record<string, unknown>>;
  scenarios?: Array<Record<string, unknown>>;
  marketplaces?: string[];
  shipping_fee?: number;
  delivery_days?: number;
  cod_available?: boolean;
  official_store?: boolean;
}

export interface RunSimulationPayload {
  study_id: string;
  plan_code?: string;
  population_size?: number;
  mc_rounds?: number;
  seed?: number;
  idempotency_key?: string;
}

export interface SimulationRunStatus {
  run_job_id: string;
  study_id: string;
  status: "PENDING" | "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED";
  stage: string;
  stage_label: string;
  progress_percent: number;
  plan_code: string;
  calibration_tier:
    | "PUBLIC_EVIDENCE"
    | "PLATFORM_CATEGORY_BENCHMARK"
    | "CUSTOMER_OBSERVED_CHOICE";
  report_id?: string | null;
  error_code?: string | null;
  can_close_page: boolean;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface BillingPackage {
  code: string;
  name: string;
  credits: number;
  bonus_credits: number;
  run_entitlements: Record<string, number>;
  amount_minor: number;
  currency: string;
  description: string;
}

export interface PaymentMethod {
  code: "ALIPAY" | "WECHAT_PAY" | "WECHAT_APPRECIATION";
  name: string;
  image_url: string;
  package_codes: string[];
}

export interface PurchaseOrder {
  id: string;
  package_code: string;
  credits: number;
  bonus_credits: number;
  run_entitlements: Record<string, number>;
  amount_minor: number;
  currency: string;
  status: string;
  payment_method?: PaymentMethod["code"] | null;
  payer_name?: string | null;
  payment_claim_reference?: string | null;
  payment_time_text?: string | null;
  payment_claim_note?: string | null;
  payment_claimed_at?: string | null;
  payment_reference?: string | null;
  reviewed_at?: string | null;
  review_note?: string | null;
  allowed_payment_methods: PaymentMethod[];
  created_at: string;
  updated_at: string;
  next_step?: string;
}

export interface AdminDashboard {
  overview: {
    total_users: number;
    total_orders: number;
    pending_orders: number;
    paid_orders: number;
    paid_revenue_minor: number;
    total_runs: number;
    completed_runs: number;
    failed_runs: number;
    active_runs: number;
    active_invite_codes: number;
    calibration_contributions: number;
  };
  calibration_benchmarks: {
    total_contributions: number;
    privacy_status: string;
    cohorts: Array<{
      category_key: string;
      study_type: string;
      contribution_count: number;
      choice_set_count: number;
    }>;
  };
  users: Array<UserProfile & {
    created_at: string;
    order_count: number;
    paid_total_minor: number;
    referral_commission_minor: number;
  }>;
  orders: Array<PurchaseOrder & {
    user_email: string;
    user_name?: string;
    company?: string;
    invite_code?: string | null;
    invite_owner?: string | null;
    referral_commission_minor: number;
  }>;
  invite_codes: Array<{
    id: string;
    code: string;
    source_name: string;
    owner_name: string;
    owner_contact?: string | null;
    commission_percent: number;
    bonus_credits: number;
    notes?: string | null;
    active: boolean;
    registrations: number;
    paid_revenue_minor: number;
    commission_due_minor: number;
    created_at: string;
    updated_at: string;
  }>;
  audit_logs: Array<{
    id: string;
    actor_email: string;
    action: string;
    target_type: string;
    target_id: string;
    details: Record<string, unknown>;
    created_at: string;
  }>;
}

export async function registerApi(payload: RegistrationPayload) {
  return apiJson<{ access_token: string; user: UserProfile }>(
    "/v1/auth/register",
    { method: "POST", body: JSON.stringify(payload) },
    false,
  );
}

export async function getAuthConfigApi() {
  return apiJson<AuthConfig>("/v1/auth/config", {}, false);
}

export async function startRegistrationVerificationApi(
  payload: RegistrationPayload & { turnstile_token: string },
) {
  return apiJson<{
    challenge_id: string;
    email: string;
    expires_in_seconds: number;
    attempts_remaining: number;
  }>(
    "/v1/auth/register/verification/start",
    { method: "POST", body: JSON.stringify(payload) },
    false,
  );
}

export async function completeRegistrationVerificationApi(payload: {
  challenge_id: string;
  code: string;
}) {
  return apiJson<{ access_token: string; user: UserProfile }>(
    "/v1/auth/register/verification/complete",
    { method: "POST", body: JSON.stringify(payload) },
    false,
  );
}

export async function loginApi(payload: { email: string; password: string }) {
  return apiJson<{ access_token: string; user: UserProfile }>(
    "/v1/auth/login",
    { method: "POST", body: JSON.stringify(payload) },
    false,
  );
}

export async function getMeApi() {
  return apiJson<UserProfile>("/v1/auth/me");
}

export async function getCatalogApi() {
  return apiJson<{
    packages: BillingPackage[];
    credit_pricing: Record<string, number>;
    self_service_plans: string[];
    assisted_plans: string[];
    manual_payment: {
      enabled: boolean;
      automatic_callback: boolean;
      methods: PaymentMethod[];
      notice: string;
    };
  }>("/v1/catalog", {}, false);
}

export async function createStudyApi(payload: CreateStudyPayload) {
  return apiJson<StudyDetail>("/v1/studies", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listStudiesApi() {
  return apiJson<StudyListItem[]>("/v1/studies");
}

export async function confirmStudyApi(
  studyId: string,
  overrides: Record<string, unknown> = {},
) {
  return apiJson<StudyDetail>(`/v1/studies/${studyId}/confirm`, {
    method: "POST",
    body: JSON.stringify({ overrides }),
  });
}

export async function runSimulationApi(payload: RunSimulationPayload) {
  return apiJson<{ report_id?: string; run_job_id?: string } & Partial<SimulationRunStatus>>(
    `/v1/studies/${payload.study_id}/runs`,
    { method: "POST", body: JSON.stringify(payload) },
  );
}

export async function getRunStatusApi(runJobId: string) {
  return apiJson<SimulationRunStatus>(
    `/v1/runs/${encodeURIComponent(runJobId)}`,
  );
}

export async function getReportApi<T = Record<string, unknown>>(reportId: string) {
  return apiJson<T>(`/v1/reports/${reportId}`);
}

export async function getStudyApi(studyId: string) {
  return apiJson<StudyDetail>(`/v1/studies/${studyId}`);
}

export async function getTransactionsApi() {
  return apiJson<
    Array<{
      id: string;
      amount: number;
      type: string;
      description?: string;
      balance_after?: number;
      created_at: string;
    }>
  >("/v1/billing/transactions");
}

export async function getEntitlementTransactionsApi() {
  return apiJson<
    Array<{
      id: string;
      plan_code: string;
      amount: number;
      type: string;
      description?: string;
      balance_after: number;
      created_at: string;
    }>
  >("/v1/billing/entitlement-transactions");
}

export async function getOrdersApi() {
  return apiJson<PurchaseOrder[]>("/v1/billing/orders");
}

export async function createOrderApi(packageCode: string) {
  return apiJson<PurchaseOrder>("/v1/billing/orders", {
    method: "POST",
    body: JSON.stringify({ package_code: packageCode }),
  });
}

export async function submitPaymentClaimApi(
  orderId: string,
  payload: {
    payment_method: PaymentMethod["code"];
    payer_name?: string;
    payment_claim_reference?: string;
    payment_time_text?: string;
    note?: string;
  },
) {
  return apiJson<PurchaseOrder>(
    `/v1/billing/orders/${encodeURIComponent(orderId)}/payment-claim`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export async function getAdminDashboardApi() {
  return apiJson<AdminDashboard>("/v1/admin/dashboard");
}

export async function completeAdminOrderApi(
  orderId: string,
  paymentReference: string,
) {
  return apiJson<PurchaseOrder>(
    `/v1/admin/billing/orders/${encodeURIComponent(orderId)}/complete`,
    {
      method: "POST",
      body: JSON.stringify({ payment_reference: paymentReference }),
    },
  );
}

export async function rejectAdminOrderPaymentApi(
  orderId: string,
  note: string,
) {
  return apiJson<PurchaseOrder>(
    `/v1/admin/billing/orders/${encodeURIComponent(orderId)}/reject`,
    {
      method: "POST",
      body: JSON.stringify({ note }),
    },
  );
}

export async function createAdminInviteCodeApi(payload: {
  code: string;
  source_name: string;
  owner_name: string;
  owner_contact?: string;
  commission_percent: number;
  bonus_credits: number;
  notes?: string;
}) {
  return apiJson<AdminDashboard["invite_codes"][number]>(
    "/v1/admin/invite-codes",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export async function deactivateAdminInviteCodeApi(code: string) {
  return apiJson<{ code: string; active: boolean; message: string }>(
    `/v1/admin/invite-codes/${encodeURIComponent(code)}`,
    { method: "DELETE" },
  );
}
