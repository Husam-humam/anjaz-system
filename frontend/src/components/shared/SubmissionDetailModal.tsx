"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { getPeriodAggregated } from "@/lib/api/submissions";
import type {
  AggregatedIndicator,
  PeriodAggregatedData,
  QismSubmissionInfo,
  SubmissionAnswerDetail,
} from "@/lib/api/submissions";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { EmptyState } from "@/components/shared/EmptyState";
import { formatNumber, formatDate } from "@/lib/utils";
import { ACCUMULATION_TYPE_LABELS } from "@/lib/constants";
import {
  ArrowRight,
  Building,
  CalendarDays,
  CheckCircle2,
  Clock,
  FileText,
  Layers,
  FolderTree,
  Target as TargetIcon,
  User,
  AlertCircle,
} from "lucide-react";

export interface ScopeUnitRef {
  id: number | null;
  name: string;
  unit_type: "institution" | "daira" | "mudiriya" | "qism";
}

interface Props {
  periodId: number | null;
  scope: ScopeUnitRef | null;
  open: boolean;
  onClose: () => void;
}

const STATUS_LABELS: Record<string, string> = {
  approved: "معتمد",
  submitted: "مُرسل",
  draft: "مسودة",
  late: "متأخر",
  extended: "مُمدَّد",
  returned: "مُرجَع",
  not_submitted: "غير مُقدَّم",
};

const STATUS_COLORS: Record<string, string> = {
  approved: "bg-green-100 text-green-800 border-green-200",
  submitted: "bg-blue-100 text-blue-800 border-blue-200",
  draft: "bg-amber-100 text-amber-800 border-amber-200",
  late: "bg-red-100 text-red-800 border-red-200",
  extended: "bg-purple-100 text-purple-800 border-purple-200",
  returned: "bg-pink-100 text-pink-800 border-pink-200",
  not_submitted: "bg-gray-100 text-gray-600 border-gray-200",
};

const UNIT_TYPE_ICONS = {
  institution: Building,
  daira: FolderTree,
  mudiriya: Layers,
  qism: TargetIcon,
};

const UNIT_TYPE_LABELS = {
  institution: "المؤسسة كاملة",
  daira: "دائرة",
  mudiriya: "مديرية",
  qism: "قسم",
};

export function SubmissionDetailModal({
  periodId,
  scope,
  open,
  onClose,
}: Props) {
  // نحافظ على stack من النطاقات لتسهيل الرجوع (drill in / back)
  const [scopeStack, setScopeStack] = useState<ScopeUnitRef[]>([]);
  const currentScope =
    scopeStack.length > 0 ? scopeStack[scopeStack.length - 1] : scope;

  // reset عند فتح/إغلاق
  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) {
      setScopeStack([]);
      onClose();
    }
  };

  const drillInto = (newScope: ScopeUnitRef) => {
    setScopeStack((prev) => [...prev, newScope]);
  };

  const goBack = () => {
    setScopeStack((prev) => prev.slice(0, -1));
  };

  const { data, isLoading } = useQuery({
    queryKey: [
      "period-aggregated",
      periodId,
      currentScope?.id,
    ],
    queryFn: () =>
      periodId !== null
        ? getPeriodAggregated(periodId, currentScope?.id ?? null)
        : Promise.reject(new Error("no period")),
    enabled: open && periodId !== null,
  });

  const Icon = currentScope
    ? UNIT_TYPE_ICONS[currentScope.unit_type] || Building
    : Building;

  const titleLabel = currentScope
    ? `${UNIT_TYPE_LABELS[currentScope.unit_type]}: ${currentScope.name}`
    : "المؤسسة كاملة";

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Icon className="w-5 h-5 text-primary-600" />
            <span>{titleLabel}</span>
            {data?.period && (
              <span className="text-sm font-normal text-gray-500 mr-2">
                — الأسبوع {data.period.week_number}/{data.period.year}
              </span>
            )}
          </DialogTitle>
          <DialogDescription>
            {data?.period && (
              <span className="flex items-center gap-1 text-xs">
                <CalendarDays className="w-3 h-3" />
                {formatDate(data.period.start_date)} →{" "}
                {formatDate(data.period.end_date)}
              </span>
            )}
          </DialogDescription>
        </DialogHeader>

        {/* شريط التنقّل — Back button لو في drill-in stack */}
        {scopeStack.length > 0 && (
          <div className="flex items-center gap-2 pb-3 border-b border-gray-200">
            <Button variant="ghost" size="sm" onClick={goBack}>
              <ArrowRight className="w-4 h-4 ml-1" />
              رجوع
            </Button>
          </div>
        )}

        {isLoading ? (
          <LoadingSpinner size="lg" />
        ) : !data ? (
          <EmptyState message="لا توجد بيانات." />
        ) : data.mode === "qism" ? (
          <QismSubmissionView data={data} />
        ) : (
          <GroupView data={data} onDrillIn={drillInto} />
        )}
      </DialogContent>
    </Dialog>
  );
}

// ═══════════════════════════════════════════════
// Qism view — استمارة منجز قسم كامل
// ═══════════════════════════════════════════════
function QismSubmissionView({ data }: { data: PeriodAggregatedData }) {
  const sub = data.qism_submission;
  if (!sub) {
    return (
      <div className="py-8 text-center">
        <AlertCircle className="w-12 h-12 text-amber-500 mx-auto mb-3" />
        <h3 className="font-semibold text-gray-700 mb-1">
          لم يُقدَّم منجز لهذا القسم في هذا الأسبوع
        </h3>
        <p className="text-sm text-gray-500">
          القسم لم يُرسل استمارته بعد للفترة المختارة.
        </p>
      </div>
    );
  }

  const statusLabel = STATUS_LABELS[sub.status] || sub.status;
  const statusColor = STATUS_COLORS[sub.status] || STATUS_COLORS.not_submitted;

  // فصل الإجابات الرقمية عن النوعية
  const numericAnswers = sub.answers.filter((a) => !a.is_qualitative);
  const qualitativeAnswers = sub.answers.filter((a) => a.is_qualitative);

  return (
    <div className="space-y-4 py-3">
      {/* ترويسة الحالة */}
      <div className="bg-gray-50 rounded-lg p-4 space-y-2">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <span
            className={`inline-flex items-center gap-1 px-3 py-1 rounded-md text-sm font-medium border ${statusColor}`}
          >
            <CheckCircle2 className="w-4 h-4" />
            {statusLabel}
          </span>
          {sub.submitted_at && (
            <div className="flex items-center gap-1 text-xs text-gray-500">
              <Clock className="w-3 h-3" />
              أُرسل في: {formatDate(sub.submitted_at)}
            </div>
          )}
        </div>
        {sub.planning_approved_by && (
          <div className="flex items-center gap-1 text-xs text-gray-600">
            <User className="w-3 h-3" />
            اعتمد بواسطة: <span className="font-medium">{sub.planning_approved_by}</span>
          </div>
        )}
      </div>

      {/* المؤشرات الرقمية */}
      {numericAnswers.length > 0 && (
        <section>
          <h3 className="text-sm font-semibold text-gray-800 mb-2 flex items-center gap-1">
            <TargetIcon className="w-4 h-4 text-blue-600" />
            المؤشرات الرقمية
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {numericAnswers.map((ans) => (
              <NumericAnswerCard key={ans.id} answer={ans} />
            ))}
          </div>
        </section>
      )}

      {/* المنجزات النوعية */}
      {qualitativeAnswers.length > 0 && (
        <section>
          <h3 className="text-sm font-semibold text-gray-800 mb-2 flex items-center gap-1">
            <FileText className="w-4 h-4 text-amber-600" />
            المنجزات النوعية
          </h3>
          <div className="space-y-2">
            {qualitativeAnswers.map((ans) => (
              <QualitativeAnswerCard key={ans.id} answer={ans} />
            ))}
          </div>
        </section>
      )}

      {/* الملاحظات */}
      {sub.notes && (
        <section>
          <h3 className="text-sm font-semibold text-gray-800 mb-1">ملاحظات</h3>
          <div className="bg-gray-50 rounded-md p-3 text-sm text-gray-700 whitespace-pre-wrap">
            {sub.notes}
          </div>
        </section>
      )}

      {sub.answers.length === 0 && (
        <EmptyState message="الاستمارة فارغة." />
      )}
    </div>
  );
}

function NumericAnswerCard({ answer }: { answer: SubmissionAnswerDetail }) {
  const hasValue = answer.numeric_value !== null || answer.text_value;
  return (
    <div className="bg-white border rounded-md p-3">
      <div className="text-xs text-gray-500 mb-1">
        {answer.indicator_category && (
          <span className="inline-block px-1.5 py-0.5 rounded bg-gray-100 text-gray-600 ml-2">
            {answer.indicator_category}
          </span>
        )}
        {answer.is_mandatory && (
          <span className="text-red-500 mr-1">إلزامي</span>
        )}
      </div>
      <div className="text-sm font-medium text-gray-800 mb-1">
        {answer.indicator_name}
      </div>
      <div className="text-lg font-bold text-blue-700" dir="ltr">
        {hasValue ? (
          <>
            {answer.numeric_value !== null
              ? formatNumber(answer.numeric_value)
              : answer.text_value}
            {answer.indicator_unit_label && (
              <span className="text-xs text-gray-500 mr-1">
                {answer.indicator_unit_label}
              </span>
            )}
          </>
        ) : (
          <span className="text-gray-400">—</span>
        )}
      </div>
    </div>
  );
}

function QualitativeAnswerCard({
  answer,
}: {
  answer: SubmissionAnswerDetail;
}) {
  return (
    <div className="bg-amber-50/50 border border-amber-200 rounded-md p-3">
      <div className="flex items-start justify-between mb-1">
        <div className="font-medium text-gray-800 text-sm">
          {answer.indicator_name}
        </div>
        <span className="text-xs px-1.5 py-0.5 rounded bg-amber-100 text-amber-800">
          {answer.qualitative_status === "approved"
            ? "معتمد"
            : answer.qualitative_status === "pending_statistics"
            ? "بانتظار الاعتماد"
            : answer.qualitative_status === "pending_planning"
            ? "قيد مراجعة التخطيط"
            : answer.qualitative_status}
        </span>
      </div>
      <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
        {answer.qualitative_details || (
          <span className="italic text-gray-400">لا توجد تفاصيل</span>
        )}
      </p>
    </div>
  );
}

// ═══════════════════════════════════════════════
// Group view — تجميع على مستوى مديرية/دائرة/مؤسسة
// ═══════════════════════════════════════════════
function GroupView({
  data,
  onDrillIn,
}: {
  data: PeriodAggregatedData;
  onDrillIn: (scope: ScopeUnitRef) => void;
}) {
  const { stats, aggregated_indicators, qism_submissions, qualitative_answers } =
    data;

  if (stats.total === 0) {
    return <EmptyState message="لا توجد أقسام في هذا النطاق." />;
  }

  // تصنيف المؤشرات
  const grouped: Record<string, AggregatedIndicator[]> = {};
  aggregated_indicators.forEach((ind) => {
    const cat = ind.indicator_category || "أخرى";
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(ind);
  });

  return (
    <div className="space-y-5 py-3">
      {/* إحصاءات سريعة */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatBox
          label="إجمالي الأقسام"
          value={formatNumber(stats.total)}
          color="text-gray-700 bg-gray-50"
        />
        <StatBox
          label="معتمدة"
          value={formatNumber(stats.approved)}
          color="text-green-700 bg-green-50"
        />
        <StatBox
          label="متأخرة"
          value={formatNumber(stats.late)}
          color="text-red-700 bg-red-50"
        />
        <StatBox
          label="غير مُقدَّمة"
          value={formatNumber(stats.not_submitted)}
          color="text-gray-600 bg-gray-50"
        />
      </div>

      {/* المؤشرات المُجمّعة */}
      {aggregated_indicators.length > 0 ? (
        <section>
          <h3 className="text-sm font-semibold text-gray-800 mb-2">
            القيم الإجمالية للمؤشرات
          </h3>
          <div className="space-y-3">
            {Object.entries(grouped).map(([category, inds]) => (
              <div key={category}>
                <div className="text-xs text-gray-500 mb-1">{category}</div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {inds.map((ind) => (
                    <AggregatedIndicatorCard
                      key={ind.indicator_id}
                      indicator={ind}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : (
        <section>
          <h3 className="text-sm font-semibold text-gray-800 mb-2">
            القيم الإجمالية للمؤشرات
          </h3>
          <EmptyState message="لم تُقدّم منجزات تحتوي إجابات رقمية." />
        </section>
      )}

      {/* المنجزات النوعية */}
      {qualitative_answers.length > 0 && (
        <section>
          <h3 className="text-sm font-semibold text-gray-800 mb-2 flex items-center gap-1">
            <FileText className="w-4 h-4 text-amber-600" />
            المنجزات النوعية المعتمدة ({formatNumber(qualitative_answers.length)})
          </h3>
          <div className="space-y-2 max-h-[200px] overflow-y-auto">
            {qualitative_answers.map((qa) => (
              <div
                key={qa.id}
                className="bg-amber-50/50 border border-amber-200 rounded-md p-3 text-sm"
              >
                <div className="text-xs text-amber-900 mb-1">
                  {qa.qism_name} — {qa.indicator_name}
                </div>
                <p className="text-gray-700 whitespace-pre-wrap leading-relaxed">
                  {qa.details}
                </p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* قائمة الأقسام (قابلة للضغط) */}
      <section>
        <h3 className="text-sm font-semibold text-gray-800 mb-2">
          الأقسام ضمن النطاق
        </h3>
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
                <th className="text-right py-2 px-3 font-semibold text-gray-700 w-20"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {qism_submissions.map((q) => {
                const statusColor =
                  STATUS_COLORS[q.status] || STATUS_COLORS.not_submitted;
                return (
                  <tr key={q.qism_id} className="hover:bg-gray-50 transition">
                    <td className="py-2 px-3">
                      <div className="font-medium text-gray-900">
                        {q.qism_name}
                      </div>
                      <div className="text-xs text-gray-400" dir="ltr">
                        {q.qism_code}
                      </div>
                    </td>
                    <td className="py-2 px-3">
                      <span
                        className={`inline-block px-2 py-0.5 rounded-md text-xs font-medium border ${statusColor}`}
                      >
                        {STATUS_LABELS[q.status] || q.status}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-left">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() =>
                          onDrillIn({
                            id: q.qism_id,
                            name: q.qism_name,
                            unit_type: "qism",
                          })
                        }
                      >
                        عرض
                      </Button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function StatBox({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color: string;
}) {
  return (
    <div className={`rounded-lg p-3 ${color}`}>
      <div className="text-xs mb-1 opacity-80">{label}</div>
      <div className="text-xl font-bold" dir="ltr">
        {value}
      </div>
    </div>
  );
}

function AggregatedIndicatorCard({
  indicator,
}: {
  indicator: AggregatedIndicator;
}) {
  return (
    <div className="bg-white border rounded-md p-3">
      <div className="text-sm font-medium text-gray-800 mb-1">
        {indicator.indicator_name}
      </div>
      <div className="flex items-end justify-between">
        <div className="text-xl font-bold text-blue-700" dir="ltr">
          {formatNumber(indicator.aggregated_value)}
          {indicator.indicator_unit_label && (
            <span className="text-xs text-gray-500 mr-1">
              {indicator.indicator_unit_label}
            </span>
          )}
        </div>
        <div className="text-xs text-gray-500">
          {ACCUMULATION_TYPE_LABELS[indicator.accumulation_type] ||
            indicator.accumulation_type}
          <span className="mx-1">·</span>
          {formatNumber(indicator.contributing_qisms)} قسم مساهم
        </div>
      </div>
    </div>
  );
}
