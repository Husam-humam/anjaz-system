export const STATUS_LABELS: Record<string, string> = {
  draft: "مسودة",
  submitted: "مُرسل",
  approved: "معتمد",
  returned: "مُرجَع للتصحيح",
  late: "متأخر",
  extended: "مُمدَّد",
  returned_by_admin: "مُرجَع من الإحصاء",
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
  returned: "bg-amber-100 text-amber-700",
  late: "bg-red-100 text-red-700",
  extended: "bg-orange-100 text-orange-700",
  returned_by_admin: "bg-purple-100 text-purple-700",
  pending_approval: "bg-yellow-100 text-yellow-700",
  rejected: "bg-red-100 text-red-700",
  superseded: "bg-gray-100 text-gray-500",
  open: "bg-green-100 text-green-700",
  closed: "bg-gray-100 text-gray-700",
};

/** تسميات أنواع إجراءات سجلّ التدقيق */
export const AUDIT_ACTION_LABELS: Record<string, string> = {
  submission_created: "إنشاء منجز",
  submission_saved: "حفظ إجابات",
  submission_submitted: "إرسال المنجز",
  submission_planning_approved: "اعتماد من التخطيط",
  submission_planning_returned: "إرجاع من التخطيط",
  submission_admin_approved: "اعتماد من الإحصاء",
  submission_admin_edited: "تعديل من الإحصاء",
  submission_admin_returned: "إرجاع من الإحصاء",
  qualitative_planning_approved: "اعتماد نوعي من التخطيط",
  qualitative_planning_rejected: "رفض نوعي من التخطيط",
  qualitative_admin_approved: "اعتماد نوعي من الإحصاء",
  qualitative_admin_rejected: "رفض نوعي من الإحصاء",
  template_created: "إنشاء قالب",
  template_updated: "تعديل قالب",
  template_submitted: "تقديم قالب",
  template_approved: "اعتماد قالب",
  template_rejected: "رفض قالب",
  template_new_version: "إصدار جديد",
  target_created: "إنشاء مستهدف",
  target_updated: "تعديل مستهدف",
  target_deleted: "حذف مستهدف",
  extension_granted: "منح تمديد",
  period_opened: "فتح أسبوع",
  period_closed: "إغلاق أسبوع",
};

/** ألوان لتمييز نوع الإجراء في timeline */
export const AUDIT_ACTION_COLORS: Record<string, string> = {
  submission_created: "bg-gray-100 text-gray-700",
  submission_saved: "bg-gray-100 text-gray-700",
  submission_submitted: "bg-blue-100 text-blue-700",
  submission_planning_approved: "bg-green-100 text-green-700",
  submission_planning_returned: "bg-amber-100 text-amber-700",
  submission_admin_approved: "bg-emerald-100 text-emerald-700",
  submission_admin_edited: "bg-indigo-100 text-indigo-700",
  submission_admin_returned: "bg-purple-100 text-purple-700",
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
