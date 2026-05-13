"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getSubmissions } from "@/lib/api/submissions";
import type { WeeklySubmission } from "@/types/submissions";
import { useAuthStore } from "@/stores/authStore";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { ErrorState } from "@/components/shared/ErrorState";
import { EmptyState } from "@/components/shared/EmptyState";
import { Button } from "@/components/ui/button";
import { Eye, Clock } from "lucide-react";
import { formatDateTime, formatNumber } from "@/lib/utils";
import {
  SubmissionDetailModal,
  type ScopeUnitRef,
} from "@/components/shared/SubmissionDetailModal";

export default function HistoryPage() {
  const user = useAuthStore((s) => s.user);
  const [detailOpen, setDetailOpen] = useState(false);
  const [selectedPeriodId, setSelectedPeriodId] = useState<number | null>(null);
  const [selectedScope, setSelectedScope] = useState<ScopeUnitRef | null>(null);

  const {
    data: submissionsData,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["submissions-history"],
    queryFn: () => getSubmissions(),
  });

  const openDetail = (submission: WeeklySubmission) => {
    setSelectedPeriodId(submission.weekly_period);
    setSelectedScope({
      id: submission.qism,
      name: submission.qism_name,
      unit_type: "qism",
    });
    setDetailOpen(true);
  };

  const submissions = submissionsData?.results || [];

  if (isLoading) {
    return <LoadingSpinner size="lg" />;
  }

  if (isError) {
    return <ErrorState onRetry={() => refetch()} />;
  }

  const approvedCount = submissions.filter(
    (s: WeeklySubmission) => s.status === "approved"
  ).length;
  const submittedCount = submissions.filter(
    (s: WeeklySubmission) => s.status === "submitted"
  ).length;
  const draftCount = submissions.filter(
    (s: WeeklySubmission) => s.status === "draft"
  ).length;

  return (
    <div className="space-y-6">
      {/* العنوان */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">سجل المنجزات</h1>
        <p className="text-gray-500 mt-1">
          {user?.role === "section_manager"
            ? "عرض جميع منجزاتك الأسبوعية السابقة"
            : "عرض جميع المنجزات الأسبوعية المقدمة سابقاً"}
        </p>
      </div>

      {/* ملخص */}
      {submissions.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard
            label="إجمالي المنجزات"
            value={formatNumber(submissions.length)}
            color="text-gray-900"
          />
          <StatCard
            label="معتمدة"
            value={formatNumber(approvedCount)}
            color="text-green-600"
          />
          <StatCard
            label="مُرسلة"
            value={formatNumber(submittedCount)}
            color="text-blue-600"
          />
          <StatCard
            label="مسودات"
            value={formatNumber(draftCount)}
            color="text-gray-600"
          />
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
                  {user?.role !== "section_manager" && (
                    <th className="text-right py-3 px-4 font-semibold text-gray-700">
                      القسم
                    </th>
                  )}
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
                    {user?.role !== "section_manager" && (
                      <td className="py-3 px-4 text-gray-700">
                        {sub.qism_name}
                      </td>
                    )}
                    <td className="py-3 px-4">
                      <StatusBadge status={sub.status} />
                    </td>
                    <td className="py-3 px-4 text-gray-600" dir="ltr">
                      {formatNumber(sub.answers?.length || 0)}
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
                        onClick={() => openDetail(sub)}
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

      {/* Modal تفاصيل المنجز الموحّد */}
      <SubmissionDetailModal
        periodId={selectedPeriodId}
        scope={selectedScope}
        open={detailOpen}
        onClose={() => {
          setDetailOpen(false);
          setSelectedPeriodId(null);
          setSelectedScope(null);
        }}
      />
    </div>
  );
}

function StatCard({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color: string;
}) {
  return (
    <div className="bg-white rounded-xl border p-4 text-center">
      <div className={`text-2xl font-bold ${color}`} dir="ltr">
        {value}
      </div>
      <div className="text-sm text-gray-500 mt-1">{label}</div>
    </div>
  );
}
