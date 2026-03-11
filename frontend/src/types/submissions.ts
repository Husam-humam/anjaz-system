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

export interface WeeklySubmission {
  id: number;
  qism: number;
  qism_name: string;
  weekly_period: number;
  period_display: string;
  form_template: number;
  status: "draft" | "submitted" | "approved" | "late" | "extended";
  submitted_at: string | null;
  planning_approved_by: number | null;
  planning_approved_at: string | null;
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

export interface Target {
  id: number;
  qism: number;
  qism_name: string;
  indicator: number;
  indicator_name: string;
  year: number;
  target_value: number;
  notes: string;
}

export interface QismExtension {
  id: number;
  qism: number;
  qism_name: string;
  weekly_period: number;
  new_deadline: string;
  reason: string;
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
