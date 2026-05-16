export interface OrganizationUnit {
  id: number;
  name: string;
  code: string;
  unit_type: "daira" | "mudiriya" | "qism";
  parent: number | null;
  parent_name: string | null;
  is_active: boolean;
  /** هل هذه الوحدة قسم تخطيط (يوجد PlanningAssignment)؟ */
  is_planning?: boolean;
  /** هل هذه الوحدة قسم مُشرَف عليه (يوجد SupervisedUnit)؟ */
  is_supervised?: boolean;
  /** المعرّف في النظام الخارجي (إن وُجد) */
  external_id?: number | null;
  /** عدد الموظّفين الفعليّ في الوحدة (من النظام الخارجي) */
  employees_count?: number;
  children?: OrganizationUnit[];
  created_at: string;
  updated_at: string;
}

/** تقرير نتيجة المزامنة من النظام الخارجي */
export interface OrganizationSyncReport {
  created: number;
  updated: number;
  deactivated: number;
  skipped_unknown_type: number;
  errors: string[];
  summary: string;
  started_at: string;
  finished_at: string;
  dry_run: boolean;
}

/** قسم مُشرَف عليه مُضمَّن في PlanningAssignment */
export interface SupervisedUnitNested {
  id: number;
  unit: number;
  unit_name: string;
  unit_code: string;
  unit_employees_count?: number;
  created_at: string;
}

/** تخصيص قسم تخطيط (مع الأقسام المُشرَف عليها) */
export interface PlanningAssignment {
  id: number;
  planning_unit: number;
  planning_unit_name: string;
  planning_unit_code: string;
  context_parent: number | null;
  context_parent_name: string | null;
  supervised_units: SupervisedUnitNested[];
  notes: string;
  created_at: string;
  updated_at: string;
  created_by: number | null;
  created_by_name: string | null;
}

/** تطابق نوع وحدة خارجي → نوع داخلي */
export type UnitTypeTreatment =
  | "daira"
  | "mudiriya"
  | "qism"
  | "ignore"
  | null;

export interface ExternalUnitTypeMapping {
  id: number;
  external_type_name: string;
  external_type_id: number | null;
  treat_as: UnitTypeTreatment;
  treat_as_display: string | null;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface UnitTypeMappingRefreshResult {
  created: number;
  existing: number;
  mappings: ExternalUnitTypeMapping[];
}

/** نطاق اطّلاع لمستخدم */
export interface ViewScope {
  id: number;
  user: number;
  user_full_name: string;
  user_role: string;
  viewable_units: number[];
  viewable_units_detail: OrganizationUnit[];
  notes: string;
  created_at: string;
  updated_at: string;
}
