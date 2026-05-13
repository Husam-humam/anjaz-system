"use client";

import { useQuery } from "@tanstack/react-query";
import { getSubmissionAuditLog } from "@/lib/api/submissions";
import { AUDIT_ACTION_LABELS, AUDIT_ACTION_COLORS, ROLE_LABELS } from "@/lib/constants";
import { cn, formatDateTime, getErrorMessage } from "@/lib/utils";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import type { AuditFieldChange, AuditLogEntry } from "@/types/submissions";
import { Clock, User as UserIcon, AlertCircle } from "lucide-react";

interface AuditLogPanelProps {
  submissionId: number | null;
}

export function AuditLogPanel({ submissionId }: AuditLogPanelProps) {
  const { data, isLoading, isError, refetch, error } = useQuery({
    queryKey: ["submission-audit-log", submissionId],
    queryFn: () => getSubmissionAuditLog(submissionId as number),
    enabled: submissionId !== null,
  });

  if (submissionId === null) return null;
  if (isLoading) return <LoadingSpinner size="md" />;
  if (isError) {
    return (
      <ErrorState
        message={getErrorMessage(error, "فشل تحميل سجلّ التدقيق.")}
        onRetry={() => refetch()}
      />
    );
  }

  const entries = data?.results ?? [];
  if (entries.length === 0) {
    return <EmptyState message="لا يوجد أي إجراء مسجَّل لهذا المنجز بعد." />;
  }

  return (
    <div className="space-y-3">
      {entries.map((entry) => (
        <AuditLogItem key={entry.id} entry={entry} />
      ))}
    </div>
  );
}

function AuditLogItem({ entry }: { entry: AuditLogEntry }) {
  const label = entry.action_label || AUDIT_ACTION_LABELS[entry.action_type] || entry.action_type;
  const colorClass =
    AUDIT_ACTION_COLORS[entry.action_type] ?? "bg-gray-100 text-gray-700";
  const roleLabel = entry.actor_role ? ROLE_LABELS[entry.actor_role] ?? "" : "";

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "inline-flex items-center justify-center rounded-full px-2.5 py-0.5 text-xs font-semibold",
              colorClass
            )}
          >
            {label}
          </span>
        </div>
        <div className="flex items-center gap-1 text-xs text-gray-500">
          <Clock className="h-3.5 w-3.5" />
          <span>{formatDateTime(entry.created_at)}</span>
        </div>
      </div>

      <div className="mt-2 flex items-center gap-2 text-sm text-gray-700">
        <UserIcon className="h-4 w-4 text-gray-400" />
        <span className="font-medium">{entry.actor_name}</span>
        {roleLabel && (
          <span className="text-xs text-gray-500">({roleLabel})</span>
        )}
      </div>

      {entry.reason && (
        <div className="mt-3 flex items-start gap-2 rounded-md bg-amber-50 border border-amber-200 p-2">
          <AlertCircle className="h-4 w-4 text-amber-600 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-amber-900">
            <span className="font-semibold">السبب:</span> {entry.reason}
          </p>
        </div>
      )}

      {entry.field_changes && entry.field_changes.length > 0 && (
        <div className="mt-3 space-y-2">
          <p className="text-xs font-semibold text-gray-700">تفاصيل التعديلات:</p>
          <div className="space-y-1.5">
            {entry.field_changes.map((change, idx) => (
              <FieldChangeRow key={idx} change={change} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function FieldChangeRow({ change }: { change: AuditFieldChange }) {
  const fieldLabel =
    change.indicator_name ??
    (change.field === "numeric_value"
      ? "قيمة رقمية"
      : change.field === "text_value"
      ? "قيمة نصّية"
      : change.field);

  return (
    <div className="rounded border border-gray-200 bg-gray-50 p-2 text-xs">
      <div className="font-medium text-gray-700">{fieldLabel}</div>
      <div className="mt-1 flex items-center gap-2 flex-wrap">
        <span className="rounded bg-red-50 px-2 py-0.5 text-red-700 line-through">
          {change.old ?? "—"}
        </span>
        <span className="text-gray-400">←</span>
        <span className="rounded bg-green-50 px-2 py-0.5 text-green-700 font-semibold">
          {change.new ?? "—"}
        </span>
      </div>
    </div>
  );
}
