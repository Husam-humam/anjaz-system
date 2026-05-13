"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getPeriodicReport } from "@/lib/api/reports";
import type {
  IndicatorSummary,
  PeriodicReportRow,
} from "@/lib/api/reports";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { EmptyState } from "@/components/shared/EmptyState";
import { Button } from "@/components/ui/button";
import { AlertCircle, BarChart3, CalendarDays } from "lucide-react";
import { formatNumber } from "@/lib/utils";
import { ACCUMULATION_TYPE_LABELS } from "@/lib/constants";
import {
  HierarchicalTree,
  useBuildHierarchy,
  type TreeNodeData,
} from "./HierarchicalTree";
import type { ReportFilterValues } from "./ReportFilters";
import { getEffectiveUnitId } from "./ReportFilters";

interface Props {
  filters: ReportFilterValues;
}

export function PeriodicTab({ filters }: Props) {
  const unitId = getEffectiveUnitId(filters);
  const [selectedIndicatorId, setSelectedIndicatorId] = useState<number | null>(
    null
  );

  // تأكد من وجود date range
  const hasDateRange = Boolean(filters.fromDate && filters.toDate);

  const params: Record<string, string> = {};
  if (hasDateRange) {
    params.from_date = filters.fromDate!;
    params.to_date = filters.toDate!;
  }
  if (unitId) params.unit_id = unitId;

  const { data: reportData, isLoading } = useQuery({
    queryKey: ["periodic-report", params],
    queryFn: () => getPeriodicReport(params),
    enabled: hasDateRange,
  });

  const results: PeriodicReportRow[] = reportData?.results || [];
  const indicatorSummary: IndicatorSummary[] = reportData?.indicator_summary || [];
  const weeksCount = reportData?.meta?.weeks_count || 0;

  // تصفية التفاصيل بالمؤشر المختار
  const filteredResults = useMemo(() => {
    if (!selectedIndicatorId) return results;
    return results.filter((r) => r.indicator_id === selectedIndicatorId);
  }, [results, selectedIndicatorId]);

  // بناء الشجرة الهرمية للتفاصيل
  const tree = useBuildHierarchy(
    filteredResults,
    ({ unit, descendantQismIds, ownData }) => {
      // لكل عقدة: احسب القيمة المجمّعة ضمن أقسامها
      const relevantRows = results.filter(
        (r) =>
          descendantQismIds.includes(r.qism_id) &&
          (!selectedIndicatorId || r.indicator_id === selectedIndicatorId)
      );

      if (relevantRows.length === 0 && !ownData) {
        return {
          aggregated: "—",
          indicator: "—",
          contributing: 0,
        };
      }

      // لو مؤشر محدّد: جمع القيم المرتبطة به من أقسام العقدة
      if (selectedIndicatorId) {
        const acc = relevantRows[0]?.accumulation_type || "sum";
        const values = relevantRows
          .map((r) => r.aggregated_value)
          .filter((v): v is number => v !== null);
        const aggregated = aggregate(values, acc);
        const indicatorName = relevantRows[0]?.indicator_name || "—";
        return {
          aggregated: aggregated !== null ? formatNumber(aggregated) : "—",
          indicator: indicatorName,
          contributing: `${relevantRows.length} قسم مُساهم`,
        };
      }

      // لا مؤشر محدّد: عدد المؤشرات المقاسة في هذه العقدة
      const uniqueIndicators = new Set(relevantRows.map((r) => r.indicator_id));
      return {
        aggregated: `${uniqueIndicators.size} مؤشر`,
        indicator: "جميع المؤشرات",
        contributing: `${relevantRows.length} إدخال`,
      };
    }
  );

  if (!hasDateRange) {
    return (
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-6 flex items-start gap-3">
        <CalendarDays className="w-6 h-6 text-amber-600 flex-shrink-0 mt-0.5" />
        <div>
          <h3 className="font-semibold text-amber-900 mb-1">
            اختر نطاقاً زمنياً للبدء
          </h3>
          <p className="text-sm text-amber-700">
            حدّد "من تاريخ" و "إلى تاريخ" من الفلاتر أعلاه لعرض التقرير الدوري.
            يمكنك فلترة البيانات لأي نطاق زمني مرن (أسبوع، شهر، عدة أشهر، سنة...).
          </p>
        </div>
      </div>
    );
  }

  if (isLoading) return <LoadingSpinner size="lg" />;

  if (results.length === 0) {
    return (
      <EmptyState message="لا توجد بيانات للفترة المحدّدة. تأكد من وجود منجزات معتمدة." />
    );
  }

  return (
    <div className="space-y-6">
      {/* ── معلومات عن الفترة ── */}
      <div className="bg-white rounded-xl shadow-sm border p-4 flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3 text-sm">
          <CalendarDays className="w-5 h-5 text-blue-600" />
          <div>
            <span className="font-medium text-gray-900">
              التقرير من {filters.fromDate} إلى {filters.toDate}
            </span>
            <span className="text-gray-500 mr-3" dir="ltr">
              ({formatNumber(weeksCount)} أسبوع)
            </span>
          </div>
        </div>
      </div>

      {/* ═══ 1) ملخّص المؤشرات على مستوى النطاق ═══ */}
      <section>
        <div className="flex items-center gap-2 mb-3">
          <BarChart3 className="w-5 h-5 text-blue-600" />
          <h2 className="font-semibold text-gray-900">
            ملخّص المؤشرات — الإجمالي الكلي
          </h2>
        </div>
        <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50">
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    المؤشر
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    التصنيف
                  </th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">
                    القيمة الإجمالية
                  </th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">
                    طريقة التجميع
                  </th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">
                    الأقسام المساهمة
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    عرض التفصيل
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {indicatorSummary.map((row) => {
                  const isSelected = selectedIndicatorId === row.indicator_id;
                  return (
                    <tr
                      key={row.indicator_id}
                      className={
                        isSelected
                          ? "bg-blue-50"
                          : "hover:bg-gray-50 transition"
                      }
                    >
                      <td className="py-3 px-4 font-medium text-gray-900">
                        {row.indicator_name}
                      </td>
                      <td className="py-3 px-4">
                        {row.indicator_category ? (
                          <span className="inline-block px-2 py-0.5 rounded-md text-xs bg-gray-100 text-gray-700">
                            {row.indicator_category}
                          </span>
                        ) : (
                          <span className="text-xs text-gray-400">—</span>
                        )}
                      </td>
                      <td
                        className="py-3 px-4 font-bold text-lg text-blue-700"
                        dir="ltr"
                      >
                        {formatNumber(row.total_value)}
                      </td>
                      <td className="py-3 px-4 text-xs text-gray-500">
                        {ACCUMULATION_TYPE_LABELS[row.accumulation_type] ||
                          row.accumulation_type}
                      </td>
                      <td className="py-3 px-4 text-gray-600" dir="ltr">
                        {formatNumber(row.contributing_qisms)}
                      </td>
                      <td className="py-3 px-4">
                        <Button
                          size="sm"
                          variant={isSelected ? "default" : "outline"}
                          onClick={() =>
                            setSelectedIndicatorId(
                              isSelected ? null : row.indicator_id
                            )
                          }
                        >
                          {isSelected ? "إلغاء التحديد" : "عرض التفصيل"}
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* ═══ 2) تفصيل هرمي (دوائر → مديريات → أقسام) ═══ */}
      <section>
        <div className="flex items-center gap-2 mb-3">
          <h2 className="font-semibold text-gray-900">
            التفصيل الهرمي
            {selectedIndicatorId && (
              <span className="text-blue-600 mr-2 text-sm font-normal">
                — مصفّى للمؤشر المختار
              </span>
            )}
          </h2>
        </div>

        {!selectedIndicatorId && (
          <div className="bg-blue-50 border border-blue-100 rounded-md p-3 flex items-start gap-2 mb-3">
            <AlertCircle className="w-4 h-4 text-blue-600 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-blue-700">
              💡 اختر مؤشراً من الجدول أعلاه لرؤية التفصيل الهرمي لقيمه عبر
              الدوائر والمديريات والأقسام.
            </p>
          </div>
        )}

        <HierarchicalTree
          data={tree}
          columns={[
            { key: "indicator", label: "المؤشر" },
            { key: "aggregated", label: "القيمة / العدد", align: "left" },
            { key: "contributing", label: "المساهمة", align: "left" },
          ]}
        />
      </section>
    </div>
  );
}

// ── helper: تجميع قيم ──
function aggregate(values: number[], accType: string): number | null {
  if (values.length === 0) return null;
  if (accType === "sum") {
    return values.reduce((a, b) => a + b, 0);
  }
  if (accType === "average") {
    return values.reduce((a, b) => a + b, 0) / values.length;
  }
  if (accType === "last_value") {
    return values[values.length - 1];
  }
  return values.reduce((a, b) => a + b, 0);
}
