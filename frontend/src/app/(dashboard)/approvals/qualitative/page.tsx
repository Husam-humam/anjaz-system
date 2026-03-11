"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getQualitativeAnswers,
  approveQualitative,
  rejectQualitative,
} from "@/lib/api/submissions";
import type { SubmissionAnswer } from "@/types/submissions";
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
import { CheckCircle, XCircle } from "lucide-react";

interface QualitativeItem extends SubmissionAnswer {
  qism_name?: string;
  submission_week?: string;
}

export default function QualitativeApprovalsPage() {
  const queryClient = useQueryClient();
  const [approveConfirmOpen, setApproveConfirmOpen] = useState(false);
  const [rejectDialogOpen, setRejectDialogOpen] = useState(false);
  const [actionId, setActionId] = useState<number | null>(null);
  const [rejectReason, setRejectReason] = useState("");

  const {
    data: qualitativeData,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["pending-qualitative"],
    queryFn: () =>
      getQualitativeAnswers({ qualitative_status: "pending_statistics" }),
  });

  const approveMutation = useMutation({
    mutationFn: (id: number) => approveQualitative(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pending-qualitative"] });
      setApproveConfirmOpen(false);
      setActionId(null);
    },
  });

  const rejectMutation = useMutation({
    mutationFn: ({ id, reason }: { id: number; reason: string }) =>
      rejectQualitative(id, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pending-qualitative"] });
      setRejectDialogOpen(false);
      setActionId(null);
      setRejectReason("");
    },
  });

  const handleApproveClick = (id: number) => {
    setActionId(id);
    setApproveConfirmOpen(true);
  };

  const handleRejectClick = (id: number) => {
    setActionId(id);
    setRejectDialogOpen(true);
  };

  const handleConfirmApprove = () => {
    if (actionId) {
      approveMutation.mutate(actionId);
    }
  };

  const handleConfirmReject = () => {
    if (actionId && rejectReason) {
      rejectMutation.mutate({ id: actionId, reason: rejectReason });
    }
  };

  const items: QualitativeItem[] = qualitativeData?.results || [];

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
          اعتماد المنجزات النوعية
        </h1>
        <p className="text-gray-500 mt-1">
          مراجعة واعتماد أو رفض المنجزات النوعية المقدمة
        </p>
      </div>

      {items.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3">
          <span className="text-amber-800 text-sm font-medium">
            يوجد {items.length} منجز نوعي بانتظار الاعتماد
          </span>
        </div>
      )}

      {/* القائمة */}
      <div className="bg-white rounded-xl shadow-sm border">
        {items.length === 0 ? (
          <EmptyState message="لا توجد منجزات نوعية بانتظار الاعتماد حالياً." />
        ) : (
          <div className="divide-y divide-gray-100">
            {items.map((item: QualitativeItem) => (
              <div
                key={item.id}
                className="p-5 hover:bg-gray-50 transition"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    {/* معلومات المؤشر */}
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="font-medium text-gray-900">
                        {item.indicator_name}
                      </h3>
                      <StatusBadge status={item.qualitative_status} />
                    </div>

                    {/* معلومات القسم والأسبوع */}
                    <div className="flex items-center gap-3 text-sm text-gray-500 mb-3">
                      {item.qism_name && (
                        <span className="bg-gray-100 px-2 py-0.5 rounded text-xs">
                          {item.qism_name}
                        </span>
                      )}
                      {item.submission_week && (
                        <span>{item.submission_week}</span>
                      )}
                    </div>

                    {/* القيمة الرقمية إن وجدت */}
                    {item.numeric_value !== null && (
                      <div className="text-sm text-gray-600 mb-2">
                        القيمة الرقمية:{" "}
                        <span className="font-semibold" dir="ltr">
                          {item.numeric_value.toLocaleString("ar-IQ")}
                        </span>
                      </div>
                    )}

                    {/* تفاصيل المنجز النوعي */}
                    <div className="bg-blue-50 border border-blue-100 rounded-lg p-4 mt-2">
                      <p className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">
                        {item.qualitative_details}
                      </p>
                    </div>
                  </div>

                  {/* أزرار الإجراءات */}
                  <div className="flex flex-col gap-2 flex-shrink-0">
                    <Button
                      size="sm"
                      className="bg-green-600 hover:bg-green-700"
                      onClick={() => handleApproveClick(item.id)}
                    >
                      <CheckCircle className="w-4 h-4 ml-1" />
                      اعتماد
                    </Button>
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => handleRejectClick(item.id)}
                    >
                      <XCircle className="w-4 h-4 ml-1" />
                      رفض
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* تأكيد الاعتماد */}
      <ConfirmDialog
        open={approveConfirmOpen}
        onOpenChange={setApproveConfirmOpen}
        title="اعتماد المنجز النوعي"
        description="هل أنت متأكد من اعتماد هذا المنجز النوعي؟"
        confirmLabel="اعتماد"
        onConfirm={handleConfirmApprove}
        loading={approveMutation.isPending}
      />

      {/* مربع حوار الرفض */}
      <Dialog open={rejectDialogOpen} onOpenChange={setRejectDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>رفض المنجز النوعي</DialogTitle>
            <DialogDescription>
              يرجى إدخال سبب رفض هذا المنجز النوعي
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="qual-reject-reason">سبب الرفض</Label>
              <textarea
                id="qual-reject-reason"
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
              {rejectMutation.isPending ? "جارٍ الرفض..." : "رفض المنجز"}
            </Button>
            <Button
              variant="outline"
              onClick={() => setRejectDialogOpen(false)}
            >
              إلغاء
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
