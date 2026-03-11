"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getFormTemplates,
  createFormTemplate,
  submitFormTemplate,
} from "@/lib/api/forms";
import { getOrganizationUnits } from "@/lib/api/organization";
import { getIndicators } from "@/lib/api/indicators";
import type { FormTemplate, FormTemplateItem } from "@/types/submissions";
import type { OrganizationUnit } from "@/types/organization";
import type { Indicator } from "@/types/indicators";
import { STATUS_LABELS, STATUS_COLORS } from "@/lib/constants";
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
import { Plus, Send, Eye, X } from "lucide-react";
import { formatDate } from "@/lib/utils";

interface NewTemplateItem {
  indicator: number;
  is_mandatory: boolean;
  display_order: number;
}

export default function FormsPage() {
  const queryClient = useQueryClient();
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [detailDialogOpen, setDetailDialogOpen] = useState(false);
  const [submitConfirmOpen, setSubmitConfirmOpen] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<FormTemplate | null>(
    null
  );
  const [submittingId, setSubmittingId] = useState<number | null>(null);
  const [selectedQism, setSelectedQism] = useState<number | null>(null);
  const [templateItems, setTemplateItems] = useState<NewTemplateItem[]>([]);

  const {
    data: templatesData,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["form-templates"],
    queryFn: () => getFormTemplates(),
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
      items: { indicator: number; is_mandatory: boolean; display_order: number }[];
    }) => createFormTemplate(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["form-templates"] });
      setCreateDialogOpen(false);
      setSelectedQism(null);
      setTemplateItems([]);
    },
  });

  const submitMutation = useMutation({
    mutationFn: (id: number) => submitFormTemplate(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["form-templates"] });
      setSubmitConfirmOpen(false);
      setSubmittingId(null);
    },
  });

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
    if (!selectedQism || templateItems.length === 0) return;
    createMutation.mutate({
      qism: selectedQism,
      items: templateItems.map((item) => ({
        indicator: item.indicator,
        is_mandatory: item.is_mandatory,
        display_order: item.display_order,
      })),
    });
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

  const viewDetails = (template: FormTemplate) => {
    setSelectedTemplate(template);
    setDetailDialogOpen(true);
  };

  const templates = templatesData?.results || [];
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
          <h1 className="text-2xl font-bold text-gray-900">نماذج الاستمارات</h1>
          <p className="text-gray-500 mt-1">
            إنشاء وإدارة نماذج الاستمارات الأسبوعية
          </p>
        </div>
        <Button onClick={() => setCreateDialogOpen(true)}>
          <Plus className="w-4 h-4 ml-2" />
          إنشاء استمارة جديدة
        </Button>
      </div>

      {/* الجدول */}
      <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
        {templates.length === 0 ? (
          <EmptyState message="لا توجد نماذج استمارات بعد." />
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
                      <div className="flex items-center gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => viewDetails(template)}
                        >
                          <Eye className="w-4 h-4 ml-1" />
                          تفاصيل
                        </Button>
                        {template.status === "draft" && (
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
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* مربع حوار إنشاء استمارة */}
      <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>إنشاء استمارة جديدة</DialogTitle>
            <DialogDescription>
              اختر القسم وأضف المؤشرات المطلوبة
            </DialogDescription>
          </DialogHeader>

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

            {/* عناصر الاستمارة */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label>المؤشرات</Label>
                <Button variant="outline" size="sm" onClick={addItem}>
                  <Plus className="w-3 h-3 ml-1" />
                  إضافة مؤشر
                </Button>
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
                        {indicators.map((ind: Indicator) => (
                          <option key={ind.id} value={ind.id.toString()}>
                            {ind.name}
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
                !selectedQism ||
                templateItems.length === 0 ||
                templateItems.some((item) => !item.indicator)
              }
            >
              {createMutation.isPending
                ? "جارٍ الإنشاء..."
                : "إنشاء الاستمارة"}
            </Button>
            <Button
              variant="outline"
              onClick={() => setCreateDialogOpen(false)}
            >
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
        onOpenChange={setSubmitConfirmOpen}
        title="إرسال الاستمارة للاعتماد"
        description="هل أنت متأكد من إرسال هذه الاستمارة للاعتماد؟ لن تتمكن من التعديل بعد الإرسال."
        confirmLabel="إرسال"
        onConfirm={handleConfirmSubmit}
        loading={submitMutation.isPending}
      />
    </div>
  );
}
