"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getFormTemplates,
  createFormTemplate,
  updateFormTemplate,
  submitFormTemplate,
  createNewVersion,
  approveFormTemplate,
  rejectFormTemplate,
} from "@/lib/api/forms";
import { getOrganizationUnits } from "@/lib/api/organization";
import { getIndicators, getIndicatorCategories } from "@/lib/api/indicators";
import { useAuthStore } from "@/stores/authStore";
import type { FormTemplate, FormTemplateItem } from "@/types/submissions";
import type { OrganizationUnit } from "@/types/organization";
import type { Indicator, IndicatorCategory } from "@/types/indicators";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { ErrorState } from "@/components/shared/ErrorState";
import { EmptyState } from "@/components/shared/EmptyState";
import { Button } from "@/components/ui/button";
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
import { Plus, Send, Eye, X, Pencil, Copy, AlertCircle, Search, Filter, RotateCcw, CheckCircle, XCircle, Bell } from "lucide-react";
import { formatDate, getErrorMessage } from "@/lib/utils";
import { Input } from "@/components/ui/input";

interface NewTemplateItem {
  indicator: number;
  is_mandatory: boolean;
  display_order: number;
}

export default function FormsPage() {
  const queryClient = useQueryClient();
  const user = useAuthStore((s) => s.user);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [detailDialogOpen, setDetailDialogOpen] = useState(false);
  const [submitConfirmOpen, setSubmitConfirmOpen] = useState(false);
  const [newVersionConfirmOpen, setNewVersionConfirmOpen] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<FormTemplate | null>(
    null
  );
  const [submittingId, setSubmittingId] = useState<number | null>(null);
  const [versioningId, setVersioningId] = useState<number | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [selectedQism, setSelectedQism] = useState<number | null>(null);
  const [templateItems, setTemplateItems] = useState<NewTemplateItem[]>([]);

  // حالات اعتماد/رفض القوالب
  const [approveDialogOpen, setApproveDialogOpen] = useState(false);
  const [rejectDialogOpen, setRejectDialogOpen] = useState(false);
  const [actionTemplateId, setActionTemplateId] = useState<number | null>(null);
  const [effectiveWeek, setEffectiveWeek] = useState("");
  const [effectiveYear, setEffectiveYear] = useState(
    new Date().getFullYear().toString()
  );
  const [rejectReason, setRejectReason] = useState("");

  // فلتر تصنيف وبحث المؤشرات داخل الـ dialog
  const [indicatorCategoryFilter, setIndicatorCategoryFilter] = useState("");
  const [indicatorSearchQuery, setIndicatorSearchQuery] = useState("");

  // أخطاء الإجراءات (إرسال، إنشاء إصدار)
  const [actionError, setActionError] = useState<string | null>(null);

  // ─── حالات الفلاتر ───
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [dairaFilter, setDairaFilter] = useState("");
  const [mudiriyaFilter, setMudiriyaFilter] = useState("");
  const [latestOnly, setLatestOnly] = useState(false);

  // بناء معاملات الاستعلام
  const queryParams: Record<string, string> = {};
  if (searchQuery.trim()) queryParams.search = searchQuery.trim();
  if (statusFilter) queryParams.status = statusFilter;
  if (dairaFilter) queryParams.daira_id = dairaFilter;
  if (mudiriyaFilter) queryParams.mudiriya_id = mudiriyaFilter;
  if (latestOnly) queryParams.latest_only = "true";

  const {
    data: templatesData,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["form-templates", queryParams],
    queryFn: () => getFormTemplates(queryParams),
  });

  const { data: unitsData } = useQuery({
    queryKey: ["organization-units-qism"],
    queryFn: () => getOrganizationUnits({ unit_type: "qism" }),
  });

  // قوائم الدوائر والمديريات للفلاتر
  const { data: dairasData } = useQuery({
    queryKey: ["organization-units-daira"],
    queryFn: () => getOrganizationUnits({ unit_type: "daira" }),
  });

  const { data: mudiriyasData } = useQuery({
    queryKey: ["organization-units-mudiriya", dairaFilter],
    queryFn: () => {
      const params: Record<string, string> = { unit_type: "mudiriya" };
      if (dairaFilter) params.parent = dairaFilter;
      return getOrganizationUnits(params);
    },
  });

  const { data: indicatorsData } = useQuery({
    queryKey: ["indicators-active"],
    queryFn: () => getIndicators({ is_active: "true", page_size: "1000" }),
  });

  const { data: indicatorCategoriesData } = useQuery({
    queryKey: ["indicator-categories"],
    queryFn: () => getIndicatorCategories(),
  });

  const createMutation = useMutation({
    mutationFn: (data: {
      qism: number;
      items: { indicator: number; is_mandatory: boolean; display_order: number }[];
    }) => createFormTemplate(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["form-templates"] });
      closeCreateDialog();
    },
    onError: () => {
      // الخطأ يُعرَض داخل الحوار عبر createMutation.error
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({
      id,
      items,
    }: {
      id: number;
      items: { indicator: number; is_mandatory: boolean; display_order: number }[];
    }) => updateFormTemplate(id, { items }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["form-templates"] });
      closeCreateDialog();
    },
    onError: () => {
      // الخطأ يُعرَض داخل الحوار عبر updateMutation.error
    },
  });

  const submitMutation = useMutation({
    mutationFn: (id: number) => submitFormTemplate(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["form-templates"] });
      setSubmitConfirmOpen(false);
      setSubmittingId(null);
      setActionError(null);
    },
    onError: (err: unknown) => {
      setActionError(getErrorMessage(err));
      setSubmitConfirmOpen(false);
      setSubmittingId(null);
    },
  });

  const newVersionMutation = useMutation({
    mutationFn: (id: number) => createNewVersion(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["form-templates"] });
      setNewVersionConfirmOpen(false);
      setVersioningId(null);
      setActionError(null);
    },
    onError: (err: unknown) => {
      setActionError(getErrorMessage(err));
      setNewVersionConfirmOpen(false);
      setVersioningId(null);
    },
  });

  const approveMutation = useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: number;
      data: { effective_from_week: number; effective_from_year: number };
    }) => approveFormTemplate(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["form-templates"] });
      queryClient.invalidateQueries({
        queryKey: ["sidebar-pending-forms-count"],
      });
      setApproveDialogOpen(false);
      setActionTemplateId(null);
      setEffectiveWeek("");
      setEffectiveYear(new Date().getFullYear().toString());
    },
    onError: () => {
      // الخطأ يُعرَض داخل الحوار عبر approveMutation.error
    },
  });

  const rejectMutation = useMutation({
    mutationFn: ({ id, reason }: { id: number; reason: string }) =>
      rejectFormTemplate(id, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["form-templates"] });
      queryClient.invalidateQueries({
        queryKey: ["sidebar-pending-forms-count"],
      });
      setRejectDialogOpen(false);
      setActionTemplateId(null);
      setRejectReason("");
    },
    onError: () => {
      // الخطأ يُعرَض داخل الحوار عبر rejectMutation.error
    },
  });

  // مساعدات إغلاق الحوارات مع إعادة ضبط الحالة
  const closeApproveDialog = (open: boolean) => {
    setApproveDialogOpen(open);
    if (!open) {
      setActionTemplateId(null);
      setEffectiveWeek("");
      setEffectiveYear(new Date().getFullYear().toString());
      approveMutation.reset();
    }
  };

  const closeRejectDialog = (open: boolean) => {
    setRejectDialogOpen(open);
    if (!open) {
      setActionTemplateId(null);
      setRejectReason("");
      rejectMutation.reset();
    }
  };

  const closeSubmitConfirm = (open: boolean) => {
    setSubmitConfirmOpen(open);
    if (!open) {
      setSubmittingId(null);
    }
  };

  const closeNewVersionConfirm = (open: boolean) => {
    setNewVersionConfirmOpen(open);
    if (!open) {
      setVersioningId(null);
    }
  };

  const closeCreateDialog = () => {
    setCreateDialogOpen(false);
    setSelectedQism(null);
    setTemplateItems([]);
    setEditingId(null);
    setIndicatorCategoryFilter("");
    setIndicatorSearchQuery("");
    createMutation.reset();
    updateMutation.reset();
  };

  const addItem = () => {
    setTemplateItems((prev) => [
      ...prev,
      {
        indicator: 0,
        is_mandatory: true,
        display_order: prev.length + 1,
      },
    ]);
  };

  const removeItem = (index: number) => {
    setTemplateItems((prev) =>
      prev
        .filter((_, i) => i !== index)
        .map((item, i) => ({ ...item, display_order: i + 1 }))
    );
  };

  const updateItem = (
    index: number,
    field: keyof NewTemplateItem,
    value: number | boolean
  ) => {
    setTemplateItems((prev) =>
      prev.map((item, i) => (i === index ? { ...item, [field]: value } : item))
    );
  };

  const handleCreate = () => {
    if (templateItems.length === 0) return;
    const items = templateItems.map((item) => ({
      indicator: item.indicator,
      is_mandatory: item.is_mandatory,
      display_order: item.display_order,
    }));

    if (editingId) {
      // وضع التعديل: لا نُغيّر القسم
      updateMutation.mutate({ id: editingId, items });
    } else {
      // وضع الإنشاء: نحتاج اختيار قسم
      if (!selectedQism) return;
      createMutation.mutate({ qism: selectedQism, items });
    }
  };

  const handleEditClick = (template: FormTemplate) => {
    setEditingId(template.id);
    setSelectedQism(template.qism);
    setTemplateItems(
      (template.items || []).map((item, idx) => ({
        indicator: item.indicator,
        is_mandatory: item.is_mandatory,
        display_order: item.display_order ?? idx + 1,
      }))
    );
    setCreateDialogOpen(true);
  };

  const handleSubmitClick = (id: number) => {
    setSubmittingId(id);
    setSubmitConfirmOpen(true);
  };

  const handleConfirmSubmit = () => {
    if (submittingId) {
      submitMutation.mutate(submittingId);
    }
  };

  const handleNewVersionClick = (id: number) => {
    setVersioningId(id);
    setNewVersionConfirmOpen(true);
  };

  const handleConfirmNewVersion = () => {
    if (versioningId) {
      newVersionMutation.mutate(versioningId);
    }
  };

  const handleApproveClick = (id: number) => {
    setActionTemplateId(id);
    setEffectiveWeek("");
    setEffectiveYear(new Date().getFullYear().toString());
    setApproveDialogOpen(true);
  };

  const handleRejectClick = (id: number) => {
    setActionTemplateId(id);
    setRejectReason("");
    setRejectDialogOpen(true);
  };

  const handleConfirmApprove = () => {
    if (actionTemplateId && effectiveWeek && effectiveYear) {
      approveMutation.mutate({
        id: actionTemplateId,
        data: {
          effective_from_week: parseInt(effectiveWeek),
          effective_from_year: parseInt(effectiveYear),
        },
      });
    }
  };

  const handleConfirmReject = () => {
    if (actionTemplateId && rejectReason.trim()) {
      rejectMutation.mutate({
        id: actionTemplateId,
        reason: rejectReason.trim(),
      });
    }
  };

  const viewDetails = (template: FormTemplate) => {
    setSelectedTemplate(template);
    setDetailDialogOpen(true);
  };

  // الأدوار التي تستطيع إنشاء/تعديل/إرسال القوالب
  const canManageTemplates =
    user?.role === "planning_section" || user?.role === "statistics_admin";

  // الاعتماد/الرفض حصرياً للأدمن (مدير الإحصاء)
  const canApproveOrReject = user?.role === "statistics_admin";

  const templates = templatesData?.results || [];
  const pendingTemplatesCount = templates.filter(
    (t: FormTemplate) => t.status === "pending_approval"
  ).length;
  const units = unitsData?.results || [];
  const indicators = indicatorsData?.results || [];
  const indicatorCategories = indicatorCategoriesData?.results || [];
  const dairas = dairasData?.results || [];
  const mudiriyas = mudiriyasData?.results || [];

  // حساب المؤشرات المتاحة لكل صف من صفوف البنود.
  // القواعد:
  //  - المؤشر المُختار في صف آخر يُستبعد (منع التكرار)
  //  - المؤشر المُختار في الصف الحالي يبقى ظاهراً دائماً (حتى لا يضيع الاختيار)
  //  - الفلتر النصّي والتصنيف يُطبّقان فقط على المؤشرات غير المُختارة في الصف الحالي
  const getIndicatorsForRow = (rowIndex: number): Indicator[] => {
    const currentSelection = templateItems[rowIndex]?.indicator ?? 0;
    // معرّفات المؤشرات المُختارة في الصفوف الأخرى (لاستبعادها)
    const takenByOtherRows = new Set(
      templateItems
        .map((it, idx) => (idx !== rowIndex ? it.indicator : 0))
        .filter((id) => id > 0)
    );
    const trimmedSearch = indicatorSearchQuery.trim().toLowerCase();

    return indicators.filter((ind: Indicator) => {
      // المؤشر الخاص بهذا الصف يظهر دائماً (لإظهار الاختيار الحالي)
      if (ind.id === currentSelection) return true;
      // استبعاد المُختار في صفوف أخرى
      if (takenByOtherRows.has(ind.id)) return false;
      // تطبيق فلتر التصنيف
      if (
        indicatorCategoryFilter &&
        ind.category?.toString() !== indicatorCategoryFilter
      ) {
        return false;
      }
      // تطبيق فلتر البحث النصّي
      if (trimmedSearch && !ind.name.toLowerCase().includes(trimmedSearch)) {
        return false;
      }
      return true;
    });
  };

  const resetFilters = () => {
    setSearchQuery("");
    setStatusFilter("");
    setDairaFilter("");
    setMudiriyaFilter("");
    setLatestOnly(false);
  };

  const hasActiveFilters =
    searchQuery || statusFilter || dairaFilter || mudiriyaFilter || latestOnly;

  if (isLoading) {
    return <LoadingSpinner size="lg" />;
  }

  if (isError) {
    return <ErrorState onRetry={() => refetch()} />;
  }

  return (
    <div className="space-y-6">
      {/* العنوان */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">نماذج الاستمارات</h1>
          <p className="text-gray-500 mt-1">
            إنشاء وإدارة نماذج الاستمارات الأسبوعية
          </p>
        </div>
        {canManageTemplates && (
          <Button onClick={() => setCreateDialogOpen(true)}>
            <Plus className="w-4 h-4 ml-2" />
            إنشاء استمارة جديدة
          </Button>
        )}
      </div>

      {/* بانر أخطاء الإجراءات (إرسال، إصدار جديد) */}
      {actionError && (
        <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 flex items-start gap-2">
          <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-red-700 break-words flex-1">{actionError}</p>
          <button
            type="button"
            onClick={() => setActionError(null)}
            className="text-red-500 hover:text-red-700 text-sm"
          >
            ×
          </button>
        </div>
      )}

      {/* شريط تنبيه: قوالب بانتظار الاعتماد */}
      {canManageTemplates && pendingTemplatesCount > 0 && (
        <div className="bg-amber-50 border-r-4 border-amber-500 border border-amber-200 rounded-lg px-4 py-3 flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-3">
            <Bell className="w-5 h-5 text-amber-600 flex-shrink-0" />
            <span className="text-amber-900 text-sm font-medium">
              يوجد {pendingTemplatesCount}{" "}
              {pendingTemplatesCount === 1 ? "قالب" : "قوالب"} بانتظار الاعتماد
            </span>
          </div>
          <Button
            variant="outline"
            size="sm"
            className="bg-white border-amber-300 text-amber-800 hover:bg-amber-100"
            onClick={() => setStatusFilter("pending_approval")}
          >
            عرض القوالب المعلّقة فقط
          </Button>
        </div>
      )}

      {/* شريط الفلاتر */}
      <div className="bg-white rounded-xl shadow-sm border p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2 text-gray-700">
            <Filter className="w-4 h-4" />
            <span className="text-sm font-medium">الفلاتر والبحث</span>
          </div>
          {hasActiveFilters && (
            <Button variant="ghost" size="sm" onClick={resetFilters}>
              <RotateCcw className="w-3.5 h-3.5 ml-1" />
              مسح الفلاتر
            </Button>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {/* بحث بالاسم/الرمز */}
          <div className="relative md:col-span-2">
            <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <Input
              placeholder="بحث باسم القسم أو الرمز أو الملاحظات..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pr-10"
            />
          </div>

          {/* الدائرة */}
          <select
            value={dairaFilter}
            onChange={(e) => {
              setDairaFilter(e.target.value);
              setMudiriyaFilter(""); // إعادة ضبط المديرية عند تغيير الدائرة
            }}
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-right"
            dir="rtl"
          >
            <option value="">جميع الدوائر</option>
            {dairas.map((d: OrganizationUnit) => (
              <option key={d.id} value={d.id.toString()}>
                {d.name}
              </option>
            ))}
          </select>

          {/* المديرية */}
          <select
            value={mudiriyaFilter}
            onChange={(e) => setMudiriyaFilter(e.target.value)}
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-right"
            dir="rtl"
          >
            <option value="">جميع المديريات</option>
            {mudiriyas.map((m: OrganizationUnit) => (
              <option key={m.id} value={m.id.toString()}>
                {m.name}
              </option>
            ))}
          </select>

          {/* الحالة */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-right"
            dir="rtl"
          >
            <option value="">جميع الحالات</option>
            <option value="draft">مسودة</option>
            <option value="pending_approval">بانتظار الاعتماد</option>
            <option value="approved">معتمد</option>
            <option value="rejected">مرفوض</option>
            <option value="superseded">مُستبدَل</option>
          </select>

          {/* أحدث إصدار فقط */}
          <label className="flex items-center gap-2 px-3 py-2 border rounded-md cursor-pointer hover:bg-gray-50 lg:col-span-2">
            <input
              type="checkbox"
              checked={latestOnly}
              onChange={(e) => setLatestOnly(e.target.checked)}
              className="w-4 h-4"
            />
            <span className="text-sm text-gray-700">
              عرض أحدث إصدار فقط لكل قسم
            </span>
          </label>
        </div>

        {/* عدّاد النتائج */}
        <div className="mt-3 text-xs text-gray-500">
          {isLoading
            ? "جارٍ التحميل..."
            : `تم عرض ${templates.length} ${templates.length === 1 ? "قالب" : "قوالب"}${
                templatesData?.count !== undefined && templatesData.count !== templates.length
                  ? ` من أصل ${templatesData.count}`
                  : ""
              }`}
        </div>
      </div>

      {/* الجدول */}
      <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
        {templates.length === 0 ? (
          <EmptyState message="لا توجد نماذج استمارات مطابقة لمعايير البحث." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50">
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    القسم
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    الإصدار
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    الحالة
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    تاريخ التفعيل
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    عدد المؤشرات
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    تاريخ الإنشاء
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    إجراءات
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {templates.map((template: FormTemplate) => (
                  <tr key={template.id} className="hover:bg-gray-50 transition">
                    <td className="py-3 px-4 font-medium text-gray-900">
                      {template.qism_name}
                    </td>
                    <td className="py-3 px-4 text-gray-600">
                      الإصدار {template.version}
                    </td>
                    <td className="py-3 px-4">
                      <StatusBadge status={template.status} />
                    </td>
                    <td className="py-3 px-4 text-gray-600">
                      {template.effective_from_week
                        ? `الأسبوع ${template.effective_from_week} / ${template.effective_from_year}`
                        : "—"}
                    </td>
                    <td className="py-3 px-4 text-gray-600">
                      {template.items?.length || 0} مؤشر
                    </td>
                    <td className="py-3 px-4 text-gray-500 text-xs">
                      {formatDate(template.created_at)}
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2 flex-wrap">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => viewDetails(template)}
                        >
                          <Eye className="w-4 h-4 ml-1" />
                          تفاصيل
                        </Button>
                        {/* تعديل: متاح فقط في المسودة */}
                        {canManageTemplates && template.status === "draft" && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-amber-600 hover:text-amber-700"
                            onClick={() => handleEditClick(template)}
                          >
                            <Pencil className="w-4 h-4 ml-1" />
                            تعديل
                          </Button>
                        )}
                        {/* إرسال للاعتماد: متاح في المسودة */}
                        {canManageTemplates && template.status === "draft" && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-blue-600 hover:text-blue-700"
                            onClick={() => handleSubmitClick(template.id)}
                          >
                            <Send className="w-4 h-4 ml-1" />
                            إرسال للاعتماد
                          </Button>
                        )}
                        {/* اعتماد: حصرياً للأدمن في حالة بانتظار الاعتماد */}
                        {canApproveOrReject &&
                          template.status === "pending_approval" && (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-green-600 hover:text-green-700"
                              onClick={() => handleApproveClick(template.id)}
                            >
                              <CheckCircle className="w-4 h-4 ml-1" />
                              اعتماد
                            </Button>
                          )}
                        {/* رفض: حصرياً للأدمن في حالة بانتظار الاعتماد */}
                        {canApproveOrReject &&
                          template.status === "pending_approval" && (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-red-600 hover:text-red-700"
                              onClick={() => handleRejectClick(template.id)}
                            >
                              <XCircle className="w-4 h-4 ml-1" />
                              رفض
                            </Button>
                          )}
                        {/* إصدار جديد: متاح فقط للقالب المعتمد */}
                        {canManageTemplates && template.status === "approved" && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-purple-600 hover:text-purple-700"
                            onClick={() => handleNewVersionClick(template.id)}
                          >
                            <Copy className="w-4 h-4 ml-1" />
                            إصدار جديد
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* مربع حوار إنشاء/تعديل استمارة */}
      <Dialog
        open={createDialogOpen}
        onOpenChange={(open) => (open ? setCreateDialogOpen(true) : closeCreateDialog())}
      >
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>
              {editingId ? "تعديل الاستمارة" : "إنشاء استمارة جديدة"}
            </DialogTitle>
            <DialogDescription>
              {editingId
                ? "تعديل بنود الاستمارة (مسموح فقط في حالة المسودة)"
                : "اختر القسم وأضف المؤشرات المطلوبة"}
            </DialogDescription>
          </DialogHeader>

          {(createMutation.isError || updateMutation.isError) && (
            <div className="bg-red-50 border border-red-200 rounded-md p-3 flex items-start gap-2">
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-red-700">
                {getErrorMessage(createMutation.error || updateMutation.error)}
              </p>
            </div>
          )}

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="form-qism">القسم</Label>
              <select
                id="form-qism"
                value={selectedQism?.toString() || ""}
                onChange={(e) =>
                  setSelectedQism(
                    e.target.value ? parseInt(e.target.value) : null
                  )
                }
                disabled={!!editingId}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-right disabled:opacity-60 disabled:cursor-not-allowed"
                dir="rtl"
              >
                <option value="">اختر القسم</option>
                {units.map((unit: OrganizationUnit) => (
                  <option key={unit.id} value={unit.id.toString()}>
                    {unit.name}
                  </option>
                ))}
              </select>
              {editingId && (
                <p className="text-xs text-gray-500">
                  لا يمكن تغيير القسم عند التعديل
                </p>
              )}
            </div>

            {/* عناصر الاستمارة */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label>المؤشرات</Label>
                <Button variant="outline" size="sm" onClick={addItem}>
                  <Plus className="w-3 h-3 ml-1" />
                  إضافة مؤشر
                </Button>
              </div>

              {/* فلتر المؤشرات (تصنيف + بحث) */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 p-2 bg-blue-50/50 border border-blue-100 rounded-md">
                <select
                  value={indicatorCategoryFilter}
                  onChange={(e) => setIndicatorCategoryFilter(e.target.value)}
                  className="flex h-9 w-full rounded-md border border-input bg-background px-2 py-1 text-sm text-right"
                  dir="rtl"
                >
                  <option value="">جميع التصنيفات</option>
                  {indicatorCategories.map((cat: IndicatorCategory) => (
                    <option key={cat.id} value={cat.id.toString()}>
                      {cat.name}
                    </option>
                  ))}
                </select>
                <div className="relative">
                  <Search className="absolute right-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400" />
                  <Input
                    placeholder="بحث باسم المؤشر..."
                    value={indicatorSearchQuery}
                    onChange={(e) => setIndicatorSearchQuery(e.target.value)}
                    className="h-9 pr-8 text-sm"
                  />
                </div>
                <p className="text-xs text-gray-500 md:col-span-2">
                  💡 الفلتر يُطبَّق على المؤشرات الجديدة فقط — المؤشرات المُختارة بالفعل تبقى ظاهرة. يمكنك تغيير الفلتر لإضافة مؤشرات من تصنيفات أخرى.
                </p>
              </div>

              {templateItems.length === 0 ? (
                <p className="text-sm text-gray-500 text-center py-4 border border-dashed rounded-lg">
                  لم يتم إضافة مؤشرات بعد. اضغط على &quot;إضافة مؤشر&quot;
                  للبدء.
                </p>
              ) : (
                <div className="space-y-2 max-h-[300px] overflow-y-auto">
                  {templateItems.map((item, index) => (
                    <div
                      key={index}
                      className="flex items-center gap-3 p-3 border rounded-lg bg-gray-50"
                    >
                      <span className="text-xs font-semibold text-gray-400 w-6">
                        {index + 1}
                      </span>
                      <select
                        value={item.indicator.toString()}
                        onChange={(e) =>
                          updateItem(
                            index,
                            "indicator",
                            parseInt(e.target.value)
                          )
                        }
                        className="flex-1 h-9 rounded-md border border-input bg-background px-2 py-1 text-sm text-right"
                        dir="rtl"
                      >
                        <option value="0">اختر المؤشر</option>
                        {getIndicatorsForRow(index).map((ind: Indicator) => (
                          <option key={ind.id} value={ind.id.toString()}>
                            {ind.name}
                            {ind.category_name ? ` — ${ind.category_name}` : ""}
                          </option>
                        ))}
                      </select>
                      <label className="flex items-center gap-1 text-xs whitespace-nowrap">
                        <input
                          type="checkbox"
                          checked={item.is_mandatory}
                          onChange={(e) =>
                            updateItem(
                              index,
                              "is_mandatory",
                              e.target.checked
                            )
                          }
                          className="w-3.5 h-3.5"
                        />
                        إلزامي
                      </label>
                      <button
                        onClick={() => removeItem(index)}
                        className="text-red-500 hover:text-red-700 p-1"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          <DialogFooter>
            <Button
              onClick={handleCreate}
              disabled={
                createMutation.isPending ||
                updateMutation.isPending ||
                !selectedQism ||
                templateItems.length === 0 ||
                templateItems.some((item) => !item.indicator)
              }
            >
              {createMutation.isPending || updateMutation.isPending
                ? "جارٍ الحفظ..."
                : editingId
                ? "حفظ التعديلات"
                : "إنشاء الاستمارة"}
            </Button>
            <Button variant="outline" onClick={closeCreateDialog}>
              إلغاء
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* مربع حوار التفاصيل */}
      <Dialog open={detailDialogOpen} onOpenChange={setDetailDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>تفاصيل الاستمارة</DialogTitle>
            <DialogDescription>
              {selectedTemplate?.qism_name} — الإصدار{" "}
              {selectedTemplate?.version}
            </DialogDescription>
          </DialogHeader>

          {selectedTemplate && (
            <div className="space-y-4 py-4">
              <div className="flex items-center gap-3">
                <span className="text-sm text-gray-500">الحالة:</span>
                <StatusBadge status={selectedTemplate.status} />
              </div>

              {selectedTemplate.effective_from_week && (
                <div className="text-sm text-gray-600">
                  تاريخ التفعيل: الأسبوع{" "}
                  {selectedTemplate.effective_from_week} /{" "}
                  {selectedTemplate.effective_from_year}
                </div>
              )}

              <div className="border rounded-lg overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-gray-50">
                      <th className="text-right py-2 px-3 font-semibold text-gray-700">
                        #
                      </th>
                      <th className="text-right py-2 px-3 font-semibold text-gray-700">
                        المؤشر
                      </th>
                      <th className="text-right py-2 px-3 font-semibold text-gray-700">
                        إلزامي
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {selectedTemplate.items?.map(
                      (item: FormTemplateItem, idx: number) => (
                        <tr key={item.id}>
                          <td className="py-2 px-3 text-gray-500">
                            {idx + 1}
                          </td>
                          <td className="py-2 px-3 text-gray-900">
                            {item.indicator_name}
                          </td>
                          <td className="py-2 px-3">
                            {item.is_mandatory ? (
                              <span className="text-green-600 font-medium">
                                نعم
                              </span>
                            ) : (
                              <span className="text-gray-400">لا</span>
                            )}
                          </td>
                        </tr>
                      )
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* تأكيد الإرسال */}
      <ConfirmDialog
        open={submitConfirmOpen}
        onOpenChange={closeSubmitConfirm}
        title="إرسال الاستمارة للاعتماد"
        description="هل أنت متأكد من إرسال هذه الاستمارة للاعتماد؟ لن تتمكن من التعديل بعد الإرسال."
        confirmLabel="إرسال"
        onConfirm={handleConfirmSubmit}
        loading={submitMutation.isPending}
      />

      {/* مربع حوار الاعتماد */}
      <Dialog open={approveDialogOpen} onOpenChange={closeApproveDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>اعتماد الاستمارة</DialogTitle>
            <DialogDescription>
              حدد أسبوع بداية تفعيل هذه الاستمارة
            </DialogDescription>
          </DialogHeader>

          {approveMutation.isError && (
            <div className="bg-red-50 border border-red-200 rounded-md p-3 flex items-start gap-2">
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-red-700">
                {getErrorMessage(approveMutation.error)}
              </p>
            </div>
          )}

          <div className="space-y-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="eff-year">سنة التفعيل</Label>
                <Input
                  id="eff-year"
                  type="number"
                  value={effectiveYear}
                  onChange={(e) => setEffectiveYear(e.target.value)}
                  dir="ltr"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="eff-week">أسبوع التفعيل</Label>
                <Input
                  id="eff-week"
                  type="number"
                  min={1}
                  max={53}
                  value={effectiveWeek}
                  onChange={(e) => setEffectiveWeek(e.target.value)}
                  dir="ltr"
                  placeholder="رقم الأسبوع"
                />
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button
              onClick={handleConfirmApprove}
              disabled={
                approveMutation.isPending || !effectiveWeek || !effectiveYear
              }
              className="bg-green-600 hover:bg-green-700"
            >
              {approveMutation.isPending ? "جارٍ الاعتماد..." : "اعتماد"}
            </Button>
            <Button
              variant="outline"
              onClick={() => closeApproveDialog(false)}
            >
              إلغاء
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* مربع حوار الرفض */}
      <Dialog open={rejectDialogOpen} onOpenChange={closeRejectDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>رفض الاستمارة</DialogTitle>
            <DialogDescription>
              يرجى إدخال سبب رفض هذه الاستمارة
            </DialogDescription>
          </DialogHeader>

          {rejectMutation.isError && (
            <div className="bg-red-50 border border-red-200 rounded-md p-3 flex items-start gap-2">
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-red-700">
                {getErrorMessage(rejectMutation.error)}
              </p>
            </div>
          )}

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="reject-reason">سبب الرفض</Label>
              <textarea
                id="reject-reason"
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="اكتب سبب الرفض..."
                className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-right min-h-[100px]"
                dir="rtl"
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              onClick={handleConfirmReject}
              disabled={rejectMutation.isPending || !rejectReason.trim()}
              variant="destructive"
            >
              {rejectMutation.isPending ? "جارٍ الرفض..." : "رفض الاستمارة"}
            </Button>
            <Button
              variant="outline"
              onClick={() => closeRejectDialog(false)}
            >
              إلغاء
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* تأكيد إنشاء إصدار جديد */}
      <ConfirmDialog
        open={newVersionConfirmOpen}
        onOpenChange={closeNewVersionConfirm}
        title="إنشاء إصدار جديد"
        description="سيتم إنشاء نسخة جديدة (مسودة) من هذه الاستمارة بكامل بنودها. تستطيع تعديلها ثم تقديمها للاعتماد. الإصدار الحالي يبقى ساري المفعول حتى يُعتمد الجديد. هل تريد المتابعة؟"
        confirmLabel="إنشاء إصدار جديد"
        onConfirm={handleConfirmNewVersion}
        loading={newVersionMutation.isPending}
      />
    </div>
  );
}
