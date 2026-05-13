export interface WeeklyPeriod {
  id: number;
  year: number;
  week_number: number;
  start_date: string;
  end_date: string;
  deadline: string;
  status: "open" | "closed";
  created_at: string;
}

export type SubmissionStatus =
  | "draft"
  | "submitted"
  | "approved"
  | "returned"
  | "late"
  | "extended"
  | "returned_by_admin";

export type AdminReviewAction = "approved" | "edited" | "returned" | "";

export interface WeeklySubmission {
  id: number;
  qism: number;
  qism_name: string;
  qism_parent_name: string | null;
  weekly_period: number;
  period_display: string;
  period_week_number: number;
  period_year: number;
  form_template: number;
  status: SubmissionStatus;
  submitted_at: string | null;
  planning_approved_by: number | null;
  planning_approved_by_name: string | null;
  planning_approved_at: string | null;
  /** تاريخ ووقت مراجعة الإحصاء (null = لم تُراجَع بعد) */
  admin_reviewed_at: string | null;
  admin_reviewed_by: number | null;
  admin_reviewed_by_name: string | null;
  admin_review_action: AdminReviewAction;
  notes: string;
  answers: SubmissionAnswer[];
  is_editable: boolean;
}

export interface SubmissionAnswer {
  id: number;
  form_item: number;
  indicator_name: string;
  indicator_unit_type: string;
  numeric_value: number | null;
  text_value: string;
  is_qualitative: boolean;
  qualitative_details: string;
  qualitative_status: "none" | "pending_planning" | "pending_statistics" | "approved" | "rejected";
}

export interface FormTemplate {
  id: number;
  qism: number;
  qism_name: string;
  version: number;
  status: "draft" | "pending_approval" | "approved" | "superseded" | "rejected";
  effective_from_week: number | null;
  effective_from_year: number | null;
  items: FormTemplateItem[];
  created_at: string;
}

export interface FormTemplateItem {
  id: number;
  indicator: number;
  indicator_name: string;
  is_mandatory: boolean;
  display_order: number;
}

export type TargetScopeLevel =
  | "institution"
  | "daira"
  | "mudiriya"
  | "qism";

export interface Target {
  id: number;
  scope_unit: number | null; // null => مستوى المؤسسة
  scope_unit_name: string | null;
  scope_unit_type: string | null;
  scope_level: TargetScopeLevel;
  indicator: number;
  indicator_name: string;
  indicator_unit_type: string;
  indicator_accumulation_type: string;
  indicator_category: number | null;
  indicator_category_name: string | null;
  year: number;
  target_value: number;
  notes: string;
  set_by: number | null;
  set_by_name: string | null;
  created_at: string;
  updated_at: string;
  /** يُملأ فقط عند استدعاء الـ API بـ ?with_progress=true */
  progress?: {
    cumulative_value: number;
    target_value: number;
    remaining: number;
    progress_percentage: number;
    qisms_in_scope: number;
  } | null;
}

export interface TargetProgressData {
  target_id: number;
  indicator_name: string;
  indicator_accumulation_type: string;
  scope_unit_name: string;
  scope_level: TargetScopeLevel;
  year: number;
  cumulative_value: number;
  target_value: number;
  remaining: number;
  progress_percentage: number;
  qisms_in_scope: number;
}

/** عقدة في شجرة التفصيل (مؤسسة/دائرة/مديرية/قسم) */
export interface TargetBreakdownNode {
  unit_id: number;
  unit_name: string;
  unit_code: string;
  unit_type: "daira" | "mudiriya" | "qism";
  contribution_value: number;
  contribution_percentage_of_achieved: number;
  contribution_percentage_of_target: number;
  has_children: boolean;
  children: TargetBreakdownNode[];
}

export interface TargetBreakdown {
  target_id: number;
  indicator_name: string;
  scope_unit_name: string;
  scope_level: TargetScopeLevel;
  year: number;
  target_value: number;
  cumulative_value: number;
  progress_percentage: number;
  qisms_in_scope: number;
  breakdown: TargetBreakdownNode[];
  breakdown_type: "tree" | "none";
}

export interface QismExtension {
  id: number;
  qism: number;
  qism_name: string;
  weekly_period: number;
  new_deadline: string;
  reason: string;
}

/** نوع الإجراء في سجلّ التدقيق — يطابق apps/audit/models.py:ActionType */
export type AuditActionType =
  | "submission_created"
  | "submission_saved"
  | "submission_submitted"
  | "submission_planning_approved"
  | "submission_planning_returned"
  | "submission_admin_approved"
  | "submission_admin_edited"
  | "submission_admin_returned"
  | "qualitative_planning_approved"
  | "qualitative_planning_rejected"
  | "qualitative_admin_approved"
  | "qualitative_admin_rejected"
  | "template_created"
  | "template_updated"
  | "template_submitted"
  | "template_approved"
  | "template_rejected"
  | "template_new_version"
  | "target_created"
  | "target_updated"
  | "target_deleted"
  | "extension_granted"
  | "period_opened"
  | "period_closed";

/** سطر واحد من تعديل حقل ضمن حدث تعديل */
export interface AuditFieldChange {
  field: string;
  old: string | null;
  new: string | null;
  answer_id?: number;
  indicator_id?: number;
  indicator_name?: string;
}

export interface AuditLogEntry {
  id: number;
  action_type: AuditActionType;
  action_label: string;
  actor_id: number | null;
  actor_name: string;
  actor_role: string;
  field_changes: AuditFieldChange[] | null;
  reason: string;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

export interface Notification {
  id: number;
  notification_type: string;
  title: string;
  message: string;
  is_read: boolean;
  related_model: string;
  related_id: number | null;
  created_at: string;
}

export type UserRole = "statistics_admin" | "planning_section" | "section_manager";

export interface User {
  id: number;
  username: string;
  full_name: string;
  role: UserRole;
  unit: {
    id: number;
    name: string;
    code: string;
  } | null;
  is_active: boolean;
}

export interface LoginResponse {
  access: string;
  refresh: string;
  user: User;
}
