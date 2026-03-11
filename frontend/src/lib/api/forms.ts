import apiClient from "./client";
import type { FormTemplate } from "@/types/submissions";
import type { ApiResponse } from "@/types/api";

export async function getFormTemplates(params?: Record<string, string>): Promise<ApiResponse<FormTemplate>> {
  const { data } = await apiClient.get<ApiResponse<FormTemplate>>("/forms/templates/", { params });
  return data;
}

export async function getFormTemplate(id: number): Promise<FormTemplate> {
  const { data } = await apiClient.get<FormTemplate>(`/forms/templates/${id}/`);
  return data;
}

export async function createFormTemplate(templateData: {
  qism: number;
  items: { indicator: number; is_mandatory: boolean; display_order: number }[];
  notes?: string;
}): Promise<FormTemplate> {
  const { data } = await apiClient.post<FormTemplate>("/forms/templates/", templateData);
  return data;
}

export async function updateFormTemplate(
  id: number,
  templateData: {
    items?: { indicator: number; is_mandatory: boolean; display_order: number }[];
    notes?: string;
  }
): Promise<FormTemplate> {
  const { data } = await apiClient.patch<FormTemplate>(`/forms/templates/${id}/`, templateData);
  return data;
}

export async function submitFormTemplate(id: number): Promise<FormTemplate> {
  const { data } = await apiClient.post<FormTemplate>(`/forms/templates/${id}/submit/`);
  return data;
}

export async function approveFormTemplate(
  id: number,
  approvalData: { effective_from_week: number; effective_from_year: number }
): Promise<FormTemplate> {
  const { data } = await apiClient.post<FormTemplate>(`/forms/templates/${id}/approve/`, approvalData);
  return data;
}

export async function rejectFormTemplate(id: number, rejectionReason: string): Promise<FormTemplate> {
  const { data } = await apiClient.post<FormTemplate>(`/forms/templates/${id}/reject/`, {
    rejection_reason: rejectionReason,
  });
  return data;
}

export async function getActiveTemplate(qismId: number): Promise<FormTemplate> {
  const { data } = await apiClient.get<FormTemplate>("/forms/templates/active/", {
    params: { qism_id: qismId },
  });
  return data;
}
