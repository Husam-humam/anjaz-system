import apiClient from "./client";

// --- أنواع التقارير ---

export interface TargetProgress {
  indicator_name: string;
  cumulative_value: number;
  target_value: number;
  progress_percentage: number;
}

export interface SummaryData {
  period: { year: number; week_number: number };
  compliance_rate: number;
  total_submissions: number;
  approved_submissions: number;
  pending_qualitative: number;
  target_progress: TargetProgress[];
}

export interface PeriodicReportData {
  [key: string]: unknown;
}

export interface ComplianceReportData {
  [key: string]: unknown;
}

export interface QualitativeReportData {
  [key: string]: unknown;
}

// --- دوال التقارير ---

export async function getSummary(params?: Record<string, string>): Promise<SummaryData> {
  const { data } = await apiClient.get<SummaryData>("/reports/summary/", { params });
  return data;
}

export async function getPeriodicReport(params?: Record<string, string>): Promise<PeriodicReportData> {
  const { data } = await apiClient.get<PeriodicReportData>("/reports/periodic/", { params });
  return data;
}

export async function getComplianceReport(params?: Record<string, string>): Promise<ComplianceReportData> {
  const { data } = await apiClient.get<ComplianceReportData>("/reports/compliance/", { params });
  return data;
}

export async function getQualitativeReport(params?: Record<string, string>): Promise<QualitativeReportData> {
  const { data } = await apiClient.get<QualitativeReportData>("/reports/qualitative/", { params });
  return data;
}

export async function exportReport(params: {
  format: "pdf" | "excel";
  period_type: string;
  year: string;
  period_number: string;
  unit_id?: string;
}): Promise<Blob> {
  const { data } = await apiClient.get<Blob>("/reports/export/", {
    params,
    responseType: "blob",
  });
  return data;
}
