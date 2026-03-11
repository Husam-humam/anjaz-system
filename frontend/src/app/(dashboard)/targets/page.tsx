"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getTargets, createTarget, updateTarget, deleteTarget } from "@/lib/api/targets";
import { getOrganizationUnits } from "@/lib/api/organization";
import { getIndicators } from "@/lib/api/indicators";
import type { Target } from "@/types/submissions";
import type { OrganizationUnit } from "@/types/organization";
import type { Indicator } from "@/types/indicators";
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
import { Plus, Pencil, Trash2 } from "lucide-react";

interface TargetFormData {
  qism: number | null;
  indicator: number | null;
  year: number;
  target_value: number;
  notes: string;
}

const currentYear = new Date().getFullYear();

const initialFormData: TargetFormData = {
  qism: null,
  indicator: null,
  year: currentYear,
  target_value: 0,
  notes: "",
};

export default function TargetsPage() {
  const queryClient = useQueryClient();
  const [yearFilter, setYearFilter] = useState(currentYear.toString());
  const [dialogOpen, setDialogOpen] = useState(false);
  const [formData, setFormData] = useState<TargetFormData>(initialFormData);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const params: Record<string, string> = {};
  if (yearFilter) params.year = yearFilter;

  const {
    data: targetsData,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["targets", params],
    queryFn: () => getTargets(params),
  });

  const { data: unitsData } = useQuery({
    queryKey: ["organization-units-qism"],
    queryFn: () => getOrganizationUnits({ unit_type: "qism" }),
  });

  const { data: indicatorsData } = useQuery({
    queryKey: ["indicators-active"],
    queryFn: () => getIndicators({ is_active: "true" }),
  });

  const createMutation = useMutation({
    mutationFn: (data: {
      qism: number;
      indicator: number;
      year: number;
      target_value: number;
      notes?: string;
    }) => createTarget(data),
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
    mutationFn: (id: number) => deleteTarget(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["targets"] });
      setDeleteConfirmOpen(false);
      setDeletingId(null);
    },
  });

  const openAddDialog = () => {
    setFormData(initialFormData);
    setEditingId(null);
    setDialogOpen(true);
  };

  const openEditDialog = (target: Target) => {
    setFormData({
      qism: target.qism,
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
  };

  const handleSubmit = () => {
    if (!formData.qism || !formData.indicator) return;

    const payload = {
      qism: formData.qism,
      indicator: formData.indicator,
      year: formData.year,
      target_value: formData.target_value,
      notes: formData.notes || undefined,
    };

    if (editingId) {
      updateMutation.mutate({ id: editingId, data: payload });
    } else {
      createMutation.mutate(payload);
    }
  };

  const handleDeleteClick = (id: number) => {
    setDeletingId(id);
    setDeleteConfirmOpen(true);
  };

  const handleConfirmDelete = () => {
    if (deletingId) {
      deleteMutation.mutate(deletingId);
    }
  };

  const isMutating = createMutation.isPending || updateMutation.isPending;
  const targets = targetsData?.results || [];
  const units = unitsData?.results || [];
  const indicators = indicatorsData?.results || [];

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
          <h1 className="text-2xl font-bold text-gray-900">إدارة المستهدفات</h1>
          <p className="text-gray-500 mt-1">
            تحديد المستهدفات السنوية للأقسام
          </p>
        </div>
        <Button onClick={openAddDialog}>
          <Plus className="w-4 h-4 ml-2" />
          إضافة مستهدف
        </Button>
      </div>

      {/* فلتر السنة */}
      <div className="bg-white rounded-xl shadow-sm border p-4">
        <div className="flex items-center gap-4">
          <Label htmlFor="target-year-filter">السنة:</Label>
          <select
            id="target-year-filter"
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
        {targets.length === 0 ? (
          <EmptyState message="لا توجد مستهدفات لهذه السنة." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50">
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    القسم
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    المؤشر
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    السنة
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    القيمة المستهدفة
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    ملاحظات
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    إجراءات
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {targets.map((target: Target) => (
                  <tr key={target.id} className="hover:bg-gray-50 transition">
                    <td className="py-3 px-4 font-medium text-gray-900">
                      {target.qism_name}
                    </td>
                    <td className="py-3 px-4 text-gray-900">
                      {target.indicator_name}
                    </td>
                    <td className="py-3 px-4 text-gray-600">{target.year}</td>
                    <td className="py-3 px-4 font-semibold text-gray-900" dir="ltr">
                      {target.target_value.toLocaleString("ar-IQ")}
                    </td>
                    <td className="py-3 px-4 text-gray-500 text-xs max-w-[200px] truncate">
                      {target.notes || "—"}
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
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
              {editingId ? "تعديل المستهدف" : "إضافة مستهدف جديد"}
            </DialogTitle>
            <DialogDescription>
              {editingId
                ? "قم بتعديل بيانات المستهدف"
                : "أدخل بيانات المستهدف الجديد"}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="target-qism">القسم</Label>
              <select
                id="target-qism"
                value={formData.qism?.toString() || ""}
                onChange={(e) =>
                  setFormData((prev) => ({
                    ...prev,
                    qism: e.target.value ? parseInt(e.target.value) : null,
                  }))
                }
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-right"
                dir="rtl"
              >
                <option value="">اختر القسم</option>
                {units.map((unit: OrganizationUnit) => (
                  <option key={unit.id} value={unit.id.toString()}>
                    {unit.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="target-indicator">المؤشر</Label>
              <select
                id="target-indicator"
                value={formData.indicator?.toString() || ""}
                onChange={(e) =>
                  setFormData((prev) => ({
                    ...prev,
                    indicator: e.target.value ? parseInt(e.target.value) : null,
                  }))
                }
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-right"
                dir="rtl"
              >
                <option value="">اختر المؤشر</option>
                {indicators.map((ind: Indicator) => (
                  <option key={ind.id} value={ind.id.toString()}>
                    {ind.name}
                  </option>
                ))}
              </select>
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
              disabled={isMutating || !formData.qism || !formData.indicator}
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
        description="هل أنت متأكد من حذف هذا المستهدف؟ لا يمكن التراجع عن هذا الإجراء."
        confirmLabel="حذف"
        onConfirm={handleConfirmDelete}
        variant="destructive"
        loading={deleteMutation.isPending}
      />
    </div>
  );
}
