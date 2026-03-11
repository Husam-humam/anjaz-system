import apiClient from "./client";
import type {
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

export async function updateSubmission(
  id: number,
  submissionData: {
    answers?: {
      form_item: number;
      numeric_value?: number | null;
      text_value?: string;
      is_qualitative?: boolean;
      qualitative_details?: string;
    }[];
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
