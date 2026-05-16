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
import { Plus, Lock, Eye, AlertCircle, Zap, Calendar as CalendarIcon } from "lucide-react";
import { formatDate, formatDateTime, formatPercent, getErrorMessage } from "@/lib/utils";
import {
  HierarchicalTree,
  useBuildHierarchy,
} from "@/app/(dashboard)/reports/HierarchicalTree";
import {
  SubmissionDetailModal,
  type ScopeUnitRef,
} from "@/components/shared/SubmissionDetailModal";

interface PeriodFormData {
  year: number;
  week_number: number;
  start_date: string;
  end_date: string;
  deadline: string;
}

// خريطة الحالات بلون متوافق مع عرض الشجرة
const STATUS_DISPLAY: Record<string, { label: string; color: string }> = {
  approved: { label: "معتمد", color: "text-green-700 bg-green-50" },
  submitted: { label: "مُرسل", color: "text-blue-700 bg-blue-50" },
  late: { label: "متأخر", color: "text-red-700 bg-red-50" },
  draft: { label: "مسودة", color: "text-amber-700 bg-amber-50" },
  extended: { label: "مُمدَّد", color: "text-purple-700 bg-purple-50" },
  returned: { label: "مُرجَع", color: "text-pink-700 bg-pink-50" },
  not_submitted: { label: "غير مُقدَّم", color: "text-gray-600 bg-gray-100" },
};

/**
 * مكوّن شجري لعرض الالتزام بشكل هرمي (دائرة → مديرية → قسم).
 * يعتمد على `complianceData.sections` المسطّحة ويبني الشجرة تلقائياً.
 */
function ComplianceTree({
  sections,
  onNodeClick,
}: {
  sections: Array<{ qism_id: number; qism_name: string; status: string }>;
  onNodeClick?: (scope: ScopeUnitRef) => void;
}) {
  const tree = useBuildHierarchy(
    sections,
    ({ unit, descendantQismIds, ownData }) => {
      // عقدة قسم: تعرض الحالة مباشرة
      if (unit.unit_type === "qism" && ownData) {
        const display = STATUS_DISPLAY[ownData.status] || {
          label: ownData.status,
          color: "text-gray-700 bg-gray-50",
        };
        return {
          status: (
            <span
              className={`inline-block px-2 py-0.5 rounded-md text-xs font-medium ${display.color}`}
            >
              {display.label}
            </span>
          ),
          rate: "—",
        };
      }

      // عقدة دائرة/مديرية: نحسب إجمالي الأقسام الفرعية + نسبة الالتزام
      const relevantSections = sections.filter((s) =>
        descendantQismIds.includes(s.qism_id)
      );
      if (relevantSections.length === 0) {
        return { status: "—", rate: "—" };
      }

      const total = relevantSections.length;
      const compliant = relevantSections.filter(
        (s) => s.status === "approved" || s.status === "submitted"
      ).length;
      const rate = total > 0 ? (compliant / total) * 100 : 0;
      const rateColor =
        rate >= 90 ? "text-green-700" : rate >= 50 ? "text-blue-700" : "text-red-700";

      return {
        status: (
          <span className="text-sm font-medium text-gray-700">
            {compliant} <span className="text-gray-400">/</span> {total} قسم
          </span>
        ),
        rate: (
          <span className={`font-bold ${rateColor}`}>
            {formatPercent(rate)}
          </span>
        ),
      };
    },
    { includeEmpty: true }
  );

  return (
    <HierarchicalTree
      data={tree}
      columns={[
        { key: "status", label: "الحالة / الملتزم", align: "left" },
        { key: "rate", label: "نسبة الالتزام", align: "left" },
      ]}
      onNodeClick={
        onNodeClick
          ? (node) =>
              onNodeClick({
                id: node.unit_id,
                name: node.unit_name,
                unit_type: node.unit_type,
              })
          : undefined
      }
    />
  );
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
  const [submissionDetailOpen, setSubmissionDetailOpen] = useState(false);
  const [submissionDetailScope, setSubmissionDetailScope] =
    useState<ScopeUnitRef | null>(null);
  const [formData, setFormData] = useState<PeriodFormData>({
    year: currentYear,
    week_number: 1,
    start_date: "",
    end_date: "",
    deadline: "",
  });
  // خطأ إغلاق الأسبوع — يظهر كبانر فوق الجدول
  const [closeError, setCloseError] = useState<string | null>(null);

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
    onError: () => {
      // الخطأ يُعرَض داخل الحوار عبر createMutation.error
    },
  });

  const closeMutation = useMutation({
    mutationFn: (id: number) => closePeriod(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["periods"] });
      setCloseConfirmOpen(false);
      setClosingPeriodId(null);
      setCloseError(null);
    },
    onError: (err: unknown) => {
      setCloseError(getErrorMessage(err));
      setCloseConfirmOpen(false);
      setClosingPeriodId(null);
    },
  });

  const handleCloseConfirmChange = (open: boolean) => {
    setCloseConfirmOpen(open);
    if (!open) {
      setClosingPeriodId(null);
    }
  };

  // مسح خطأ الإنشاء عند فتح/إغلاق الـ dialog
  const handleDialogChange = (open: boolean) => {
    setDialogOpen(open);
    if (!open) {
      createMutation.reset();
      resetForm();
    }
  };

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

  // حساب الأسبوع الحالي (أحدث فترة مفتوحة)
  const currentPeriod = periods.find(
    (p: WeeklyPeriod) => p.status === "open"
  );

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
        <Button onClick={() => setDialogOpen(true)} variant="outline">
          <Plus className="w-4 h-4 ml-2" />
          فتح أسبوع يدوياً
        </Button>
      </div>

      {/* بطاقة الأسبوع الحالي — الإدارة التلقائية */}
      <div className="relative bg-gradient-to-l from-primary-50 to-blue-50 border border-primary-200 rounded-xl p-5 overflow-hidden">
        <div className="absolute top-0 left-0 w-32 h-32 bg-primary-100/40 rounded-full blur-3xl -translate-x-8 -translate-y-8" />
        <div className="relative flex items-start justify-between flex-wrap gap-4">
          <div className="flex items-start gap-4">
            <div className="flex-shrink-0 w-12 h-12 bg-primary-600 rounded-lg flex items-center justify-center shadow-sm">
              <CalendarIcon className="w-6 h-6 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2 mb-1">
                <h2 className="text-sm font-medium text-primary-700">
                  الأسبوع الحالي
                </h2>
                <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-primary-600 text-white text-xs font-medium rounded-full">
                  <Zap className="w-3 h-3" />
                  مُدار تلقائياً
                </span>
              </div>
              {currentPeriod ? (
                <>
                  <p className="text-xl font-bold text-gray-900">
                    الأسبوع {currentPeriod.week_number} / {currentPeriod.year}
                  </p>
                  <p className="text-sm text-gray-600 mt-1">
                    {formatDate(currentPeriod.start_date)} — {formatDate(currentPeriod.end_date)}
                  </p>
                  <p className="text-sm text-gray-600">
                    الموعد النهائي: {formatDateTime(currentPeriod.deadline)}
                  </p>
                </>
              ) : (
                <p className="text-sm text-gray-600 mt-1">
                  لا يوجد أسبوع مفتوح حالياً. سيُنشأ تلقائياً في بداية الأسبوع القادم.
                </p>
              )}
            </div>
          </div>
          <div className="text-xs text-gray-500 max-w-xs">
            💡 يُنشئ النظام الأسبوع الحالي تلقائياً ويُغلق السابق بعد انتهاء الموعد النهائي.
            يمكن تعديل الإعدادات من لوحة تحكم Django.
          </div>
        </div>
      </div>

      {/* بانر خطأ إغلاق الأسبوع */}
      {closeError && (
        <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 flex items-start gap-2">
          <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-red-700 break-words flex-1">{closeError}</p>
          <button
            type="button"
            onClick={() => setCloseError(null)}
            className="text-red-500 hover:text-red-700 text-sm"
          >
            ×
          </button>
        </div>
      )}

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
      <Dialog open={dialogOpen} onOpenChange={handleDialogChange}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>فتح أسبوع جديد</DialogTitle>
            <DialogDescription>
              أدخل بيانات الفترة الأسبوعية الجديدة
            </DialogDescription>
          </DialogHeader>

          {createMutation.isError && (
            <div className="bg-red-50 border border-red-200 rounded-md p-3 flex items-start gap-2">
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-red-700">
                {getErrorMessage(createMutation.error)}
              </p>
            </div>
          )}

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
            <Button variant="outline" onClick={() => handleDialogChange(false)}>
              إلغاء
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* تأكيد الإغلاق */}
      <ConfirmDialog
        open={closeConfirmOpen}
        onOpenChange={handleCloseConfirmChange}
        title="إغلاق الأسبوع"
        description="هل أنت متأكد من إغلاق هذا الأسبوع؟ لن يتمكن مدراء الأقسام من تقديم أو تعديل منجزاتهم بعد الإغلاق."
        confirmLabel="إغلاق الأسبوع"
        onConfirm={handleConfirmClose}
        variant="destructive"
        loading={closeMutation.isPending}
      />

      {/* Modal تفاصيل المنجز (قسم / مديرية / دائرة) */}
      <SubmissionDetailModal
        periodId={selectedPeriodId}
        scope={submissionDetailScope}
        open={submissionDetailOpen}
        onClose={() => {
          setSubmissionDetailOpen(false);
          setSubmissionDetailScope(null);
        }}
      />

      {/* مربع حوار الالتزام */}
      <Dialog open={complianceDialogOpen} onOpenChange={setComplianceDialogOpen}>
        <DialogContent className="max-w-3xl">
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

              {/* التفاصيل بشكل شجري (دائرة → مديرية → قسم) */}
              {complianceData.sections && complianceData.sections.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs text-gray-500 px-1">
                    💡 اضغط على سهم التوسيع لرؤية الأقسام، واضغط "عرض" لفتح تفاصيل منجز قسم أو تجميع مديرية/دائرة
                  </p>
                  <div className="max-h-[50vh] overflow-y-auto">
                    <ComplianceTree
                      sections={complianceData.sections}
                      onNodeClick={(scope) => {
                        setSubmissionDetailScope(scope);
                        setSubmissionDetailOpen(true);
                      }}
                    />
                  </div>
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
