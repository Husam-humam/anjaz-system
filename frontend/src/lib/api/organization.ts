import apiClient from "./client";
import type {
  ExternalUnitTypeMapping,
  OrganizationUnit,
  OrganizationSyncReport,
  PlanningAssignment,
  UnitTypeMappingRefreshResult,
  UnitTypeTreatment,
  ViewScope,
} from "@/types/organization";
import type { ApiResponse } from "@/types/api";

// ─── وحدات الهيكل التنظيمي ───────────────────────

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

/** المزامنة من النظام الخارجي — للأدمن فقط. */
export async function syncOrganizationFromExternal(
  dryRun: boolean = false,
): Promise<OrganizationSyncReport> {
  const { data } = await apiClient.post<OrganizationSyncReport>(
    "/organization/units/sync/",
    null,
    { params: dryRun ? { dry_run: "1" } : undefined },
  );
  return data;
}

// ─── تخصيصات أقسام التخطيط ───────────────────────

export async function getPlanningAssignments(
  params?: Record<string, string>,
): Promise<ApiResponse<PlanningAssignment>> {
  const { data } = await apiClient.get<ApiResponse<PlanningAssignment>>(
    "/organization/planning-assignments/",
    { params },
  );
  return data;
}

export async function getPlanningAssignment(id: number): Promise<PlanningAssignment> {
  const { data } = await apiClient.get<PlanningAssignment>(
    `/organization/planning-assignments/${id}/`,
  );
  return data;
}

export async function createPlanningAssignment(payload: {
  planning_unit: number;
  context_parent?: number | null;
  notes?: string;
}): Promise<PlanningAssignment> {
  const { data } = await apiClient.post<PlanningAssignment>(
    "/organization/planning-assignments/",
    payload,
  );
  return data;
}

export async function updatePlanningAssignment(
  id: number,
  payload: Partial<{ context_parent: number | null; notes: string }>,
): Promise<PlanningAssignment> {
  const { data } = await apiClient.patch<PlanningAssignment>(
    `/organization/planning-assignments/${id}/`,
    payload,
  );
  return data;
}

export async function deletePlanningAssignment(id: number): Promise<void> {
  await apiClient.delete(`/organization/planning-assignments/${id}/`);
}

export async function addSupervisedUnit(
  assignmentId: number,
  unitId: number,
): Promise<{ id: number; unit: number; unit_name: string; unit_code: string }> {
  const { data } = await apiClient.post(
    `/organization/planning-assignments/${assignmentId}/supervised-units/`,
    { unit: unitId },
  );
  return data;
}

export async function removeSupervisedUnit(
  assignmentId: number,
  unitId: number,
): Promise<void> {
  await apiClient.delete(
    `/organization/planning-assignments/${assignmentId}/supervised-units/${unitId}/`,
  );
}

// ─── نطاقات الاطّلاع ─────────────────────────────

export async function getViewScopes(
  params?: Record<string, string>,
): Promise<ApiResponse<ViewScope>> {
  const { data } = await apiClient.get<ApiResponse<ViewScope>>(
    "/organization/view-scopes/",
    { params },
  );
  return data;
}

export async function getViewScopeForUser(userId: number): Promise<ViewScope | null> {
  const result = await getViewScopes({ user: String(userId) });
  return result.results[0] ?? null;
}

export async function upsertViewScope(payload: {
  id?: number;
  user: number;
  viewable_units: number[];
  notes?: string;
}): Promise<ViewScope> {
  if (payload.id) {
    const { data } = await apiClient.patch<ViewScope>(
      `/organization/view-scopes/${payload.id}/`,
      {
        viewable_units: payload.viewable_units,
        notes: payload.notes ?? "",
      },
    );
    return data;
  }
  const { data } = await apiClient.post<ViewScope>(
    "/organization/view-scopes/",
    payload,
  );
  return data;
}

export async function deleteViewScope(id: number): Promise<void> {
  await apiClient.delete(`/organization/view-scopes/${id}/`);
}

// ─── تطابق أنواع الوحدات الخارجيّة ───────────────

export async function getUnitTypeMappings(): Promise<ApiResponse<ExternalUnitTypeMapping>> {
  const { data } = await apiClient.get<ApiResponse<ExternalUnitTypeMapping>>(
    "/organization/unit-type-mappings/",
    { params: { page_size: "1000" } },
  );
  return data;
}

export async function updateUnitTypeMapping(
  id: number,
  treat_as: UnitTypeTreatment,
): Promise<ExternalUnitTypeMapping> {
  const { data } = await apiClient.patch<ExternalUnitTypeMapping>(
    `/organization/unit-type-mappings/${id}/`,
    { treat_as },
  );
  return data;
}

export async function refreshUnitTypeMappings(): Promise<UnitTypeMappingRefreshResult> {
  const { data } = await apiClient.post<UnitTypeMappingRefreshResult>(
    "/organization/unit-type-mappings/refresh/",
  );
  return data;
}
