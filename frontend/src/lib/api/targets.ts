import apiClient from "./client";
import type {
  Target,
  TargetBreakdown,
  TargetProgressData,
} from "@/types/submissions";
import type { ApiResponse } from "@/types/api";

// --- المستهدفات الهرمية ---

export interface TargetInput {
  scope_unit: number | null; // null => مستوى المؤسسة
  indicator: number;
  year: number;
  target_value: number;
  notes?: string;
}

export async function getTargets(
  params?: Record<string, string>
): Promise<ApiResponse<Target>> {
  const { data } = await apiClient.get<ApiResponse<Target>>("/targets/", {
    params,
  });
  return data;
}

export async function getTarget(id: number): Promise<Target> {
  const { data } = await apiClient.get<Target>(`/targets/${id}/`);
  return data;
}

export async function createTarget(targetData: TargetInput): Promise<Target> {
  const { data } = await apiClient.post<Target>("/targets/", targetData);
  return data;
}

export async function updateTarget(
  id: number,
  targetData: Partial<TargetInput>
): Promise<Target> {
  const { data } = await apiClient.patch<Target>(`/targets/${id}/`, targetData);
  return data;
}

export async function deleteTarget(id: number): Promise<void> {
  await apiClient.delete(`/targets/${id}/`);
}

export async function getTargetProgress(id: number): Promise<TargetProgressData> {
  const { data } = await apiClient.get<TargetProgressData>(
    `/targets/${id}/progress/`
  );
  return data;
}

export async function getTargetBreakdown(id: number): Promise<TargetBreakdown> {
  const { data } = await apiClient.get<TargetBreakdown>(
    `/targets/${id}/breakdown/`
  );
  return data;
}
