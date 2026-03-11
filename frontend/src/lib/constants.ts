export const STATUS_LABELS: Record<string, string> = {
  draft: "مسودة",
  submitted: "مُرسل",
  approved: "معتمد",
  late: "متأخر",
  extended: "مُمدَّد",
  pending_approval: "بانتظار الاعتماد",
  rejected: "مرفوض",
  superseded: "مُستبدَل",
  open: "مفتوح",
  closed: "مغلق",
};

export const STATUS_COLORS: Record<string, string> = {
  draft: "bg-gray-100 text-gray-700",
  submitted: "bg-blue-100 text-blue-700",
  approved: "bg-green-100 text-green-700",
  late: "bg-red-100 text-red-700",
  extended: "bg-orange-100 text-orange-700",
  pending_approval: "bg-yellow-100 text-yellow-700",
  rejected: "bg-red-100 text-red-700",
  superseded: "bg-gray-100 text-gray-500",
  open: "bg-green-100 text-green-700",
  closed: "bg-gray-100 text-gray-700",
};

export const ROLE_LABELS: Record<string, string> = {
  statistics_admin: "مدير قسم الإحصاء",
  planning_section: "قسم التخطيط",
  section_manager: "مدير قسم",
};

export const UNIT_TYPE_LABELS: Record<string, string> = {
  number: "رقم",
  percentage: "نسبة مئوية",
  text: "نص",
  hours: "ساعات",
  days: "أيام",
};

export const ACCUMULATION_TYPE_LABELS: Record<string, string> = {
  sum: "مجموع",
  average: "متوسط",
  last_value: "آخر قيمة",
};
