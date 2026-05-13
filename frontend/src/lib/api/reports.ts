import apiClient from "./client";

// --- أنواع التقارير ---

export interface TargetProgress {
  target_id?: number;
  indicator_name: string;
  qism_name: string;
  scope_unit_name?: string;
  scope_level?: string;
  cumulative_value: number;
  target_value: number;
  progress_percentage: number;
}

export interface SummaryPeriod {
  year: number;
  week_number: number;
  status: "open" | "closed";
  deadline: string | null;
}

export interface SummaryData {
  period: SummaryPeriod | null;
  compliance_rate: number;
  total_submissions: number;
  approved_submissions: number;
  pending_qualitative: number;
  status_breakdown?: Record<string, number>;
  target_progress: TargetProgress[];
}

export interface PeriodicReportRow {
  qism_id: number;
  qism_name: string;
  qism_code: string;
  parent_id: number | null;
  parent_name: string | null;
  grandparent_id: number | null;
  grandparent_name: string | null;
  indicator_id: number;
  indicator_name: string;
  indicator_category: string | null;
  aggregated_value: number | null;
  accumulation_type: string;
  data_points: number;
}

export interface IndicatorSummary {
  indicator_id: number;
  indicator_name: string;
  indicator_category: string | null;
  total_value: number | null;
  accumulation_type: string;
  contributing_qisms: number;
  data_points: number;
}

export interface PeriodicReportMeta {
  weeks_count: number;
  period_type: string | null;
  year: number | null;
  period_number: number | null;
  from_date: string | null;
  to_date: string | null;
}

export interface PeriodicReportData {
  results: PeriodicReportRow[];
  indicator_summary: IndicatorSummary[];
  meta: PeriodicReportMeta;
}

export interface ComplianceRow {
  qism_id: number;
  qism_name: string;
  total_periods: number;
  submitted: number;
  late: number;
  not_submitted: number;
  compliance_rate: number;
}

export interface QualitativeReportItem {
  id: number;
  qism_name: string;
  indicator_name: string;
  week_number: number;
  qualitative_details: string;
  approved_by: string | null;
  approved_at: string | null;
}

// --- دوال التقارير ---

export async function getSummary(params?: Record<string, string>): Promise<SummaryData> {
  const { data } = await apiClient.get<SummaryData>("/reports/summary/", { params });
  return data;
}

export async function getPeriodicReport(
  params?: Record<string, string>
): Promise<PeriodicReportData> {
  const { data } = await apiClient.get<PeriodicReportData>(
    "/reports/periodic/",
    { params }
  );
  return data;
}

export async function getComplianceReport(
  params?: Record<string, string>
): Promise<ComplianceRow[]> {
  const { data } = await apiClient.get<ComplianceRow[]>(
    "/reports/compliance/",
    { params }
  );
  return data;
}

export async function getQualitativeReport(
  params?: Record<string, string>
): Promise<QualitativeReportItem[]> {
  const { data } = await apiClient.get<QualitativeReportItem[]>(
    "/reports/qualitative/",
    { params }
  );
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
