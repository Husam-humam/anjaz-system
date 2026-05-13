"use client";

import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getTargets,
  createTarget,
  updateTarget,
  deleteTarget,
  getTargetBreakdown,
} from "@/lib/api/targets";
import { getOrganizationUnits } from "@/lib/api/organization";
import {
  getIndicators,
  getIndicatorCategories,
} from "@/lib/api/indicators";
import type {
  Target,
  TargetScopeLevel,
  TargetBreakdownNode,
} from "@/types/submissions";
import type { OrganizationUnit } from "@/types/organization";
import type { Indicator, IndicatorCategory } from "@/types/indicators";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { ErrorState } from "@/components/shared/ErrorState";
import { EmptyState } from "@/components/shared/EmptyState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import {
  Plus,
  Pencil,
  Trash2,
  Search,
  Building2,
  Layers,
  FolderTree,
  Target as TargetIcon,
  AlertCircle,
  BarChart3,
  Eye,
  ChevronDown,
  ChevronLeft,
} from "lucide-react";
import { getErrorMessage } from "@/lib/utils";

interface TargetFormData {
  scope_level: TargetScopeLevel;
  scope_unit: number | null;
  indicator: number | null;
  year: number;
  target_value: number;
  notes: string;
}

const currentYear = new Date().getFullYear();

const initialFormData: TargetFormData = {
  scope_level: "institution",
  scope_unit: null,
  indicator: null,
  year: currentYear,
  target_value: 0,
  notes: "",
};

const SCOPE_LEVEL_LABELS: Record<TargetScopeLevel, string> = {
  institution: "المؤسسة كاملة",
  daira: "دائرة",
  mudiriya: "مديرية",
  qism: "قسم",
};

const SCOPE_LEVEL_ICONS: Record<
  TargetScopeLevel,
  React.ComponentType<{ className?: string }>
> = {
  institution: Building2,
  daira: FolderTree,
  mudiriya: Layers,
  qism: TargetIcon,
};

const SCOPE_LEVEL_COLORS: Record<TargetScopeLevel, string> = {
  institution: "bg-purple-100 text-purple-800 border-purple-200",
  daira: "bg-blue-100 text-blue-800 border-blue-200",
  mudiriya: "bg-emerald-100 text-emerald-800 border-emerald-200",
  qism: "bg-amber-100 text-amber-800 border-amber-200",
};

// أيقونة ولون حسب نوع الوحدة في الشجرة
const UNIT_TYPE_STYLES: Record<
  "daira" | "mudiriya" | "qism",
  { icon: React.ComponentType<{ className?: string }>; color: string; label: string }
> = {
  daira: { icon: FolderTree, color: "text-blue-700", label: "دائرة" },
  mudiriya: { icon: Layers, color: "text-emerald-700", label: "مديرية" },
  qism: { icon: TargetIcon, color: "text-amber-700", label: "قسم" },
};

// ═══ مكوّن الشجرة الهرمية لتفصيل المستهدف ═══
interface TreeNodeProps {
  node: TargetBreakdownNode;
  level: number;
}

function BreakdownTreeNode({ node, level }: TreeNodeProps) {
  // الدوائر والمديريات مفتوحة افتراضياً في المستوى الأول، البقية مغلقة
  const [expanded, setExpanded] = useState(level === 0 && node.unit_type !== "qism");
  const style = UNIT_TYPE_STYLES[node.unit_type];
  const Icon = style.icon;
  const isZero = node.contribution_value === 0;

  const canExpand = node.has_children && node.children.length > 0;
  const toggle = () => canExpand && setExpanded((v) => !v);

  return (
    <div className="select-none">
      <div
        onClick={toggle}
        className={`flex items-center gap-2 py-2 px-3 rounded-md border transition ${
          canExpand ? "cursor-pointer hover:bg-gray-50" : "cursor-default"
        } ${isZero ? "bg-red-50/50 border-red-100" : "bg-white border-gray-200"}`}
        style={{ marginInlineStart: `${level * 24}px` }}
      >
        {/* أيقونة التوسيع */}
        <div className="w-4 h-4 flex-shrink-0">
          {canExpand ? (
            expanded ? (
              <ChevronDown className="w-4 h-4 text-gray-500" />
            ) : (
              <ChevronLeft className="w-4 h-4 text-gray-500" />
            )
          ) : null}
        </div>

        {/* أيقونة النوع */}
        <Icon className={`w-4 h-4 flex-shrink-0 ${style.color}`} />

        {/* اسم الوحدة */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-gray-900 truncate">
              {node.unit_name}
            </span>
            <span className="text-xs text-gray-400" dir="ltr">
              {node.unit_code}
            </span>
            <span className={`text-xs ${style.color}`}>
              {style.label}
            </span>
          </div>
        </div>

        {/* القيمة والنسب */}
        <div className="flex items-center gap-3 text-xs flex-shrink-0">
          <div className="text-right">
            <div className="font-bold text-gray-900" dir="ltr">
              {isZero ? (
                <span className="text-red-500">—</span>
              ) : (
                node.contribution_value.toLocaleString("ar-IQ")
              )}
            </div>
            <div className="text-gray-500" dir="ltr">
              {node.contribution_percentage_of_target}% من المستهدف
            </div>
          </div>
          {!isZero && (
            <div className="w-20 bg-gray-100 rounded-full h-1.5 overflow-hidden">
              <div
                className={`h-1.5 rounded-full ${
                  node.contribution_percentage_of_target >= 100
                    ? "bg-green-500"
                    : node.contribution_percentage_of_target >= 50
                    ? "bg-blue-500"
                    : "bg-amber-500"
                }`}
                style={{
                  width: `${Math.min(
                    node.contribution_percentage_of_target,
                    100
                  )}%`,
                }}
              />
            </div>
          )}
        </div>
      </div>

      {/* الأبناء */}
      {expanded && canExpand && (
        <div className="mt-1 space-y-1">
          {node.children.map((child) => (
            <BreakdownTreeNode
              key={child.unit_id}
              node={child}
              level={level + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function TargetsPage() {
  const queryClient = useQueryClient();

  // ── حالات الفلترة ──
  const [yearFilter, setYearFilter] = useState(currentYear.toString());
  const [scopeLevelFilter, setScopeLevelFilter] = useState<string>("");
  const [categoryFilter, setCategoryFilter] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState("");

  // ── حالات الحوار ──
  const [dialogOpen, setDialogOpen] = useState(false);
  const [formData, setFormData] = useState<TargetFormData>(initialFormData);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [breakdownTargetId, setBreakdownTargetId] = useState<number | null>(null);
  const [breakdownOpen, setBreakdownOpen] = useState(false);

  // ── الاستعلامات ──
  const queryParams: Record<string, string> = {
    with_progress: "true", // دائماً نطلب التقدم للجدول
  };
  if (yearFilter) queryParams.year = yearFilter;
  if (scopeLevelFilter) queryParams.scope_level = scopeLevelFilter;
  if (categoryFilter) queryParams.indicator__category = categoryFilter;

  const {
    data: targetsData,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["targets", queryParams],
    queryFn: () => getTargets(queryParams),
  });

  // قوائم الوحدات للفلاتر والـ form
  const { data: dairasData } = useQuery({
    queryKey: ["organization-units-daira"],
    queryFn: () => getOrganizationUnits({ unit_type: "daira" }),
  });

  const { data: mudiriyasData } = useQuery({
    queryKey: ["organization-units-mudiriya"],
    queryFn: () => getOrganizationUnits({ unit_type: "mudiriya" }),
  });

  const { data: qismsData } = useQuery({
    queryKey: ["organization-units-qism-regular"],
    queryFn: () => getOrganizationUnits({ unit_type: "qism" }),
  });

  const { data: indicatorsData } = useQuery({
    queryKey: ["indicators-active-all"],
    queryFn: () =>
      getIndicators({ is_active: "true", page_size: "1000" }),
  });

  const { data: indicatorCategoriesData } = useQuery({
    queryKey: ["indicator-categories"],
    queryFn: () => getIndicatorCategories(),
  });

  const { data: breakdownData, isLoading: breakdownLoading } = useQuery({
    queryKey: ["target-breakdown", breakdownTargetId],
    queryFn: () => getTargetBreakdown(breakdownTargetId!),
    enabled: !!breakdownTargetId && breakdownOpen,
  });

  // ── Mutations ──
  const createMutation = useMutation({
    mutationFn: createTarget,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["targets"] });
      closeDialog();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<Target> }) =>
      updateTarget(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["targets"] });
      closeDialog();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteTarget,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["targets"] });
      setDeleteConfirmOpen(false);
      setDeletingId(null);
    },
  });

  // ── بيانات مستخرجة ──
  const targets = targetsData?.results || [];
  const dairas = dairasData?.results || [];
  const mudiriyas = mudiriyasData?.results || [];
  const qisms = (qismsData?.results || []).filter(
    // إظهار الأقسام العادية فقط في الـ form (لا الإحصاء/التخطيط)
    (q: OrganizationUnit) => q.qism_role === "regular"
  );
  const indicators = indicatorsData?.results || [];
  const categories = indicatorCategoriesData?.results || [];

  // تصفية محلية بالبحث النصّي
  const filteredTargets = useMemo(() => {
    if (!searchQuery.trim()) return targets;
    const q = searchQuery.trim().toLowerCase();
    return targets.filter(
      (t: Target) =>
        (t.scope_unit_name || "").toLowerCase().includes(q) ||
        t.indicator_name.toLowerCase().includes(q) ||
        (t.notes || "").toLowerCase().includes(q)
    );
  }, [targets, searchQuery]);

  // المؤشرات المتاحة في الـ form (تستبعد النصية والـ last_value إذا النطاق غير قسم)
  const availableIndicators = useMemo(() => {
    return indicators.filter((ind: Indicator) => {
      if (ind.unit_type === "text") return false;
      if (
        ind.accumulation_type === "last_value" &&
        formData.scope_level !== "qism"
      ) {
        return false;
      }
      return true;
    });
  }, [indicators, formData.scope_level]);

  // ── دوال الحوار ──
  const openAddDialog = () => {
    setFormData(initialFormData);
    setEditingId(null);
    setDialogOpen(true);
  };

  const openEditDialog = (target: Target) => {
    setFormData({
      scope_level: target.scope_level,
      scope_unit: target.scope_unit,
      indicator: target.indicator,
      year: target.year,
      target_value: target.target_value,
      notes: target.notes || "",
    });
    setEditingId(target.id);
    setDialogOpen(true);
  };

  const closeDialog = () => {
    setDialogOpen(false);
    setFormData(initialFormData);
    setEditingId(null);
    createMutation.reset();
    updateMutation.reset();
  };

  const handleScopeLevelChange = (newLevel: TargetScopeLevel) => {
    setFormData((prev) => ({
      ...prev,
      scope_level: newLevel,
      // مسح الـ scope_unit لأن القائمة ستتغيّر
      scope_unit: newLevel === "institution" ? null : null,
      // لو المؤشر الحالي last_value والمستوى أعلى من قسم، امسح الاختيار
      indicator: prev.indicator,
    }));
  };

  const handleSubmit = () => {
    if (!formData.indicator) return;
    if (formData.scope_level !== "institution" && !formData.scope_unit) return;
    if (formData.target_value <= 0) return;

    const payload = {
      scope_unit:
        formData.scope_level === "institution" ? null : formData.scope_unit,
      indicator: formData.indicator,
      year: formData.year,
      target_value: formData.target_value,
      notes: formData.notes || undefined,
    };

    if (editingId) {
      updateMutation.mutate({ id: editingId, data: payload as Partial<Target> });
    } else {
      createMutation.mutate(payload);
    }
  };

  const handleDeleteClick = (id: number) => {
    setDeletingId(id);
    setDeleteConfirmOpen(true);
  };

  const handleConfirmDelete = () => {
    if (deletingId) deleteMutation.mutate(deletingId);
  };

  const openBreakdown = (id: number) => {
    setBreakdownTargetId(id);
    setBreakdownOpen(true);
  };

  const isMutating = createMutation.isPending || updateMutation.isPending;

  const getScopeUnitsForLevel = (level: TargetScopeLevel): OrganizationUnit[] => {
    if (level === "daira") return dairas;
    if (level === "mudiriya") return mudiriyas;
    if (level === "qism") return qisms;
    return [];
  };

  if (isLoading) return <LoadingSpinner size="lg" />;
  if (isError) return <ErrorState onRetry={() => refetch()} />;

  return (
    <div className="space-y-6">
      {/* العنوان */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            إدارة المستهدفات
          </h1>
          <p className="text-gray-500 mt-1">
            المستهدفات الهرمية: المؤسسة، الدوائر، المديريات، والأقسام
          </p>
        </div>
        <Button onClick={openAddDialog}>
          <Plus className="w-4 h-4 ml-2" />
          إضافة مستهدف
        </Button>
      </div>

      {/* شريط الفلاتر */}
      <div className="bg-white rounded-xl shadow-sm border p-4">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3">
          <div className="relative lg:col-span-2">
            <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <Input
              placeholder="بحث باسم النطاق أو المؤشر أو الملاحظات..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pr-10"
            />
          </div>
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-right"
            dir="rtl"
          >
            <option value="">جميع تصنيفات المؤشرات</option>
            {categories.map((cat: IndicatorCategory) => (
              <option key={cat.id} value={cat.id.toString()}>
                {cat.name}
              </option>
            ))}
          </select>
          <select
            value={scopeLevelFilter}
            onChange={(e) => setScopeLevelFilter(e.target.value)}
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-right"
            dir="rtl"
          >
            <option value="">جميع المستويات</option>
            <option value="institution">المؤسسة كاملة</option>
            <option value="daira">الدوائر</option>
            <option value="mudiriya">المديريات</option>
            <option value="qism">الأقسام</option>
          </select>
          <select
            value={yearFilter}
            onChange={(e) => setYearFilter(e.target.value)}
            className="flex h-10 rounded-md border border-input bg-background px-3 py-2 text-sm"
            dir="ltr"
          >
            {Array.from({ length: 5 }, (_, i) => currentYear - 2 + i).map(
              (year) => (
                <option key={year} value={year.toString()}>
                  {year}
                </option>
              )
            )}
          </select>
        </div>
      </div>

      {/* الجدول */}
      <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
        {filteredTargets.length === 0 ? (
          <EmptyState message="لا توجد مستهدفات مطابقة." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50">
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    المستوى
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    النطاق
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    المؤشر
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    التصنيف
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    السنة
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    القيمة المستهدفة
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700 min-w-[180px]">
                    التقدم
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    إجراءات
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {filteredTargets.map((target: Target) => {
                  const Icon = SCOPE_LEVEL_ICONS[target.scope_level];
                  const colorClass = SCOPE_LEVEL_COLORS[target.scope_level];
                  const canShowBreakdown = target.scope_level !== "qism";

                  return (
                    <tr
                      key={target.id}
                      className="hover:bg-gray-50 transition"
                    >
                      <td className="py-3 px-4">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium border ${colorClass}`}
                        >
                          <Icon className="w-3 h-3" />
                          {SCOPE_LEVEL_LABELS[target.scope_level]}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-medium text-gray-900">
                        {target.scope_unit_name || "المؤسسة كاملة"}
                      </td>
                      <td className="py-3 px-4 text-gray-700">
                        {target.indicator_name}
                      </td>
                      <td className="py-3 px-4">
                        {target.indicator_category_name ? (
                          <span className="inline-block px-2 py-0.5 rounded-md text-xs font-medium bg-gray-100 text-gray-700 border border-gray-200">
                            {target.indicator_category_name}
                          </span>
                        ) : (
                          <span className="text-xs text-gray-400">—</span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-gray-600" dir="ltr">
                        {target.year}
                      </td>
                      <td
                        className="py-3 px-4 font-semibold text-gray-900"
                        dir="ltr"
                      >
                        {target.target_value.toLocaleString("ar-IQ")}
                      </td>
                      <td className="py-3 px-4">
                        {target.progress ? (
                          <div className="space-y-1 min-w-[160px]">
                            <div className="flex items-center justify-between text-xs">
                              <span className="text-gray-600" dir="ltr">
                                {target.progress.cumulative_value.toLocaleString(
                                  "ar-IQ"
                                )}
                                {" / "}
                                {target.progress.target_value.toLocaleString(
                                  "ar-IQ"
                                )}
                              </span>
                              <span
                                className={`font-bold ${
                                  target.progress.progress_percentage >= 100
                                    ? "text-green-600"
                                    : target.progress.progress_percentage >= 75
                                    ? "text-blue-600"
                                    : target.progress.progress_percentage >= 50
                                    ? "text-amber-600"
                                    : "text-red-600"
                                }`}
                                dir="ltr"
                              >
                                {target.progress.progress_percentage}%
                              </span>
                            </div>
                            <div className="w-full bg-gray-100 rounded-full h-2 overflow-hidden">
                              <div
                                className={`h-2 rounded-full transition-all ${
                                  target.progress.progress_percentage >= 100
                                    ? "bg-green-500"
                                    : target.progress.progress_percentage >= 75
                                    ? "bg-blue-500"
                                    : target.progress.progress_percentage >= 50
                                    ? "bg-amber-500"
                                    : "bg-red-500"
                                }`}
                                style={{
                                  width: `${Math.min(
                                    target.progress.progress_percentage,
                                    100
                                  )}%`,
                                }}
                              />
                            </div>
                          </div>
                        ) : (
                          <span className="text-xs text-gray-400">—</span>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-1 flex-wrap">
                          {canShowBreakdown && (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-blue-600 hover:text-blue-700"
                              onClick={() => openBreakdown(target.id)}
                            >
                              <Eye className="w-4 h-4 ml-1" />
                              التفصيل
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openEditDialog(target)}
                          >
                            <Pencil className="w-4 h-4 ml-1" />
                            تعديل
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-red-600 hover:text-red-700"
                            onClick={() => handleDeleteClick(target.id)}
                          >
                            <Trash2 className="w-4 h-4 ml-1" />
                            حذف
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* حوار الإنشاء/التعديل */}
      <Dialog
        open={dialogOpen}
        onOpenChange={(open) => (open ? setDialogOpen(true) : closeDialog())}
      >
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle>
              {editingId ? "تعديل المستهدف" : "إضافة مستهدف جديد"}
            </DialogTitle>
            <DialogDescription>
              اختر المستوى (مؤسسة / دائرة / مديرية / قسم) ثم المؤشر وقيمة المستهدف
            </DialogDescription>
          </DialogHeader>

          {(createMutation.isError || updateMutation.isError) && (
            <div className="bg-red-50 border border-red-200 rounded-md p-3 flex items-start gap-2">
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-red-700">
                {getErrorMessage(
                  createMutation.error || updateMutation.error
                )}
              </p>
            </div>
          )}

          <div className="space-y-4 py-4">
            {/* اختيار المستوى */}
            <div className="space-y-2">
              <Label>مستوى المستهدف</Label>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                {(
                  ["institution", "daira", "mudiriya", "qism"] as const
                ).map((level) => {
                  const Icon = SCOPE_LEVEL_ICONS[level];
                  const isSelected = formData.scope_level === level;
                  return (
                    <button
                      key={level}
                      type="button"
                      onClick={() => handleScopeLevelChange(level)}
                      className={`flex flex-col items-center gap-1 p-2 rounded-md border text-xs transition ${
                        isSelected
                          ? "bg-primary-50 border-primary-400 text-primary-800"
                          : "bg-white border-gray-200 text-gray-600 hover:bg-gray-50"
                      }`}
                    >
                      <Icon className="w-5 h-5" />
                      <span>{SCOPE_LEVEL_LABELS[level]}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* اختيار الوحدة (إن لم يكن مستوى المؤسسة) */}
            {formData.scope_level !== "institution" && (
              <div className="space-y-2">
                <Label htmlFor="target-scope-unit">
                  اختر {SCOPE_LEVEL_LABELS[formData.scope_level]}
                </Label>
                <select
                  id="target-scope-unit"
                  value={formData.scope_unit?.toString() || ""}
                  onChange={(e) =>
                    setFormData((prev) => ({
                      ...prev,
                      scope_unit: e.target.value
                        ? parseInt(e.target.value)
                        : null,
                    }))
                  }
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-right"
                  dir="rtl"
                >
                  <option value="">
                    -- اختر {SCOPE_LEVEL_LABELS[formData.scope_level]} --
                  </option>
                  {getScopeUnitsForLevel(formData.scope_level).map(
                    (unit: OrganizationUnit) => (
                      <option key={unit.id} value={unit.id.toString()}>
                        {unit.name}
                      </option>
                    )
                  )}
                </select>
              </div>
            )}

            {/* المؤشر */}
            <div className="space-y-2">
              <Label htmlFor="target-indicator">المؤشر</Label>
              <select
                id="target-indicator"
                value={formData.indicator?.toString() || ""}
                onChange={(e) =>
                  setFormData((prev) => ({
                    ...prev,
                    indicator: e.target.value
                      ? parseInt(e.target.value)
                      : null,
                  }))
                }
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-right"
                dir="rtl"
              >
                <option value="">اختر المؤشر</option>
                {availableIndicators.map((ind: Indicator) => {
                  const cat = categories.find(
                    (c: IndicatorCategory) => c.id === ind.category
                  );
                  return (
                    <option key={ind.id} value={ind.id.toString()}>
                      {ind.name}
                      {cat ? ` — ${cat.name}` : ""}
                    </option>
                  );
                })}
              </select>
              {formData.scope_level !== "qism" && (
                <p className="text-xs text-gray-500">
                  💡 المؤشرات من نوع "آخر قيمة" و"النصّية" مخفيّة لأنها غير
                  مسموحة على هذا المستوى.
                </p>
              )}
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="target-year">السنة</Label>
                <Input
                  id="target-year"
                  type="number"
                  value={formData.year}
                  onChange={(e) =>
                    setFormData((prev) => ({
                      ...prev,
                      year: parseInt(e.target.value) || currentYear,
                    }))
                  }
                  dir="ltr"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="target-value">القيمة المستهدفة</Label>
                <Input
                  id="target-value"
                  type="number"
                  value={formData.target_value}
                  onChange={(e) =>
                    setFormData((prev) => ({
                      ...prev,
                      target_value: parseFloat(e.target.value) || 0,
                    }))
                  }
                  dir="ltr"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="target-notes">ملاحظات</Label>
              <textarea
                id="target-notes"
                value={formData.notes}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, notes: e.target.value }))
                }
                placeholder="ملاحظات (اختياري)"
                className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-right min-h-[60px]"
                dir="rtl"
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              onClick={handleSubmit}
              disabled={
                isMutating ||
                !formData.indicator ||
                formData.target_value <= 0 ||
                (formData.scope_level !== "institution" && !formData.scope_unit)
              }
            >
              {isMutating
                ? "جارٍ الحفظ..."
                : editingId
                ? "حفظ التعديلات"
                : "إضافة المستهدف"}
            </Button>
            <Button variant="outline" onClick={closeDialog}>
              إلغاء
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* تأكيد الحذف */}
      <ConfirmDialog
        open={deleteConfirmOpen}
        onOpenChange={setDeleteConfirmOpen}
        title="حذف المستهدف"
        description="هل أنت متأكد من حذف هذا المستهدف؟ لا يمكن التراجع."
        confirmLabel="حذف"
        onConfirm={handleConfirmDelete}
        variant="destructive"
        loading={deleteMutation.isPending}
      />

      {/* حوار التفصيل — مساهمة الأقسام */}
      <Dialog
        open={breakdownOpen}
        onOpenChange={(open) => {
          setBreakdownOpen(open);
          if (!open) setBreakdownTargetId(null);
        }}
      >
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-primary-600" />
              تفصيل المستهدف — مساهمة الأقسام
            </DialogTitle>
            <DialogDescription>
              {breakdownData
                ? `${breakdownData.indicator_name} — ${breakdownData.scope_unit_name} — ${breakdownData.year}`
                : "تحميل..."}
            </DialogDescription>
          </DialogHeader>

          {breakdownLoading ? (
            <LoadingSpinner />
          ) : breakdownData ? (
            <div className="space-y-4 py-4">
              {/* ملخص */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="p-3 bg-blue-50 rounded-lg border border-blue-100">
                  <div className="text-xs text-blue-600 mb-1">المستهدف</div>
                  <div
                    className="text-xl font-bold text-blue-900"
                    dir="ltr"
                  >
                    {breakdownData.target_value.toLocaleString("ar-IQ")}
                  </div>
                </div>
                <div className="p-3 bg-green-50 rounded-lg border border-green-100">
                  <div className="text-xs text-green-600 mb-1">المحقّق</div>
                  <div
                    className="text-xl font-bold text-green-900"
                    dir="ltr"
                  >
                    {breakdownData.cumulative_value.toLocaleString("ar-IQ")}
                  </div>
                </div>
                <div className="p-3 bg-amber-50 rounded-lg border border-amber-100">
                  <div className="text-xs text-amber-600 mb-1">النسبة</div>
                  <div
                    className="text-xl font-bold text-amber-900"
                    dir="ltr"
                  >
                    {breakdownData.progress_percentage}%
                  </div>
                </div>
                <div className="p-3 bg-gray-50 rounded-lg border border-gray-100">
                  <div className="text-xs text-gray-600 mb-1">
                    الأقسام في النطاق
                  </div>
                  <div
                    className="text-xl font-bold text-gray-900"
                    dir="ltr"
                  >
                    {breakdownData.qisms_in_scope}
                  </div>
                </div>
              </div>

              {/* شريط التقدّم */}
              <div className="space-y-1">
                <div className="flex justify-between text-xs text-gray-600">
                  <span>التقدّم الإجمالي</span>
                  <span dir="ltr">
                    {breakdownData.cumulative_value} /{" "}
                    {breakdownData.target_value}
                  </span>
                </div>
                <div className="w-full bg-gray-100 rounded-full h-3 overflow-hidden">
                  <div
                    className={`h-3 rounded-full transition-all ${
                      breakdownData.progress_percentage >= 100
                        ? "bg-green-500"
                        : breakdownData.progress_percentage >= 75
                        ? "bg-blue-500"
                        : breakdownData.progress_percentage >= 50
                        ? "bg-amber-500"
                        : "bg-red-500"
                    }`}
                    style={{
                      width: `${Math.min(
                        breakdownData.progress_percentage,
                        100
                      )}%`,
                    }}
                  />
                </div>
              </div>

              {/* شجرة مساهمة الوحدات (قابلة للتوسيع) */}
              {breakdownData.breakdown.length > 0 ? (
                <div className="space-y-2">
                  <div className="text-xs text-gray-500 px-1">
                    💡 اضغط على الدائرة أو المديرية لتوسيع تفصيل أقسامها
                  </div>
                  <div className="bg-gray-50 rounded-lg p-3 space-y-1 max-h-[500px] overflow-y-auto">
                    {breakdownData.breakdown.map((node) => (
                      <BreakdownTreeNode
                        key={node.unit_id}
                        node={node}
                        level={0}
                      />
                    ))}
                  </div>
                </div>
              ) : (
                <EmptyState message="لا توجد بيانات مساهمة." />
              )}
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}
