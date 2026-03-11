export interface IndicatorCategory {
  id: number;
  name: string;
  is_active: boolean;
}

export interface Indicator {
  id: number;
  name: string;
  description: string;
  unit_type: "number" | "percentage" | "text" | "hours" | "days";
  unit_label: string;
  accumulation_type: "sum" | "average" | "last_value";
  category: number | null;
  category_name: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}
