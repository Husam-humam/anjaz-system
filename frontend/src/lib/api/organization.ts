import apiClient from "./client";
import type { OrganizationUnit } from "@/types/organization";
import type { ApiResponse } from "@/types/api";

export async function getOrganizationTree(): Promise<OrganizationUnit[]> {
  const { data } = await apiClient.get<OrganizationUnit[]>("/organization/units/tree/");
  return data;
}

export async function getOrganizationUnits(params?: Record<string, string>): Promise<ApiResponse<OrganizationUnit>> {
  const { data } = await apiClient.get<ApiResponse<OrganizationUnit>>("/organization/units/", { params });
  return data;
}

export async function getOrganizationUnit(id: number): Promise<OrganizationUnit> {
  const { data } = await apiClient.get<OrganizationUnit>(`/organization/units/${id}/`);
  return data;
}

export async function createOrganizationUnit(unitData: Partial<OrganizationUnit>): Promise<OrganizationUnit> {
  const { data } = await apiClient.post<OrganizationUnit>("/organization/units/", unitData);
  return data;
}

export async function updateOrganizationUnit(id: number, unitData: Partial<OrganizationUnit>): Promise<OrganizationUnit> {
  const { data } = await apiClient.patch<OrganizationUnit>(`/organization/units/${id}/`, unitData);
  return data;
}

export async function deleteOrganizationUnit(id: number): Promise<void> {
  await apiClient.delete(`/organization/units/${id}/`);
}
