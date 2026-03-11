"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getSubmissions } from "@/lib/api/submissions";
import type { WeeklySubmission, SubmissionAnswer } from "@/types/submissions";
import { STATUS_LABELS, STATUS_COLORS } from "@/lib/constants";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { ErrorState } from "@/components/shared/ErrorState";
import { EmptyState } from "@/components/shared/EmptyState";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Eye, Clock } from "lucide-react";
import { formatDateTime } from "@/lib/utils";

export default function HistoryPage() {
  const [detailDialogOpen, setDetailDialogOpen] = useState(false);
  const [selectedSubmission, setSelectedSubmission] =
    useState<WeeklySubmission | null>(null);

  const {
    data: submissionsData,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["submissions-history"],
    queryFn: () => getSubmissions(),
  });

  const viewDetails = (submission: WeeklySubmission) => {
    setSelectedSubmission(submission);
    setDetailDialogOpen(true);
  };

  const submissions = submissionsData?.results || [];

  if (isLoading) {
    return <LoadingSpinner size="lg" />;
  }

  if (isError) {
    return <ErrorState onRetry={() => refetch()} />;
  }

  return (
    <div className="space-y-6">
      {/* العنوان */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">سجل المنجزات</h1>
        <p className="text-gray-500 mt-1">
          عرض جميع المنجزات الأسبوعية المقدمة سابقاً
        </p>
      </div>

      {/* ملخص */}
      {submissions.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-white rounded-xl border p-4 text-center">
            <div className="text-2xl font-bold text-gray-900">
              {submissions.length}
            </div>
            <div className="text-sm text-gray-500">إجمالي المنجزات</div>
          </div>
          <div className="bg-white rounded-xl border p-4 text-center">
            <div className="text-2xl font-bold text-green-600">
              {
                submissions.filter(
                  (s: WeeklySubmission) => s.status === "approved"
                ).length
              }
            </div>
            <div className="text-sm text-gray-500">معتمدة</div>
          </div>
          <div className="bg-white rounded-xl border p-4 text-center">
            <div className="text-2xl font-bold text-blue-600">
              {
                submissions.filter(
                  (s: WeeklySubmission) => s.status === "submitted"
                ).length
              }
            </div>
            <div className="text-sm text-gray-500">مُرسلة</div>
          </div>
          <div className="bg-white rounded-xl border p-4 text-center">
            <div className="text-2xl font-bold text-gray-600">
              {
                submissions.filter(
                  (s: WeeklySubmission) => s.status === "draft"
                ).length
              }
            </div>
            <div className="text-sm text-gray-500">مسودات</div>
          </div>
        </div>
      )}

      {/* الجدول */}
      <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
        {submissions.length === 0 ? (
          <EmptyState message="لا توجد منجزات سابقة." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50">
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    الأسبوع
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    الحالة
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    عدد الإجابات
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    تاريخ الإرسال
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    تاريخ الاعتماد
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    إجراءات
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {submissions.map((sub: WeeklySubmission) => (
                  <tr key={sub.id} className="hover:bg-gray-50 transition">
                    <td className="py-3 px-4 font-medium text-gray-900">
                      <div className="flex items-center gap-2">
                        <Clock className="w-4 h-4 text-gray-400" />
                        {sub.period_display}
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <StatusBadge status={sub.status} />
                    </td>
                    <td className="py-3 px-4 text-gray-600">
                      {sub.answers?.length || 0} إجابة
                    </td>
                    <td className="py-3 px-4 text-gray-600 text-xs">
                      {sub.submitted_at
                        ? formatDateTime(sub.submitted_at)
                        : "—"}
                    </td>
                    <td className="py-3 px-4 text-gray-600 text-xs">
                      {sub.planning_approved_at
                        ? formatDateTime(sub.planning_approved_at)
                        : "—"}
                    </td>
                    <td className="py-3 px-4">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => viewDetails(sub)}
                      >
                        <Eye className="w-4 h-4 ml-1" />
                        عرض
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* مربع حوار التفاصيل */}
      <Dialog open={detailDialogOpen} onOpenChange={setDetailDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>تفاصيل المنجز</DialogTitle>
            <DialogDescription>
              {selectedSubmission?.qism_name} —{" "}
              {selectedSubmission?.period_display}
            </DialogDescription>
          </DialogHeader>

          {selectedSubmission && (
            <div className="space-y-4 py-4">
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-500">الحالة:</span>
                  <StatusBadge status={selectedSubmission.status} />
                </div>
                {selectedSubmission.submitted_at && (
                  <span className="text-xs text-gray-400">
                    تاريخ الإرسال:{" "}
                    {formatDateTime(selectedSubmission.submitted_at)}
                  </span>
                )}
              </div>

              {selectedSubmission.notes && (
                <div className="bg-gray-50 rounded-lg p-3">
                  <span className="text-sm text-gray-500">ملاحظات: </span>
                  <span className="text-sm text-gray-900">
                    {selectedSubmission.notes}
                  </span>
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
                        القيمة
                      </th>
                      <th className="text-right py-2 px-3 font-semibold text-gray-700">
                        نوعي
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {selectedSubmission.answers?.map(
                      (answer: SubmissionAnswer, idx: number) => (
                        <tr key={answer.id}>
                          <td className="py-2 px-3 text-gray-500">
                            {idx + 1}
                          </td>
                          <td className="py-2 px-3 text-gray-900">
                            {answer.indicator_name}
                          </td>
                          <td className="py-2 px-3 text-gray-700" dir="ltr">
                            {answer.indicator_unit_type === "text"
                              ? answer.text_value || "—"
                              : answer.numeric_value?.toLocaleString(
                                  "ar-IQ"
                                ) ?? "—"}
                          </td>
                          <td className="py-2 px-3">
                            {answer.is_qualitative ? (
                              <div>
                                <StatusBadge
                                  status={answer.qualitative_status}
                                />
                                {answer.qualitative_details && (
                                  <p className="text-xs text-gray-500 mt-1 line-clamp-2">
                                    {answer.qualitative_details}
                                  </p>
                                )}
                              </div>
                            ) : (
                              <span className="text-gray-400 text-xs">—</span>
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
    </div>
  );
}
