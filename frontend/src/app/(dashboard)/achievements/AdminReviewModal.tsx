"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import {
  adminApproveSubmission,
  adminEditSubmission,
  adminReturnSubmission,
  getSubmission,
  type AdminAnswerEdit,
} from "@/lib/api/submissions";
import { cn, formatDateTime, formatNumber, getErrorMessage } from "@/lib/utils";
import type { SubmissionAnswer, WeeklySubmission } from "@/types/submissions";
import {
  AlertCircle,
  CheckCircle,
  Eye,
  Pencil,
  RotateCcw,
  XCircle,
  History,
  Save,
  Lock,
} from "lucide-react";
import { AuditLogPanel } from "./AuditLogPanel";
import { useQuery } from "@tanstack/react-query";

type Mode = "view" | "edit" | "return";
type Tab = "answers" | "audit";

interface AdminReviewModalProps {
  submissionId: number | null;
  open: boolean;
  onClose: () => void;
}

interface AnswerDraft {
  answer_id: number;
  numeric_value: string; // نخزّن كنص لتسهيل التحرير
  text_value: string;
  // أصلية للمقارنة عند الإرسال
  original_numeric: number | null;
  original_text: string;
  is_qualitative: boolean;
  is_numeric_indicator: boolean;
}

function isNumericIndicator(unit_type: string): boolean {
  // كل ما هو ليس نصّاً يُعامل رقمياً
  return unit_type !== "text";
}

export function AdminReviewModal({
  submissionId,
  open,
  onClose,
}: AdminReviewModalProps) {
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<Mode>("view");
  const [tab, setTab] = useState<Tab>("answers");
  const [reason, setReason] = useState("");
  const [drafts, setDrafts] = useState<Record<number, AnswerDraft>>({});
  const [actionError, setActionError] = useState<string | null>(null);
  const [confirmApprove, setConfirmApprove] = useState(false);

  // جلب أحدث نسخة من المنجز عند فتح المربع
  const {
    data: submission,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["submission-detail", submissionId],
    queryFn: () => getSubmission(submissionId as number),
    enabled: open && submissionId !== null,
  });

  // إعادة تهيئة الحالة عند فتح/تغيير المنجز
  useEffect(() => {
    if (!open) return;
    setMode("view");
    setTab("answers");
    setReason("");
    setActionError(null);
    setConfirmApprove(false);
  }, [open, submissionId]);

  // إنشاء مسوّدات قابلة للتحرير من إجابات المنجز
  useEffect(() => {
    if (!submission) {
      setDrafts({});
      return;
    }
    const next: Record<number, AnswerDraft> = {};
    submission.answers.forEach((ans) => {
      next[ans.id] = {
        answer_id: ans.id,
        numeric_value:
          ans.numeric_value === null || ans.numeric_value === undefined
            ? ""
            : String(ans.numeric_value),
        text_value: ans.text_value ?? "",
        original_numeric: ans.numeric_value,
        original_text: ans.text_value ?? "",
        is_qualitative: ans.is_qualitative,
        is_numeric_indicator: isNumericIndicator(ans.indicator_unit_type),
      };
    });
    setDrafts(next);
  }, [submission]);

  // — الحالات المشتقّة —
  const isReviewed = submission?.admin_reviewed_at !== null;
  const reviewerName = submission?.admin_reviewed_by_name ?? "";

  const invalidateAfterAction = () => {
    queryClient.invalidateQueries({ queryKey: ["pending-admin-review"] });
    queryClient.invalidateQueries({
      queryKey: ["sidebar-pending-admin-review-count"],
    });
    queryClient.invalidateQueries({
      queryKey: ["submission-detail", submissionId],
    });
    queryClient.invalidateQueries({
      queryKey: ["submission-audit-log", submissionId],
    });
  };

  const approveMutation = useMutation({
    mutationFn: () => adminApproveSubmission(submissionId as number),
    onSuccess: () => {
      invalidateAfterAction();
      setConfirmApprove(false);
      onClose();
    },
    onError: (err) => setActionError(getErrorMessage(err)),
  });

  const editMutation = useMutation({
    mutationFn: (payload: { reason: string; answer_edits: AdminAnswerEdit[] }) =>
      adminEditSubmission(submissionId as number, payload),
    onSuccess: () => {
      invalidateAfterAction();
      onClose();
    },
    onError: (err) => setActionError(getErrorMessage(err)),
  });

  const returnMutation = useMutation({
    mutationFn: () =>
      adminReturnSubmission(submissionId as number, reason.trim()),
    onSuccess: () => {
      invalidateAfterAction();
      onClose();
    },
    onError: (err) => setActionError(getErrorMessage(err)),
  });

  const isPending =
    approveMutation.isPending || editMutation.isPending || returnMutation.isPending;

  // — الإجراءات —
  const handleApproveClick = () => {
    setActionError(null);
    setConfirmApprove(true);
  };

  const handleApproveConfirm = () => {
    setActionError(null);
    approveMutation.mutate();
  };

  const handleEnterEditMode = () => {
    setActionError(null);
    setMode("edit");
  };

  const handleEnterReturnMode = () => {
    setActionError(null);
    setMode("return");
  };

  const handleCancelMode = () => {
    setMode("view");
    setReason("");
    setActionError(null);
    // إعادة المسوّدات إلى القيم الأصلية
    if (submission) {
      const next: Record<number, AnswerDraft> = {};
      submission.answers.forEach((ans) => {
        next[ans.id] = {
          answer_id: ans.id,
          numeric_value:
            ans.numeric_value === null ? "" : String(ans.numeric_value),
          text_value: ans.text_value ?? "",
          original_numeric: ans.numeric_value,
          original_text: ans.text_value ?? "",
          is_qualitative: ans.is_qualitative,
          is_numeric_indicator: isNumericIndicator(ans.indicator_unit_type),
        };
      });
      setDrafts(next);
    }
  };

  const computeEdits = (): AdminAnswerEdit[] => {
    const edits: AdminAnswerEdit[] = [];
    Object.values(drafts).forEach((draft) => {
      // النوعي غير قابل للتعديل عبر هذا المسار
      if (draft.is_qualitative) return;

      if (draft.is_numeric_indicator) {
        const trimmed = draft.numeric_value.trim();
        const newVal =
          trimmed === "" ? null : Number(trimmed.replace(",", "."));
        // تخطّي القيم غير الرقمية الفاسدة (سيُفلتر validation الـ backend)
        if (newVal !== null && Number.isNaN(newVal)) return;

        const oldVal = draft.original_numeric;
        const oldNum = oldVal === null ? null : Number(oldVal);
        const changed =
          (newVal === null) !== (oldNum === null) ||
          (newVal !== null && oldNum !== null && newVal !== oldNum);

        if (changed) {
          edits.push({ answer_id: draft.answer_id, numeric_value: newVal });
        }
      } else {
        if (draft.text_value !== draft.original_text) {
          edits.push({
            answer_id: draft.answer_id,
            text_value: draft.text_value,
          });
        }
      }
    });
    return edits;
  };

  const editDiffs = useMemo(
    () => (mode === "edit" ? computeEdits() : []),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [drafts, mode]
  );

  const handleSubmitEdit = () => {
    setActionError(null);
    if (!reason.trim()) {
      setActionError("يجب تحديد سبب التعديل.");
      return;
    }
    if (editDiffs.length === 0) {
      setActionError("لا يوجد أي تعديل لإرساله.");
      return;
    }
    editMutation.mutate({ reason: reason.trim(), answer_edits: editDiffs });
  };

  const handleSubmitReturn = () => {
    setActionError(null);
    if (!reason.trim()) {
      setActionError("يجب تحديد سبب الإرجاع.");
      return;
    }
    returnMutation.mutate();
  };

  // إغلاق التأكيد عند الضغط على إلغاء
  const handleClose = () => {
    if (isPending) return;
    setConfirmApprove(false);
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && handleClose()}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>مراجعة المنجز</DialogTitle>
          <DialogDescription>
            {submission
              ? `${submission.qism_name} — ${submission.period_display}`
              : "جارٍ التحميل..."}
          </DialogDescription>
        </DialogHeader>

        {isLoading && (
          <div className="flex justify-center py-12">
            <LoadingSpinner size="lg" />
          </div>
        )}

        {isError && (
          <div className="rounded-md bg-red-50 border border-red-200 p-3 flex items-start gap-2">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm text-red-700">
                {getErrorMessage(error, "تعذّر تحميل المنجز.")}
              </p>
              <Button
                variant="outline"
                size="sm"
                className="mt-2"
                onClick={() => refetch()}
              >
                إعادة المحاولة
              </Button>
            </div>
          </div>
        )}

        {submission && (
          <>
            {/* رأس معلوماتي */}
            <SubmissionHeader submission={submission} />

            {/* تنبيه إن كان المنجز مُراجَعاً مسبقاً */}
            {isReviewed && (
              <div className="rounded-md bg-purple-50 border border-purple-200 p-3 flex items-start gap-2">
                <Lock className="w-5 h-5 text-purple-700 flex-shrink-0 mt-0.5" />
                <div className="text-sm text-purple-900">
                  <p className="font-semibold">
                    تمّت مراجعة هذا المنجز مسبقاً
                  </p>
                  <p className="text-xs mt-1">
                    بواسطة <strong>{reviewerName}</strong> في{" "}
                    {submission.admin_reviewed_at &&
                      formatDateTime(submission.admin_reviewed_at)}{" "}
                    — لا يمكن إجراء مراجعة أخرى.
                  </p>
                </div>
              </div>
            )}

            {/* رسالة الخطأ من الإجراء */}
            {actionError && (
              <div className="rounded-md bg-red-50 border border-red-200 p-3 flex items-start gap-2">
                <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                <p className="text-sm text-red-700">{actionError}</p>
              </div>
            )}

            {/* علامات التبويب */}
            <div className="flex border-b border-gray-200 gap-1">
              <TabButton
                active={tab === "answers"}
                onClick={() => setTab("answers")}
                icon={<Eye className="w-4 h-4" />}
                label="الإجابات"
              />
              <TabButton
                active={tab === "audit"}
                onClick={() => setTab("audit")}
                icon={<History className="w-4 h-4" />}
                label="سجلّ التدقيق"
              />
            </div>

            {/* محتوى التبويب */}
            {tab === "answers" && (
              <AnswersSection
                submission={submission}
                drafts={drafts}
                setDrafts={setDrafts}
                editable={mode === "edit"}
              />
            )}

            {tab === "audit" && (
              <div className="py-2">
                <AuditLogPanel submissionId={submission.id} />
              </div>
            )}

            {/* حقل السبب — في وضع التعديل أو الإرجاع */}
            {(mode === "edit" || mode === "return") && (
              <div className="space-y-2 rounded-lg border border-amber-200 bg-amber-50 p-3">
                <Label htmlFor="reason" className="text-amber-900 font-semibold">
                  {mode === "edit" ? "سبب التعديل" : "سبب الإرجاع"} (إلزامي)
                </Label>
                <textarea
                  id="reason"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder={
                    mode === "edit"
                      ? "اكتب سبب التعديل..."
                      : "اكتب سبب إرجاع المنجز لقسم التخطيط..."
                  }
                  className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-right min-h-[80px]"
                  dir="rtl"
                  disabled={isPending}
                />
                {mode === "edit" && (
                  <p className="text-xs text-amber-800">
                    عدد التعديلات المُحدَّدة:{" "}
                    <strong>{formatNumber(editDiffs.length)}</strong>
                  </p>
                )}
              </div>
            )}

            {/* أزرار الإجراءات */}
            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-gray-200 pt-4">
              <Button
                variant="outline"
                onClick={handleClose}
                disabled={isPending}
              >
                إغلاق
              </Button>

              <div className="flex flex-wrap items-center gap-2">
                {mode === "view" && !isReviewed && (
                  <>
                    <Button
                      variant="ghost"
                      className="text-purple-700 hover:bg-purple-50"
                      onClick={handleEnterReturnMode}
                      disabled={isPending}
                    >
                      <RotateCcw className="w-4 h-4 ml-1" />
                      إرجاع للتخطيط
                    </Button>
                    <Button
                      variant="ghost"
                      className="text-indigo-700 hover:bg-indigo-50"
                      onClick={handleEnterEditMode}
                      disabled={isPending}
                    >
                      <Pencil className="w-4 h-4 ml-1" />
                      تعديل
                    </Button>
                    <Button
                      className="bg-green-600 hover:bg-green-700"
                      onClick={handleApproveClick}
                      disabled={isPending}
                    >
                      <CheckCircle className="w-4 h-4 ml-1" />
                      اعتماد
                    </Button>
                  </>
                )}

                {mode === "edit" && (
                  <>
                    <Button
                      variant="outline"
                      onClick={handleCancelMode}
                      disabled={isPending}
                    >
                      <XCircle className="w-4 h-4 ml-1" />
                      إلغاء التعديل
                    </Button>
                    <Button
                      className="bg-indigo-600 hover:bg-indigo-700"
                      onClick={handleSubmitEdit}
                      disabled={
                        isPending ||
                        editDiffs.length === 0 ||
                        !reason.trim()
                      }
                    >
                      <Save className="w-4 h-4 ml-1" />
                      {editMutation.isPending
                        ? "جارٍ الحفظ..."
                        : "حفظ التعديلات"}
                    </Button>
                  </>
                )}

                {mode === "return" && (
                  <>
                    <Button
                      variant="outline"
                      onClick={handleCancelMode}
                      disabled={isPending}
                    >
                      <XCircle className="w-4 h-4 ml-1" />
                      إلغاء الإرجاع
                    </Button>
                    <Button
                      variant="destructive"
                      onClick={handleSubmitReturn}
                      disabled={isPending || !reason.trim()}
                    >
                      <RotateCcw className="w-4 h-4 ml-1" />
                      {returnMutation.isPending
                        ? "جارٍ الإرجاع..."
                        : "تأكيد الإرجاع"}
                    </Button>
                  </>
                )}
              </div>
            </div>

            {/* تأكيد الاعتماد */}
            {confirmApprove && (
              <div className="rounded-lg border border-green-300 bg-green-50 p-3 flex items-start justify-between gap-3 flex-wrap">
                <p className="text-sm text-green-900">
                  هل تريد اعتماد هذا المنجز بدون تعديل؟ لن تستطيع التراجع.
                </p>
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setConfirmApprove(false)}
                    disabled={isPending}
                  >
                    تراجع
                  </Button>
                  <Button
                    size="sm"
                    className="bg-green-600 hover:bg-green-700"
                    onClick={handleApproveConfirm}
                    disabled={isPending}
                  >
                    {approveMutation.isPending ? "جارٍ الاعتماد..." : "تأكيد الاعتماد"}
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ─────────────────────────────────────────────────
// مكوّنات داخلية
// ─────────────────────────────────────────────────

function SubmissionHeader({ submission }: { submission: WeeklySubmission }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-3 bg-gray-50 rounded-lg p-3">
      <InfoCell
        label="القسم"
        value={
          <span>
            {submission.qism_name}
            {submission.qism_parent_name && (
              <span className="text-xs text-gray-500 block">
                {submission.qism_parent_name}
              </span>
            )}
          </span>
        }
      />
      <InfoCell label="الأسبوع" value={submission.period_display} />
      <InfoCell label="الحالة" value={<StatusBadge status={submission.status} />} />
      <InfoCell
        label="اعتماد التخطيط"
        value={
          submission.planning_approved_at ? (
            <span>
              {submission.planning_approved_by_name ?? "—"}
              <span className="block text-xs text-gray-500">
                {formatDateTime(submission.planning_approved_at)}
              </span>
            </span>
          ) : (
            "—"
          )
        }
      />
      <InfoCell
        label="تاريخ الإرسال"
        value={submission.submitted_at ? formatDateTime(submission.submitted_at) : "—"}
      />
      <InfoCell
        label="عدد الإجابات"
        value={formatNumber(submission.answers.length)}
      />
    </div>
  );
}

function InfoCell({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="text-sm">
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <div className="font-medium text-gray-900">{value}</div>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex items-center gap-1.5 px-3 py-2 text-sm font-medium border-b-2 transition-colors",
        active
          ? "border-primary-600 text-primary-700"
          : "border-transparent text-gray-500 hover:text-gray-700"
      )}
    >
      {icon}
      {label}
    </button>
  );
}

function AnswersSection({
  submission,
  drafts,
  setDrafts,
  editable,
}: {
  submission: WeeklySubmission;
  drafts: Record<number, AnswerDraft>;
  setDrafts: (next: Record<number, AnswerDraft>) => void;
  editable: boolean;
}) {
  const updateDraft = (id: number, patch: Partial<AnswerDraft>) => {
    setDrafts({ ...drafts, [id]: { ...drafts[id], ...patch } });
  };

  if (submission.answers.length === 0) {
    return (
      <p className="text-sm text-gray-500 text-center py-6">
        لا توجد إجابات لهذا المنجز.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-gray-50">
            <th className="text-right py-2 px-3 font-semibold text-gray-700">
              المؤشر
            </th>
            <th className="text-right py-2 px-3 font-semibold text-gray-700">
              النوع
            </th>
            <th className="text-right py-2 px-3 font-semibold text-gray-700">
              القيمة
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {submission.answers.map((ans) => (
            <AnswerRow
              key={ans.id}
              answer={ans}
              draft={drafts[ans.id]}
              editable={editable}
              onChange={(patch) => updateDraft(ans.id, patch)}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AnswerRow({
  answer,
  draft,
  editable,
  onChange,
}: {
  answer: SubmissionAnswer;
  draft: AnswerDraft | undefined;
  editable: boolean;
  onChange: (patch: Partial<AnswerDraft>) => void;
}) {
  if (!draft) return null;
  const isNumeric = draft.is_numeric_indicator;
  const isQualitative = draft.is_qualitative;

  // قابلية التعديل: لا للنوعي، نعم لغيره
  const canEdit = editable && !isQualitative;
  const hasChanged = (() => {
    if (!editable) return false;
    if (isQualitative) return false;
    if (isNumeric) {
      const trimmed = draft.numeric_value.trim();
      const newVal = trimmed === "" ? null : Number(trimmed.replace(",", "."));
      if (newVal !== null && Number.isNaN(newVal)) return false;
      const oldNum = draft.original_numeric === null ? null : Number(draft.original_numeric);
      return (newVal === null) !== (oldNum === null)
        || (newVal !== null && oldNum !== null && newVal !== oldNum);
    }
    return draft.text_value !== draft.original_text;
  })();

  return (
    <tr className={cn(hasChanged && "bg-indigo-50/50")}>
      <td className="py-2 px-3 text-gray-900">
        {answer.indicator_name}
        {isQualitative && (
          <span className="ml-2 inline-flex items-center text-xs text-amber-700 bg-amber-100 rounded px-1.5 py-0.5">
            نوعي
          </span>
        )}
      </td>
      <td className="py-2 px-3 text-gray-500 text-xs">
        {isQualitative ? "نوعي" : isNumeric ? "رقم" : "نصّ"}
      </td>
      <td className="py-2 px-3">
        {isQualitative ? (
          <div className="text-xs text-gray-700">
            {answer.qualitative_details || "—"}
            <span className="block mt-1 text-xs text-amber-600">
              (الإجابات النوعية تُراجَع عبر مسار النوعي المستقل)
            </span>
          </div>
        ) : canEdit ? (
          isNumeric ? (
            <Input
              type="number"
              step="any"
              value={draft.numeric_value}
              onChange={(e) => onChange({ numeric_value: e.target.value })}
              className={cn("h-8 max-w-[160px]", hasChanged && "border-indigo-500")}
              dir="ltr"
              placeholder="—"
            />
          ) : (
            <Input
              type="text"
              value={draft.text_value}
              onChange={(e) => onChange({ text_value: e.target.value })}
              className={cn("h-8", hasChanged && "border-indigo-500")}
              dir="rtl"
            />
          )
        ) : (
          <div className="text-gray-900">
            {isNumeric ? (
              answer.numeric_value === null ? (
                <span className="text-gray-400">—</span>
              ) : (
                formatNumber(answer.numeric_value)
              )
            ) : (
              answer.text_value || <span className="text-gray-400">—</span>
            )}
          </div>
        )}
        {hasChanged && (
          <p className="text-xs text-indigo-600 mt-1">
            القيمة الأصلية:{" "}
            {isNumeric
              ? draft.original_numeric === null
                ? "—"
                : formatNumber(draft.original_numeric)
              : draft.original_text || "—"}
          </p>
        )}
      </td>
    </tr>
  );
}
