"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  getPendingAdminReview,
  type PendingAdminReviewFilters,
} from "@/lib/api/submissions";
import { getOrganizationUnits } from "@/lib/api/organization";
import type { OrganizationUnit } from "@/types/organization";
import type { WeeklySubmission } from "@/types/submissions";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { ErrorState } from "@/components/shared/ErrorState";
import { EmptyState } from "@/components/shared/EmptyState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn, formatDateTime, formatNumber } from "@/lib/utils";
import {
  Eye,
  Filter,
  RotateCcw,
  Search,
  CheckCircle2,
  Clock,
  Pencil,
  Lock,
} from "lucide-react";
import { AdminReviewModal } from "./AdminReviewModal";

type ReviewedFilter = "" | "true" | "false";

const REVIEWED_FILTER_OPTIONS: { value: ReviewedFilter; label: string }[] = [
  { value: "false", label: "بانتظار المراجعة" },
  { value: "true", label: "تمّت مراجعتها" },
  { value: "", label: "الكل" },
];

const ADMIN_ACTION_LABELS: Record<string, string> = {
  approved: "اعتمدت",
  edited: "عُدِّلت",
  returned: "أُرجعت",
};

const ADMIN_ACTION_COLORS: Record<string, string> = {
  approved: "bg-emerald-100 text-emerald-700",
  edited: "bg-indigo-100 text-indigo-700",
  returned: "bg-purple-100 text-purple-700",
};

export default function AchievementsPage() {
  const currentYear = new Date().getFullYear();

  // ── الفلاتر ──
  const [reviewedFilter, setReviewedFilter] = useState<ReviewedFilter>("false");
  const [yearFilter, setYearFilter] = useState<string>(String(currentYear));
  const [weekFilter, setWeekFilter] = useState<string>("");
  const [dairaFilter, setDairaFilter] = useState<string>("");
  const [mudiriyaFilter, setMudiriyaFilter] = useState<string>("");
  const [qismFilter, setQismFilter] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState<string>("");

  const [page, setPage] = useState(1);
  const [reviewSubmissionId, setReviewSubmissionId] = useState<number | null>(
    null
  );
  const [modalOpen, setModalOpen] = useState(false);

  // ── الاستعلامات ──
  const queryFilters: PendingAdminReviewFilters = useMemo(() => {
    const f: PendingAdminReviewFilters = {
      page: String(page),
      page_size: "25",
    };
    if (reviewedFilter) f.reviewed = reviewedFilter;
    if (yearFilter) f.year = yearFilter;
    if (weekFilter) f.week = weekFilter;
    if (dairaFilter) f.daira_id = dairaFilter;
    if (mudiriyaFilter) f.mudiriya_id = mudiriyaFilter;
    if (qismFilter) f.qism_id = qismFilter;
    return f;
  }, [
    reviewedFilter,
    yearFilter,
    weekFilter,
    dairaFilter,
    mudiriyaFilter,
    qismFilter,
    page,
  ]);

  const {
    data: submissionsData,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["pending-admin-review", queryFilters],
    queryFn: () => getPendingAdminReview(queryFilters),
  });

  const { data: dairasData } = useQuery({
    queryKey: ["organization-units-daira"],
    queryFn: () => getOrganizationUnits({ unit_type: "daira" }),
  });

  const { data: mudiriyasData } = useQuery({
    queryKey: ["organization-units-mudiriya", dairaFilter],
    queryFn: () => {
      const params: Record<string, string> = { unit_type: "mudiriya" };
      if (dairaFilter) params.parent = dairaFilter;
      return getOrganizationUnits(params);
    },
  });

  const { data: qismsData } = useQuery({
    queryKey: ["organization-units-qism", mudiriyaFilter],
    queryFn: () => {
      const params: Record<string, string> = { unit_type: "qism" };
      // الـ backend يدعم فلتر `parent` فقط — فلترة بالدائرة تتمّ
      // على جانب المنجزات نفسها عبر `daira_id`، وقائمة الأقسام تبقى كاملة.
      if (mudiriyaFilter) params.parent = mudiriyaFilter;
      return getOrganizationUnits(params);
    },
  });

  const dairas = dairasData?.results ?? [];
  const mudiriyas = mudiriyasData?.results ?? [];
  const qisms = (qismsData?.results ?? []).filter(
    (u) => u.qism_role === "regular"
  );

  // ── النتائج والإحصاء السريع ──
  const allSubmissions = submissionsData?.results ?? [];
  const submissions = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return allSubmissions;
    return allSubmissions.filter(
      (s) =>
        s.qism_name.toLowerCase().includes(q) ||
        (s.qism_parent_name ?? "").toLowerCase().includes(q)
    );
  }, [allSubmissions, searchQuery]);

  const totalCount = submissionsData?.count ?? 0;
  const hasNext = submissionsData?.next !== null && submissionsData?.next !== undefined;
  const hasPrev = submissionsData?.previous !== null && submissionsData?.previous !== undefined;

  const pendingCountInPage = allSubmissions.filter(
    (s) => s.admin_reviewed_at === null
  ).length;

  // ── إجراءات ──
  const openReviewModal = (id: number) => {
    setReviewSubmissionId(id);
    setModalOpen(true);
  };

  const closeReviewModal = () => {
    setModalOpen(false);
    // نُبقي على submissionId لتجنّب وميض المحتوى أثناء الإغلاق
  };

  const resetFilters = () => {
    setReviewedFilter("false");
    setYearFilter(String(currentYear));
    setWeekFilter("");
    setDairaFilter("");
    setMudiriyaFilter("");
    setQismFilter("");
    setSearchQuery("");
    setPage(1);
  };

  const hasActiveFilters =
    reviewedFilter !== "false" ||
    yearFilter !== String(currentYear) ||
    weekFilter !== "" ||
    dairaFilter !== "" ||
    mudiriyaFilter !== "" ||
    qismFilter !== "" ||
    searchQuery !== "";

  // ── سنوات للفلتر ──
  const yearOptions = useMemo(() => {
    const years: number[] = [];
    for (let y = currentYear + 1; y >= currentYear - 3; y--) years.push(y);
    return years;
  }, [currentYear]);

  if (isLoading) return <LoadingSpinner size="lg" />;

  if (isError) {
    return (
      <ErrorState
        message="تعذّر تحميل قائمة المنجزات."
        onRetry={() => refetch()}
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* العنوان */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">المنجزات</h1>
          <p className="text-gray-500 mt-1">
            مراجعة المنجزات المعتمَدة من قسم التخطيط — اعتماد، تعديل، أو إرجاع
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <StatChip
            label="بانتظار المراجعة (في هذه الصفحة)"
            value={pendingCountInPage}
            color="amber"
            icon={<Clock className="w-4 h-4" />}
          />
          <StatChip
            label="إجمالي النتائج"
            value={totalCount}
            color="blue"
            icon={<CheckCircle2 className="w-4 h-4" />}
          />
        </div>
      </div>

      {/* شريط الفلاتر */}
      <div className="bg-white rounded-xl shadow-sm border p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2 text-gray-700">
            <Filter className="w-4 h-4" />
            <span className="text-sm font-medium">الفلاتر والبحث</span>
          </div>
          {hasActiveFilters && (
            <Button variant="ghost" size="sm" onClick={resetFilters}>
              <RotateCcw className="w-3.5 h-3.5 ml-1" />
              مسح الفلاتر
            </Button>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {/* بحث باسم القسم */}
          <div className="relative md:col-span-2">
            <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <Input
              placeholder="بحث باسم القسم أو المديرية..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pr-10"
            />
          </div>

          {/* السنة */}
          <select
            value={yearFilter}
            onChange={(e) => {
              setYearFilter(e.target.value);
              setPage(1);
            }}
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-right"
            dir="rtl"
            aria-label="السنة"
          >
            <option value="">جميع السنوات</option>
            {yearOptions.map((y) => (
              <option key={y} value={String(y)}>
                {y}
              </option>
            ))}
          </select>

          {/* الأسبوع */}
          <Input
            type="number"
            min={1}
            max={53}
            placeholder="رقم الأسبوع"
            value={weekFilter}
            onChange={(e) => {
              setWeekFilter(e.target.value);
              setPage(1);
            }}
            dir="ltr"
            aria-label="الأسبوع"
          />

          {/* الدائرة */}
          <select
            value={dairaFilter}
            onChange={(e) => {
              setDairaFilter(e.target.value);
              setMudiriyaFilter("");
              setQismFilter("");
              setPage(1);
            }}
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-right"
            dir="rtl"
            aria-label="الدائرة"
          >
            <option value="">جميع الدوائر</option>
            {dairas.map((d: OrganizationUnit) => (
              <option key={d.id} value={String(d.id)}>
                {d.name}
              </option>
            ))}
          </select>

          {/* المديرية */}
          <select
            value={mudiriyaFilter}
            onChange={(e) => {
              setMudiriyaFilter(e.target.value);
              setQismFilter("");
              setPage(1);
            }}
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-right"
            dir="rtl"
            aria-label="المديرية"
          >
            <option value="">جميع المديريات</option>
            {mudiriyas.map((m: OrganizationUnit) => (
              <option key={m.id} value={String(m.id)}>
                {m.name}
              </option>
            ))}
          </select>

          {/* القسم */}
          <select
            value={qismFilter}
            onChange={(e) => {
              setQismFilter(e.target.value);
              setPage(1);
            }}
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-right"
            dir="rtl"
            aria-label="القسم"
          >
            <option value="">جميع الأقسام</option>
            {qisms.map((q: OrganizationUnit) => (
              <option key={q.id} value={String(q.id)}>
                {q.name}
              </option>
            ))}
          </select>

          {/* حالة المراجعة */}
          <div className="md:col-span-2 lg:col-span-4 flex items-center gap-2 flex-wrap">
            <span className="text-xs text-gray-600">حالة المراجعة:</span>
            {REVIEWED_FILTER_OPTIONS.map((opt) => (
              <button
                type="button"
                key={opt.value || "all"}
                onClick={() => {
                  setReviewedFilter(opt.value);
                  setPage(1);
                }}
                className={cn(
                  "rounded-full px-3 py-1 text-xs font-medium border transition-colors",
                  reviewedFilter === opt.value
                    ? "bg-primary-600 text-white border-primary-600"
                    : "bg-white text-gray-700 border-gray-300 hover:border-primary-400"
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        <div className="mt-3 text-xs text-gray-500">
          {`تم عرض ${formatNumber(submissions.length)} ${
            submissions.length === 1 ? "منجز" : "منجزات"
          }${totalCount !== submissions.length ? ` من أصل ${formatNumber(totalCount)}` : ""}`}
        </div>
      </div>

      {/* الجدول */}
      <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
        {submissions.length === 0 ? (
          <EmptyState
            message={
              reviewedFilter === "false"
                ? "لا توجد منجزات بانتظار المراجعة حالياً."
                : "لا توجد منجزات مطابقة لمعايير البحث."
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50">
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    القسم
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    المديرية
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    الأسبوع
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    اعتماد التخطيط
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    حالة المراجعة
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    إجراء
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {submissions.map((sub: WeeklySubmission) => (
                  <SubmissionRow
                    key={sub.id}
                    submission={sub}
                    onReview={() => openReviewModal(sub.id)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ترقيم الصفحات */}
      {(hasNext || hasPrev) && (
        <div className="flex items-center justify-between gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={!hasPrev}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            الصفحة السابقة
          </Button>
          <span className="text-xs text-gray-500">
            صفحة {formatNumber(page)}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={!hasNext}
            onClick={() => setPage((p) => p + 1)}
          >
            الصفحة التالية
          </Button>
        </div>
      )}

      <AdminReviewModal
        submissionId={reviewSubmissionId}
        open={modalOpen}
        onClose={closeReviewModal}
      />
    </div>
  );
}

// ─────────────────────────────────────────────────
// مكوّنات مساعدة
// ─────────────────────────────────────────────────

function SubmissionRow({
  submission,
  onReview,
}: {
  submission: WeeklySubmission;
  onReview: () => void;
}) {
  const isReviewed = submission.admin_reviewed_at !== null;
  const action = submission.admin_review_action;

  return (
    <tr className="hover:bg-gray-50 transition">
      <td className="py-3 px-4 font-medium text-gray-900">
        {submission.qism_name}
      </td>
      <td className="py-3 px-4 text-gray-500 text-xs">
        {submission.qism_parent_name ?? "—"}
      </td>
      <td className="py-3 px-4 text-gray-600">
        الأسبوع {formatNumber(submission.period_week_number)} /{" "}
        {formatNumber(submission.period_year)}
      </td>
      <td className="py-3 px-4 text-gray-600">
        {submission.planning_approved_at ? (
          <div className="text-xs">
            <div className="font-medium text-gray-700">
              {submission.planning_approved_by_name ?? "—"}
            </div>
            <div className="text-gray-500">
              {formatDateTime(submission.planning_approved_at)}
            </div>
          </div>
        ) : (
          <span className="text-gray-400">—</span>
        )}
      </td>
      <td className="py-3 px-4">
        {isReviewed ? (
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className={cn(
                "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold",
                action
                  ? ADMIN_ACTION_COLORS[action] ?? "bg-gray-100 text-gray-700"
                  : "bg-gray-100 text-gray-700"
              )}
            >
              {action === "edited" ? <Pencil className="w-3 h-3" /> : <Lock className="w-3 h-3" />}
              {action ? ADMIN_ACTION_LABELS[action] ?? "مُراجَع" : "مُراجَع"}
            </span>
            {submission.admin_reviewed_by_name && (
              <span className="text-xs text-gray-500">
                {submission.admin_reviewed_by_name}
              </span>
            )}
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <StatusBadge status="submitted" />
            <span className="text-xs text-amber-700">بانتظار المراجعة</span>
          </div>
        )}
      </td>
      <td className="py-3 px-4">
        <Button variant="ghost" size="sm" onClick={onReview}>
          <Eye className="w-4 h-4 ml-1" />
          {isReviewed ? "عرض" : "مراجعة"}
        </Button>
      </td>
    </tr>
  );
}

function StatChip({
  label,
  value,
  color,
  icon,
}: {
  label: string;
  value: number;
  color: "amber" | "blue";
  icon: React.ReactNode;
}) {
  const colorClass = {
    amber: "bg-amber-50 border-amber-200 text-amber-900",
    blue: "bg-blue-50 border-blue-200 text-blue-900",
  }[color];
  return (
    <div
      className={cn(
        "inline-flex items-center gap-2 rounded-lg border px-3 py-1.5 text-sm",
        colorClass
      )}
    >
      {icon}
      <span className="text-xs">{label}:</span>
      <strong>{formatNumber(value)}</strong>
    </div>
  );
}
