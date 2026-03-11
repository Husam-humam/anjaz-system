"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getSubmissions, approveSubmission } from "@/lib/api/submissions";
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
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { CheckCircle, Eye } from "lucide-react";

export default function ApprovalsPage() {
  const queryClient = useQueryClient();
  const [detailDialogOpen, setDetailDialogOpen] = useState(false);
  const [selectedSubmission, setSelectedSubmission] =
    useState<WeeklySubmission | null>(null);
  const [approveConfirmOpen, setApproveConfirmOpen] = useState(false);
  const [approvingId, setApprovingId] = useState<number | null>(null);

  const {
    data: submissionsData,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["pending-submissions"],
    queryFn: () => getSubmissions({ status: "submitted" }),
  });

  const approveMutation = useMutation({
    mutationFn: (id: number) => approveSubmission(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pending-submissions"] });
      setApproveConfirmOpen(false);
      setApprovingId(null);
    },
  });

  const handleApproveClick = (id: number) => {
    setApprovingId(id);
    setApproveConfirmOpen(true);
  };

  const handleConfirmApprove = () => {
    if (approvingId) {
      approveMutation.mutate(approvingId);
    }
  };

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
        <h1 className="text-2xl font-bold text-gray-900">
          المنجزات بانتظار الاعتماد
        </h1>
        <p className="text-gray-500 mt-1">
          مراجعة واعتماد المنجزات الأسبوعية المقدمة من الأقسام
        </p>
      </div>

      {/* عدد المنجزات المعلقة */}
      {submissions.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3">
          <span className="text-amber-800 text-sm font-medium">
            يوجد {submissions.length} منجز بانتظار الاعتماد
          </span>
        </div>
      )}

      {/* الجدول */}
      <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
        {submissions.length === 0 ? (
          <EmptyState message="لا توجد منجزات بانتظار الاعتماد حالياً." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50">
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    القسم
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    الأسبوع
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    تاريخ الإرسال
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    عدد الإجابات
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
                {submissions.map((sub: WeeklySubmission) => (
                  <tr key={sub.id} className="hover:bg-gray-50 transition">
                    <td className="py-3 px-4 font-medium text-gray-900">
                      {sub.qism_name}
                    </td>
                    <td className="py-3 px-4 text-gray-600">
                      {sub.period_display}
                    </td>
                    <td className="py-3 px-4 text-gray-600">
                      {sub.submitted_at
                        ? new Date(sub.submitted_at).toLocaleDateString(
                            "ar-IQ",
                            {
                              year: "numeric",
                              month: "short",
                              day: "numeric",
                              hour: "2-digit",
                              minute: "2-digit",
                            }
                          )
                        : "—"}
                    </td>
                    <td className="py-3 px-4 text-gray-600">
                      {sub.answers?.length || 0} إجابة
                    </td>
                    <td className="py-3 px-4">
                      <StatusBadge status={sub.status} />
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => viewDetails(sub)}
                        >
                          <Eye className="w-4 h-4 ml-1" />
                          عرض
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-green-600 hover:text-green-700"
                          onClick={() => handleApproveClick(sub.id)}
                        >
                          <CheckCircle className="w-4 h-4 ml-1" />
                          اعتماد
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
              <div className="flex items-center gap-3">
                <span className="text-sm text-gray-500">الحالة:</span>
                <StatusBadge status={selectedSubmission.status} />
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
                      (answer: SubmissionAnswer) => (
                        <tr key={answer.id}>
                          <td className="py-2 px-3 text-gray-900">
                            {answer.indicator_name}
                          </td>
                          <td className="py-2 px-3 text-gray-700" dir="ltr">
                            {answer.indicator_unit_type === "text"
                              ? answer.text_value || "—"
                              : answer.numeric_value?.toLocaleString("ar-IQ") ??
                                "—"}
                          </td>
                          <td className="py-2 px-3">
                            {answer.is_qualitative ? (
                              <div>
                                <span className="text-green-600 text-xs font-medium">
                                  نعم
                                </span>
                                {answer.qualitative_details && (
                                  <p className="text-xs text-gray-500 mt-1 line-clamp-2">
                                    {answer.qualitative_details}
                                  </p>
                                )}
                              </div>
                            ) : (
                              <span className="text-gray-400 text-xs">لا</span>
                            )}
                          </td>
                        </tr>
                      )
                    )}
                  </tbody>
                </table>
              </div>

              {selectedSubmission.status === "submitted" && (
                <div className="flex justify-end pt-2">
                  <Button
                    onClick={() => {
                      setDetailDialogOpen(false);
                      handleApproveClick(selectedSubmission.id);
                    }}
                    className="bg-green-600 hover:bg-green-700"
                  >
                    <CheckCircle className="w-4 h-4 ml-2" />
                    اعتماد هذا المنجز
                  </Button>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* تأكيد الاعتماد */}
      <ConfirmDialog
        open={approveConfirmOpen}
        onOpenChange={setApproveConfirmOpen}
        title="اعتماد المنجز"
        description="هل أنت متأكد من اعتماد هذا المنجز الأسبوعي؟"
        confirmLabel="اعتماد"
        onConfirm={handleConfirmApprove}
        loading={approveMutation.isPending}
      />
    </div>
  );
}
