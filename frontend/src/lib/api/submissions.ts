import apiClient from "./client";
import type {
  AuditLogEntry,
  WeeklyPeriod,
  WeeklySubmission,
  SubmissionAnswer,
  QismExtension,
} from "@/types/submissions";
import type { ApiResponse } from "@/types/api";

// --- التقديمات الأسبوعية ---

export async function getSubmissions(params?: Record<string, string>): Promise<ApiResponse<WeeklySubmission>> {
  const { data } = await apiClient.get<ApiResponse<WeeklySubmission>>("/submissions/", { params });
  return data;
}

export async function getSubmission(id: number): Promise<WeeklySubmission> {
  const { data } = await apiClient.get<WeeklySubmission>(`/submissions/${id}/`);
  return data;
}

export async function createSubmission(periodId: number): Promise<WeeklySubmission> {
  const { data } = await apiClient.post<WeeklySubmission>("/submissions/", {
    weekly_period: periodId,
  });
  return data;
}

export interface AnswerInput {
  form_item: number;
  numeric_value?: number | null;
  text_value?: string;
  is_qualitative?: boolean;
  qualitative_details?: string;
}

export async function updateSubmission(
  id: number,
  submissionData: {
    answers?: AnswerInput[];
    notes?: string;
  }
): Promise<WeeklySubmission> {
  const { data } = await apiClient.patch<WeeklySubmission>(`/submissions/${id}/`, submissionData);
  return data;
}

export async function submitSubmission(id: number): Promise<WeeklySubmission> {
  const { data } = await apiClient.post<WeeklySubmission>(`/submissions/${id}/submit/`);
  return data;
}

export async function approveSubmission(id: number): Promise<WeeklySubmission> {
  const { data } = await apiClient.post<WeeklySubmission>(`/submissions/${id}/approve/`);
  return data;
}

export async function getSubmissionHistory(id: number): Promise<WeeklySubmission[]> {
  const { data } = await apiClient.get<WeeklySubmission[]>(`/submissions/${id}/history/`);
  return data;
}

// ═══════════════════════════════════════════════
// مراجعة الإحصاء (Admin Review) — الطبقة الثالثة
// ═══════════════════════════════════════════════

/**
 * فلاتر قائمة المنجزات بانتظار مراجعة الإحصاء.
 * - `reviewed`: "true" تُرجع المراجَعة، "false" تُرجع غير المراجَعة، أو تُحذف لإرجاع الكل.
 */
export interface PendingAdminReviewFilters {
  reviewed?: "true" | "false";
  week?: string;
  year?: string;
  daira_id?: string;
  mudiriya_id?: string;
  qism_id?: string;
  page?: string;
  page_size?: string;
}

export async function getPendingAdminReview(
  filters: PendingAdminReviewFilters = {}
): Promise<ApiResponse<WeeklySubmission>> {
  const params: Record<string, string> = {};
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      params[key] = value;
    }
  });
  const { data } = await apiClient.get<ApiResponse<WeeklySubmission>>(
    "/submissions/pending-admin-review/",
    { params }
  );
  return data;
}

export async function adminApproveSubmission(id: number): Promise<WeeklySubmission> {
  const { data } = await apiClient.post<WeeklySubmission>(
    `/submissions/${id}/admin-approve/`
  );
  return data;
}

export interface AdminAnswerEdit {
  answer_id: number;
  numeric_value?: number | null;
  text_value?: string;
}

export async function adminEditSubmission(
  id: number,
  payload: { reason: string; answer_edits: AdminAnswerEdit[] }
): Promise<WeeklySubmission> {
  const { data } = await apiClient.post<WeeklySubmission>(
    `/submissions/${id}/admin-edit/`,
    payload
  );
  return data;
}

export async function adminReturnSubmission(
  id: number,
  reason: string
): Promise<WeeklySubmission> {
  const { data } = await apiClient.post<WeeklySubmission>(
    `/submissions/${id}/admin-return/`,
    { reason }
  );
  return data;
}

export async function getSubmissionAuditLog(
  id: number
): Promise<{ results: AuditLogEntry[] }> {
  const { data } = await apiClient.get<{ results: AuditLogEntry[] }>(
    `/submissions/${id}/audit-log/`
  );
  return data;
}

/**
 * عدد المنجزات المعتمَدة من التخطيط وبانتظار مراجعة الإحصاء — للـ sidebar badge.
 * نستخدم `page_size=1` لتقليل حجم الاستجابة؛ المعلومة المطلوبة في `count` فقط.
 */
export async function getPendingAdminReviewCount(): Promise<number> {
  const { data } = await apiClient.get<ApiResponse<WeeklySubmission>>(
    "/submissions/pending-admin-review/",
    { params: { reviewed: "false", page_size: "1" } }
  );
  return data.count;
}

// --- الفترات الأسبوعية ---

export async function getPeriods(params?: Record<string, string>): Promise<ApiResponse<WeeklyPeriod>> {
  const { data } = await apiClient.get<ApiResponse<WeeklyPeriod>>("/periods/", { params });
  return data;
}

export async function getPeriod(id: number): Promise<WeeklyPeriod> {
  const { data } = await apiClient.get<WeeklyPeriod>(`/periods/${id}/`);
  return data;
}

export async function createPeriod(periodData: {
  year: number;
  week_number: number;
  start_date: string;
  end_date: string;
  deadline: string;
}): Promise<WeeklyPeriod> {
  const { data } = await apiClient.post<WeeklyPeriod>("/periods/", periodData);
  return data;
}

export async function closePeriod(id: number): Promise<WeeklyPeriod> {
  const { data } = await apiClient.post<WeeklyPeriod>(`/periods/${id}/close/`);
  return data;
}

// --- الالتزام ---

export interface ComplianceData {
  total_sections: number;
  submitted: number;
  late: number;
  draft: number;
  sections: {
    qism_id: number;
    qism_name: string;
    status: string;
  }[];
}

export async function getCompliance(periodId: number): Promise<ComplianceData> {
  const { data } = await apiClient.get<ComplianceData>(`/periods/${periodId}/compliance/`);
  return data;
}

// ── تفصيل مُجمّع لنطاق ضمن فترة ──

export interface PeriodScopeUnit {
  id: number | null;
  name: string;
  unit_type: "institution" | "daira" | "mudiriya" | "qism";
  code: string | null;
}

export interface AggregatedIndicator {
  indicator_id: number;
  indicator_name: string;
  indicator_unit_type: string;
  indicator_unit_label: string;
  indicator_category: string | null;
  accumulation_type: string;
  aggregated_value: number;
  contributing_qisms: number;
  data_points: number;
}

export interface QismSubmissionInfo {
  qism_id: number;
  qism_name: string;
  qism_code: string;
  submission_id: number | null;
  status: string;
  submitted_at: string | null;
}

export interface SubmissionAnswerDetail {
  id: number;
  indicator_name: string;
  indicator_unit_type: string;
  indicator_unit_label: string;
  indicator_category: string | null;
  is_mandatory: boolean;
  numeric_value: number | null;
  text_value: string;
  is_qualitative: boolean;
  qualitative_details: string;
  qualitative_status: string;
}

export interface QismSubmissionDetail {
  id: number;
  status: string;
  submitted_at: string | null;
  planning_approved_by: string | null;
  planning_approved_at: string | null;
  notes: string;
  answers: SubmissionAnswerDetail[];
}

export interface QualitativeAnswerSummary {
  id: number;
  qism_name: string;
  indicator_name: string;
  details: string;
}

export interface PeriodAggregatedData {
  scope_unit: PeriodScopeUnit;
  period: {
    id: number;
    year: number;
    week_number: number;
    start_date: string;
    end_date: string;
    deadline: string | null;
    status: string;
  };
  mode: "qism" | "group";
  qism_submission: QismSubmissionDetail | null;
  qism_submissions: QismSubmissionInfo[];
  aggregated_indicators: AggregatedIndicator[];
  qualitative_answers: QualitativeAnswerSummary[];
  stats: {
    total: number;
    submitted: number;
    approved: number;
    late: number;
    not_submitted: number;
  };
}

export async function getPeriodAggregated(
  periodId: number,
  unitId?: number | null
): Promise<PeriodAggregatedData> {
  const params: Record<string, string> = {};
  if (unitId !== null && unitId !== undefined) {
    params.unit_id = unitId.toString();
  }
  const { data } = await apiClient.get<PeriodAggregatedData>(
    `/periods/${periodId}/aggregated/`,
    { params }
  );
  return data;
}

// --- التمديدات ---

export async function createExtension(
  periodId: number,
  extensionData: {
    qism: number;
    new_deadline: string;
    reason: string;
  }
): Promise<QismExtension> {
  const { data } = await apiClient.post<QismExtension>(
    `/periods/${periodId}/extensions/`,
    extensionData
  );
  return data;
}

// --- الإنجازات النوعية ---

export async function getQualitativeAnswers(
  params?: Record<string, string>
): Promise<ApiResponse<SubmissionAnswer>> {
  const { data } = await apiClient.get<ApiResponse<SubmissionAnswer>>("/qualitative/", { params });
  return data;
}

export async function approveQualitative(answerId: number): Promise<SubmissionAnswer> {
  const { data } = await apiClient.post<SubmissionAnswer>(`/qualitative/${answerId}/approve/`);
  return data;
}

export async function rejectQualitative(answerId: number, reason: string): Promise<SubmissionAnswer> {
  const { data } = await apiClient.post<SubmissionAnswer>(`/qualitative/${answerId}/reject/`, {
    rejection_reason: reason,
  });
  return data;
}
