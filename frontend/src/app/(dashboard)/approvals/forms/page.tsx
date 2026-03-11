"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getFormTemplates,
  approveFormTemplate,
  rejectFormTemplate,
} from "@/lib/api/forms";
import type { FormTemplate, FormTemplateItem } from "@/types/submissions";
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
import { CheckCircle, XCircle, Eye } from "lucide-react";
import { formatDate } from "@/lib/utils";

export default function FormApprovalsPage() {
  const queryClient = useQueryClient();
  const [approveDialogOpen, setApproveDialogOpen] = useState(false);
  const [rejectDialogOpen, setRejectDialogOpen] = useState(false);
  const [detailDialogOpen, setDetailDialogOpen] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<FormTemplate | null>(
    null
  );
  const [actionTemplateId, setActionTemplateId] = useState<number | null>(null);
  const [effectiveWeek, setEffectiveWeek] = useState("");
  const [effectiveYear, setEffectiveYear] = useState(
    new Date().getFullYear().toString()
  );
  const [rejectReason, setRejectReason] = useState("");

  const {
    data: templatesData,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["pending-templates"],
    queryFn: () => getFormTemplates({ status: "pending_approval" }),
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
      queryClient.invalidateQueries({ queryKey: ["pending-templates"] });
      setApproveDialogOpen(false);
      setActionTemplateId(null);
      setEffectiveWeek("");
      setEffectiveYear(new Date().getFullYear().toString());
    },
  });

  const rejectMutation = useMutation({
    mutationFn: ({ id, reason }: { id: number; reason: string }) =>
      rejectFormTemplate(id, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pending-templates"] });
      setRejectDialogOpen(false);
      setActionTemplateId(null);
      setRejectReason("");
    },
  });

  const handleApproveClick = (id: number) => {
    setActionTemplateId(id);
    setApproveDialogOpen(true);
  };

  const handleRejectClick = (id: number) => {
    setActionTemplateId(id);
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
    if (actionTemplateId && rejectReason) {
      rejectMutation.mutate({
        id: actionTemplateId,
        reason: rejectReason,
      });
    }
  };

  const viewDetails = (template: FormTemplate) => {
    setSelectedTemplate(template);
    setDetailDialogOpen(true);
  };

  const templates = templatesData?.results || [];

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
          اعتماد نماذج الاستمارات
        </h1>
        <p className="text-gray-500 mt-1">
          مراجعة واعتماد أو رفض نماذج الاستمارات المقدمة
        </p>
      </div>

      {templates.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3">
          <span className="text-amber-800 text-sm font-medium">
            يوجد {templates.length} استمارة بانتظار الاعتماد
          </span>
        </div>
      )}

      {/* القائمة */}
      <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
        {templates.length === 0 ? (
          <EmptyState message="لا توجد استمارات بانتظار الاعتماد حالياً." />
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
                    عدد المؤشرات
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    تاريخ الإنشاء
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
                {templates.map((tpl: FormTemplate) => (
                  <tr key={tpl.id} className="hover:bg-gray-50 transition">
                    <td className="py-3 px-4 font-medium text-gray-900">
                      {tpl.qism_name}
                    </td>
                    <td className="py-3 px-4 text-gray-600">
                      الإصدار {tpl.version}
                    </td>
                    <td className="py-3 px-4 text-gray-600">
                      {tpl.items?.length || 0} مؤشر
                    </td>
                    <td className="py-3 px-4 text-gray-500 text-xs">
                      {formatDate(tpl.created_at)}
                    </td>
                    <td className="py-3 px-4">
                      <StatusBadge status={tpl.status} />
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => viewDetails(tpl)}
                        >
                          <Eye className="w-4 h-4 ml-1" />
                          عرض
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-green-600 hover:text-green-700"
                          onClick={() => handleApproveClick(tpl.id)}
                        >
                          <CheckCircle className="w-4 h-4 ml-1" />
                          اعتماد
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-red-600 hover:text-red-700"
                          onClick={() => handleRejectClick(tpl.id)}
                        >
                          <XCircle className="w-4 h-4 ml-1" />
                          رفض
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

      {/* مربع حوار الاعتماد */}
      <Dialog open={approveDialogOpen} onOpenChange={setApproveDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>اعتماد الاستمارة</DialogTitle>
            <DialogDescription>
              حدد أسبوع بداية تفعيل هذه الاستمارة
            </DialogDescription>
          </DialogHeader>

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
              onClick={() => setApproveDialogOpen(false)}
            >
              إلغاء
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* مربع حوار الرفض */}
      <Dialog open={rejectDialogOpen} onOpenChange={setRejectDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>رفض الاستمارة</DialogTitle>
            <DialogDescription>
              يرجى إدخال سبب رفض هذه الاستمارة
            </DialogDescription>
          </DialogHeader>

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
