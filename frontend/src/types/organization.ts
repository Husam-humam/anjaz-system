export interface OrganizationUnit {
  id: number;
  name: string;
  code: string;
  unit_type: "daira" | "mudiriya" | "qism";
  qism_role: "regular" | "planning" | "statistics";
  parent: number | null;
  parent_name: string | null;
  is_active: boolean;
  children?: OrganizationUnit[];
  created_at: string;
  updated_at: string;
}
