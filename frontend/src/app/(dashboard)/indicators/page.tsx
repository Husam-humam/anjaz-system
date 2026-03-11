"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getIndicators,
  getIndicatorCategories,
  createIndicator,
  updateIndicator,
} from "@/lib/api/indicators";
import type { Indicator, IndicatorCategory } from "@/types/indicators";
import { UNIT_TYPE_LABELS, ACCUMULATION_TYPE_LABELS } from "@/lib/constants";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { ErrorState } from "@/components/shared/ErrorState";
import { EmptyState } from "@/components/shared/EmptyState";
import { StatusBadge } from "@/components/shared/StatusBadge";
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
import { Plus, Search, Pencil } from "lucide-react";

interface IndicatorFormData {
  name: string;
  description: string;
  unit_type: Indicator["unit_type"];
  accumulation_type: Indicator["accumulation_type"];
  category: number | null;
}

const initialFormData: IndicatorFormData = {
  name: "",
  description: "",
  unit_type: "number",
  accumulation_type: "sum",
  category: null,
};

export default function IndicatorsPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [unitTypeFilter, setUnitTypeFilter] = useState("");
  const [activeFilter, setActiveFilter] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [formData, setFormData] = useState<IndicatorFormData>(initialFormData);
  const [editingId, setEditingId] = useState<number | null>(null);

  const params: Record<string, string> = {};
  if (search) params.search = search;
  if (categoryFilter) params.category = categoryFilter;
  if (unitTypeFilter) params.unit_type = unitTypeFilter;
  if (activeFilter) params.is_active = activeFilter;

  const {
    data: indicatorsData,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["indicators", params],
    queryFn: () => getIndicators(params),
  });

  const { data: categoriesData } = useQuery({
    queryKey: ["indicator-categories"],
    queryFn: () => getIndicatorCategories(),
  });

  const createMutation = useMutation({
    mutationFn: (data: Partial<Indicator>) => createIndicator(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["indicators"] });
      closeDialog();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<Indicator> }) =>
      updateIndicator(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["indicators"] });
      closeDialog();
    },
  });

  const openAddDialog = () => {
    setFormData(initialFormData);
    setEditingId(null);
    setDialogOpen(true);
  };

  const openEditDialog = (indicator: Indicator) => {
    setFormData({
      name: indicator.name,
      description: indicator.description,
      unit_type: indicator.unit_type,
      accumulation_type: indicator.accumulation_type,
      category: indicator.category,
    });
    setEditingId(indicator.id);
    setDialogOpen(true);
  };

  const closeDialog = () => {
    setDialogOpen(false);
    setFormData(initialFormData);
    setEditingId(null);
  };

  const handleSubmit = () => {
    const payload: Partial<Indicator> = {
      name: formData.name,
      description: formData.description,
      unit_type: formData.unit_type,
      accumulation_type: formData.accumulation_type,
      category: formData.category,
    };

    if (editingId) {
      updateMutation.mutate({ id: editingId, data: payload });
    } else {
      createMutation.mutate(payload);
    }
  };

  const isMutating = createMutation.isPending || updateMutation.isPending;
  const indicators = indicatorsData?.results || [];
  const categories = categoriesData?.results || [];

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
          <h1 className="text-2xl font-bold text-gray-900">بنك المؤشرات</h1>
          <p className="text-gray-500 mt-1">إدارة المؤشرات الإحصائية</p>
        </div>
        <Button onClick={openAddDialog}>
          <Plus className="w-4 h-4 ml-2" />
          إضافة مؤشر
        </Button>
      </div>

      {/* الفلاتر */}
      <div className="bg-white rounded-xl shadow-sm border p-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="relative">
            <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <Input
              placeholder="بحث عن مؤشر..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pr-10"
            />
          </div>
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-right"
            dir="rtl"
          >
            <option value="">جميع التصنيفات</option>
            {categories.map((cat: IndicatorCategory) => (
              <option key={cat.id} value={cat.id.toString()}>
                {cat.name}
              </option>
            ))}
          </select>
          <select
            value={unitTypeFilter}
            onChange={(e) => setUnitTypeFilter(e.target.value)}
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-right"
            dir="rtl"
          >
            <option value="">جميع وحدات القياس</option>
            {Object.entries(UNIT_TYPE_LABELS).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
          <select
            value={activeFilter}
            onChange={(e) => setActiveFilter(e.target.value)}
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-right"
            dir="rtl"
          >
            <option value="">الكل</option>
            <option value="true">نشط</option>
            <option value="false">غير نشط</option>
          </select>
        </div>
      </div>

      {/* الجدول */}
      <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
        {indicators.length === 0 ? (
          <EmptyState message="لا توجد مؤشرات مطابقة لمعايير البحث." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50">
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    اسم المؤشر
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    التصنيف
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    وحدة القياس
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    طريقة التجميع
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    الحالة
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    إجراءات
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {indicators.map((indicator: Indicator) => (
                  <tr key={indicator.id} className="hover:bg-gray-50 transition">
                    <td className="py-3 px-4">
                      <div>
                        <span className="font-medium text-gray-900">
                          {indicator.name}
                        </span>
                        {indicator.description && (
                          <p className="text-xs text-gray-500 mt-0.5 line-clamp-1">
                            {indicator.description}
                          </p>
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-4 text-gray-600">
                      {indicator.category_name || "—"}
                    </td>
                    <td className="py-3 px-4 text-gray-600">
                      {UNIT_TYPE_LABELS[indicator.unit_type] || indicator.unit_type}
                    </td>
                    <td className="py-3 px-4 text-gray-600">
                      {ACCUMULATION_TYPE_LABELS[indicator.accumulation_type] ||
                        indicator.accumulation_type}
                    </td>
                    <td className="py-3 px-4">
                      <StatusBadge
                        status={indicator.is_active ? "approved" : "rejected"}
                      />
                    </td>
                    <td className="py-3 px-4">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => openEditDialog(indicator)}
                      >
                        <Pencil className="w-4 h-4 ml-1" />
                        تعديل
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* مربع حوار الإضافة/التعديل */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editingId ? "تعديل المؤشر" : "إضافة مؤشر جديد"}
            </DialogTitle>
            <DialogDescription>
              {editingId
                ? "قم بتعديل بيانات المؤشر"
                : "أدخل بيانات المؤشر الجديد"}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="ind-name">اسم المؤشر</Label>
              <Input
                id="ind-name"
                value={formData.name}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, name: e.target.value }))
                }
                placeholder="أدخل اسم المؤشر"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="ind-desc">الوصف</Label>
              <textarea
                id="ind-desc"
                value={formData.description}
                onChange={(e) =>
                  setFormData((prev) => ({
                    ...prev,
                    description: e.target.value,
                  }))
                }
                placeholder="وصف المؤشر (اختياري)"
                className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-right min-h-[80px]"
                dir="rtl"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="ind-unit">وحدة القياس</Label>
                <select
                  id="ind-unit"
                  value={formData.unit_type}
                  onChange={(e) =>
                    setFormData((prev) => ({
                      ...prev,
                      unit_type: e.target.value as Indicator["unit_type"],
                    }))
                  }
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-right"
                  dir="rtl"
                >
                  {Object.entries(UNIT_TYPE_LABELS).map(([key, label]) => (
                    <option key={key} value={key}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="ind-acc">طريقة التجميع</Label>
                <select
                  id="ind-acc"
                  value={formData.accumulation_type}
                  onChange={(e) =>
                    setFormData((prev) => ({
                      ...prev,
                      accumulation_type: e.target
                        .value as Indicator["accumulation_type"],
                    }))
                  }
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-right"
                  dir="rtl"
                >
                  {Object.entries(ACCUMULATION_TYPE_LABELS).map(([key, label]) => (
                    <option key={key} value={key}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="ind-cat">التصنيف</Label>
              <select
                id="ind-cat"
                value={formData.category?.toString() || ""}
                onChange={(e) =>
                  setFormData((prev) => ({
                    ...prev,
                    category: e.target.value ? parseInt(e.target.value) : null,
                  }))
                }
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-right"
                dir="rtl"
              >
                <option value="">بدون تصنيف</option>
                {categories.map((cat: IndicatorCategory) => (
                  <option key={cat.id} value={cat.id.toString()}>
                    {cat.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <DialogFooter>
            <Button onClick={handleSubmit} disabled={isMutating || !formData.name}>
              {isMutating
                ? "جارٍ الحفظ..."
                : editingId
                ? "حفظ التعديلات"
                : "إضافة المؤشر"}
            </Button>
            <Button variant="outline" onClick={closeDialog}>
              إلغاء
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
