"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getPeriods,
  createPeriod,
  closePeriod,
  getCompliance,
} from "@/lib/api/submissions";
import type { WeeklyPeriod } from "@/types/submissions";
import type { ComplianceData } from "@/lib/api/submissions";
import { STATUS_LABELS, STATUS_COLORS } from "@/lib/constants";
import { StatusBadge } from "@/components/shared/StatusBadge";
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
import { Plus, Lock, Eye } from "lucide-react";
import { formatDate, formatDateTime } from "@/lib/utils";

interface PeriodFormData {
  year: number;
  week_number: number;
  start_date: string;
  end_date: string;
  deadline: string;
}

export default function PeriodsPage() {
  const queryClient = useQueryClient();
  const currentYear = new Date().getFullYear();
  const [yearFilter, setYearFilter] = useState(currentYear.toString());
  const [dialogOpen, setDialogOpen] = useState(false);
  const [closeConfirmOpen, setCloseConfirmOpen] = useState(false);
  const [closingPeriodId, setClosingPeriodId] = useState<number | null>(null);
  const [complianceDialogOpen, setComplianceDialogOpen] = useState(false);
  const [selectedPeriodId, setSelectedPeriodId] = useState<number | null>(null);
  const [formData, setFormData] = useState<PeriodFormData>({
    year: currentYear,
    week_number: 1,
    start_date: "",
    end_date: "",
    deadline: "",
  });

  const params: Record<string, string> = {};
  if (yearFilter) params.year = yearFilter;

  const {
    data: periodsData,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["periods", params],
    queryFn: () => getPeriods(params),
  });

  const { data: complianceData, isLoading: complianceLoading } = useQuery({
    queryKey: ["compliance", selectedPeriodId],
    queryFn: () => getCompliance(selectedPeriodId!),
    enabled: !!selectedPeriodId && complianceDialogOpen,
  });

  const createMutation = useMutation({
    mutationFn: (data: PeriodFormData) => createPeriod(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["periods"] });
      setDialogOpen(false);
      resetForm();
    },
  });

  const closeMutation = useMutation({
    mutationFn: (id: number) => closePeriod(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["periods"] });
      setCloseConfirmOpen(false);
      setClosingPeriodId(null);
    },
  });

  const resetForm = () => {
    setFormData({
      year: currentYear,
      week_number: 1,
      start_date: "",
      end_date: "",
      deadline: "",
    });
  };

  const handleCreate = () => {
    createMutation.mutate(formData);
  };

  const handleCloseClick = (id: number) => {
    setClosingPeriodId(id);
    setCloseConfirmOpen(true);
  };

  const handleConfirmClose = () => {
    if (closingPeriodId) {
      closeMutation.mutate(closingPeriodId);
    }
  };

  const openComplianceView = (periodId: number) => {
    setSelectedPeriodId(periodId);
    setComplianceDialogOpen(true);
  };

  const periods = periodsData?.results || [];

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
          <h1 className="text-2xl font-bold text-gray-900">
            إدارة الفترات الأسبوعية
          </h1>
          <p className="text-gray-500 mt-1">
            فتح وإغلاق الأسابيع ومتابعة الالتزام
          </p>
        </div>
        <Button onClick={() => setDialogOpen(true)}>
          <Plus className="w-4 h-4 ml-2" />
          فتح أسبوع جديد
        </Button>
      </div>

      {/* فلتر السنة */}
      <div className="bg-white rounded-xl shadow-sm border p-4">
        <div className="flex items-center gap-4">
          <Label htmlFor="year-filter">السنة:</Label>
          <select
            id="year-filter"
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
        {periods.length === 0 ? (
          <EmptyState message="لا توجد فترات أسبوعية لهذه السنة." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50">
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    السنة
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    رقم الأسبوع
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    تاريخ البداية
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    تاريخ النهاية
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    الموعد النهائي
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
                {periods.map((period: WeeklyPeriod) => (
                  <tr key={period.id} className="hover:bg-gray-50 transition">
                    <td className="py-3 px-4 text-gray-900">{period.year}</td>
                    <td className="py-3 px-4 font-medium text-gray-900">
                      الأسبوع {period.week_number}
                    </td>
                    <td className="py-3 px-4 text-gray-600">
                      {formatDate(period.start_date)}
                    </td>
                    <td className="py-3 px-4 text-gray-600">
                      {formatDate(period.end_date)}
                    </td>
                    <td className="py-3 px-4 text-gray-600">
                      {formatDateTime(period.deadline)}
                    </td>
                    <td className="py-3 px-4">
                      <StatusBadge status={period.status} />
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openComplianceView(period.id)}
                        >
                          <Eye className="w-4 h-4 ml-1" />
                          الالتزام
                        </Button>
                        {period.status === "open" && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-red-600 hover:text-red-700"
                            onClick={() => handleCloseClick(period.id)}
                          >
                            <Lock className="w-4 h-4 ml-1" />
                            إغلاق
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

      {/* مربع حوار فتح أسبوع جديد */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>فتح أسبوع جديد</DialogTitle>
            <DialogDescription>
              أدخل بيانات الفترة الأسبوعية الجديدة
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="period-year">السنة</Label>
                <Input
                  id="period-year"
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
                <Label htmlFor="period-week">رقم الأسبوع</Label>
                <Input
                  id="period-week"
                  type="number"
                  min={1}
                  max={53}
                  value={formData.week_number}
                  onChange={(e) =>
                    setFormData((prev) => ({
                      ...prev,
                      week_number: parseInt(e.target.value) || 1,
                    }))
                  }
                  dir="ltr"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="period-start">تاريخ البداية</Label>
              <Input
                id="period-start"
                type="date"
                value={formData.start_date}
                onChange={(e) =>
                  setFormData((prev) => ({
                    ...prev,
                    start_date: e.target.value,
                  }))
                }
                dir="ltr"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="period-end">تاريخ النهاية</Label>
              <Input
                id="period-end"
                type="date"
                value={formData.end_date}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, end_date: e.target.value }))
                }
                dir="ltr"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="period-deadline">الموعد النهائي</Label>
              <Input
                id="period-deadline"
                type="datetime-local"
                value={formData.deadline}
                onChange={(e) =>
                  setFormData((prev) => ({
                    ...prev,
                    deadline: e.target.value,
                  }))
                }
                dir="ltr"
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              onClick={handleCreate}
              disabled={
                createMutation.isPending ||
                !formData.start_date ||
                !formData.end_date ||
                !formData.deadline
              }
            >
              {createMutation.isPending ? "جارٍ الإنشاء..." : "فتح الأسبوع"}
            </Button>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              إلغاء
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* تأكيد الإغلاق */}
      <ConfirmDialog
        open={closeConfirmOpen}
        onOpenChange={setCloseConfirmOpen}
        title="إغلاق الأسبوع"
        description="هل أنت متأكد من إغلاق هذا الأسبوع؟ لن يتمكن مدراء الأقسام من تقديم أو تعديل منجزاتهم بعد الإغلاق."
        confirmLabel="إغلاق الأسبوع"
        onConfirm={handleConfirmClose}
        variant="destructive"
        loading={closeMutation.isPending}
      />

      {/* مربع حوار الالتزام */}
      <Dialog open={complianceDialogOpen} onOpenChange={setComplianceDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>متابعة الالتزام</DialogTitle>
            <DialogDescription>
              حالة تقديم المنجزات لهذا الأسبوع
            </DialogDescription>
          </DialogHeader>

          {complianceLoading ? (
            <LoadingSpinner />
          ) : complianceData ? (
            <div className="space-y-4 py-4">
              {/* ملخص */}
              <div className="grid grid-cols-3 gap-4">
                <div className="text-center p-3 bg-blue-50 rounded-lg">
                  <div className="text-2xl font-bold text-blue-700">
                    {complianceData.total_sections}
                  </div>
                  <div className="text-sm text-blue-600">إجمالي الأقسام</div>
                </div>
                <div className="text-center p-3 bg-green-50 rounded-lg">
                  <div className="text-2xl font-bold text-green-700">
                    {complianceData.submitted}
                  </div>
                  <div className="text-sm text-green-600">مُقدَّم</div>
                </div>
                <div className="text-center p-3 bg-red-50 rounded-lg">
                  <div className="text-2xl font-bold text-red-700">
                    {complianceData.late}
                  </div>
                  <div className="text-sm text-red-600">متأخر</div>
                </div>
              </div>

              {/* نسبة الالتزام */}
              {complianceData.total_sections > 0 && (
                <div className="bg-gray-50 rounded-lg p-3">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-sm font-medium text-gray-700">
                      نسبة الالتزام
                    </span>
                    <span className="text-sm font-bold text-gray-900">
                      {Math.round(
                        (complianceData.submitted / complianceData.total_sections) *
                          100
                      )}
                      %
                    </span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2.5">
                    <div
                      className="h-2.5 rounded-full bg-green-500 transition-all"
                      style={{
                        width: `${Math.round(
                          (complianceData.submitted /
                            complianceData.total_sections) *
                            100
                        )}%`,
                      }}
                    />
                  </div>
                </div>
              )}

              {/* التفاصيل */}
              {complianceData.sections && complianceData.sections.length > 0 && (
                <div className="border rounded-lg overflow-hidden">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b bg-gray-50">
                        <th className="text-right py-2 px-3 font-semibold text-gray-700">
                          القسم
                        </th>
                        <th className="text-right py-2 px-3 font-semibold text-gray-700">
                          الحالة
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {complianceData.sections.map(
                        (section: ComplianceData["sections"][0]) => (
                          <tr key={section.qism_id}>
                            <td className="py-2 px-3 text-gray-900">
                              {section.qism_name}
                            </td>
                            <td className="py-2 px-3">
                              <StatusBadge status={section.status} />
                            </td>
                          </tr>
                        )
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ) : (
            <EmptyState message="لا توجد بيانات التزام." />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
