"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { getComplianceReport } from "@/lib/api/reports";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { EmptyState } from "@/components/shared/EmptyState";
import { formatNumber, formatPercent } from "@/lib/utils";
import type { ReportFilterValues } from "./ReportFilters";
import { getEffectiveUnitId } from "./ReportFilters";
import {
  HierarchicalTree,
  useBuildHierarchy,
} from "./HierarchicalTree";

interface Props {
  filters: ReportFilterValues;
}

// نضيف qism_id كمفتاح رئيسي للـ hierarchy
interface ComplianceRowWithId {
  qism_id: number;
  qism_name: string;
  total_periods: number;
  submitted: number;
  late: number;
  not_submitted: number;
  compliance_rate: number;
}

export function ComplianceTab({ filters }: Props) {
  const unitId = getEffectiveUnitId(filters);
  const params: Record<string, string> = { year: filters.year.toString() };
  if (unitId) params.unit_id = unitId;

  const { data: compliance, isLoading } = useQuery({
    queryKey: ["compliance-tab", params],
    queryFn: () => getComplianceReport(params),
  });

  // إحصاءات إجمالية
  const stats = useMemo(() => {
    if (!compliance || compliance.length === 0) {
      return { avgRate: 0, total: 0, fullyCompliant: 0, atRisk: 0 };
    }
    const total = compliance.length;
    const sum = compliance.reduce((acc, r) => acc + r.compliance_rate, 0);
    const avgRate = total > 0 ? sum / total : 0;
    const fullyCompliant = compliance.filter(
      (r) => r.compliance_rate >= 95
    ).length;
    const atRisk = compliance.filter((r) => r.compliance_rate < 50).length;
    return { avgRate, total, fullyCompliant, atRisk };
  }, [compliance]);

  // بناء الشجرة الهرمية
  const tree = useBuildHierarchy<ComplianceRowWithId>(
    (compliance || []) as ComplianceRowWithId[],
    ({ unit, descendantQismIds, ownData }) => {
      if (unit.unit_type === "qism" && ownData) {
        return {
          rate: formatPercent(ownData.compliance_rate),
          submitted: formatNumber(ownData.submitted),
          late: formatNumber(ownData.late),
          not_submitted: formatNumber(ownData.not_submitted),
        };
      }

      // عقدة أعلى: حساب متوسط النسبة من أقسام الأحفاد
      const descendantRows = (compliance || []).filter((r) =>
        descendantQismIds.includes(r.qism_id)
      );
      if (descendantRows.length === 0) {
        return {
          rate: "—",
          submitted: "—",
          late: "—",
          not_submitted: "—",
        };
      }
      const avgRate =
        descendantRows.reduce((a, r) => a + r.compliance_rate, 0) /
        descendantRows.length;
      const submitted = descendantRows.reduce((a, r) => a + r.submitted, 0);
      const late = descendantRows.reduce((a, r) => a + r.late, 0);
      const notSubmitted = descendantRows.reduce(
        (a, r) => a + r.not_submitted,
        0
      );
      return {
        rate: formatPercent(avgRate),
        submitted: formatNumber(submitted),
        late: formatNumber(late),
        not_submitted: formatNumber(notSubmitted),
      };
    }
  );

  if (isLoading) return <LoadingSpinner size="lg" />;
  if (!compliance || compliance.length === 0) {
    return <EmptyState message="لا توجد بيانات التزام للفترة المحدّدة." />;
  }

  return (
    <div className="space-y-6">
      {/* ── إحصاءات سريعة ── */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard
          label="متوسط الالتزام"
          value={formatPercent(stats.avgRate)}
          bg="bg-blue-50"
          color="text-blue-700"
        />
        <StatCard
          label="أقسام ملتزمة بالكامل"
          value={`${formatNumber(stats.fullyCompliant)} / ${formatNumber(
            stats.total
          )}`}
          bg="bg-green-50"
          color="text-green-700"
          hint="النسبة ≥ 95%"
        />
        <StatCard
          label="أقسام متعثّرة"
          value={formatNumber(stats.atRisk)}
          bg="bg-red-50"
          color="text-red-700"
          hint="النسبة < 50%"
        />
        <StatCard
          label="إجمالي الأقسام"
          value={formatNumber(stats.total)}
          bg="bg-gray-50"
          color="text-gray-700"
        />
      </div>

      {/* ── العرض الهرمي ── */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold text-gray-900">
            تفصيل الالتزام حسب الهيكل التنظيمي
          </h2>
          <p className="text-xs text-gray-500">
            💡 اضغط على الدائرة أو المديرية لتوسيع تفصيل الأقسام التابعة
          </p>
        </div>
        <HierarchicalTree
          data={tree}
          columns={[
            { key: "rate", label: "نسبة الالتزام", align: "left" },
            { key: "submitted", label: "مُقدَّم", align: "left" },
            { key: "late", label: "متأخر", align: "left" },
            { key: "not_submitted", label: "غير مُقدَّم", align: "left" },
          ]}
        />
      </section>
    </div>
  );
}

function StatCard({
  label,
  value,
  bg,
  color,
  hint,
}: {
  label: string;
  value: string | number;
  bg: string;
  color: string;
  hint?: string;
}) {
  return (
    <div className={`${bg} rounded-xl p-4 border border-white shadow-sm`}>
      <div className="text-xs text-gray-600 mb-1">{label}</div>
      <div className={`text-2xl font-bold ${color}`} dir="ltr">
        {value}
      </div>
      {hint && <div className="text-xs text-gray-500 mt-1">{hint}</div>}
    </div>
  );
}
