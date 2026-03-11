import apiClient from "./client";
import type { Indicator, IndicatorCategory } from "@/types/indicators";
import type { ApiResponse } from "@/types/api";

// --- فئات المؤشرات ---

export async function getIndicatorCategories(params?: Record<string, string>): Promise<ApiResponse<IndicatorCategory>> {
  const { data } = await apiClient.get<ApiResponse<IndicatorCategory>>("/indicators/categories/", { params });
  return data;
}

export async function createIndicatorCategory(categoryData: Partial<IndicatorCategory>): Promise<IndicatorCategory> {
  const { data } = await apiClient.post<IndicatorCategory>("/indicators/categories/", categoryData);
  return data;
}

export async function updateIndicatorCategory(id: number, categoryData: Partial<IndicatorCategory>): Promise<IndicatorCategory> {
  const { data } = await apiClient.patch<IndicatorCategory>(`/indicators/categories/${id}/`, categoryData);
  return data;
}

// --- المؤشرات ---

export async function getIndicators(params?: Record<string, string>): Promise<ApiResponse<Indicator>> {
  const { data } = await apiClient.get<ApiResponse<Indicator>>("/indicators/", { params });
  return data;
}

export async function getIndicator(id: number): Promise<Indicator> {
  const { data } = await apiClient.get<Indicator>(`/indicators/${id}/`);
  return data;
}

export async function createIndicator(indicatorData: Partial<Indicator>): Promise<Indicator> {
  const { data } = await apiClient.post<Indicator>("/indicators/", indicatorData);
  return data;
}

export async function updateIndicator(id: number, indicatorData: Partial<Indicator>): Promise<Indicator> {
  const { data } = await apiClient.patch<Indicator>(`/indicators/${id}/`, indicatorData);
  return data;
}
