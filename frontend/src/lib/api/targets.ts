import apiClient from "./client";
import type { Target } from "@/types/submissions";
import type { ApiResponse } from "@/types/api";

// --- المستهدفات ---

export async function getTargets(params?: Record<string, string>): Promise<ApiResponse<Target>> {
  const { data } = await apiClient.get<ApiResponse<Target>>("/targets/", { params });
  return data;
}

export async function getTarget(id: number): Promise<Target> {
  const { data } = await apiClient.get<Target>(`/targets/${id}/`);
  return data;
}

export async function createTarget(targetData: {
  qism: number;
  indicator: number;
  year: number;
  target_value: number;
  notes?: string;
}): Promise<Target> {
  const { data } = await apiClient.post<Target>("/targets/", targetData);
  return data;
}

export async function updateTarget(id: number, targetData: Partial<Target>): Promise<Target> {
  const { data } = await apiClient.patch<Target>(`/targets/${id}/`, targetData);
  return data;
}

export async function deleteTarget(id: number): Promise<void> {
  await apiClient.delete(`/targets/${id}/`);
}
