"use client";

import { useQuery } from "@tanstack/react-query";
import { getQualitativeReport } from "@/lib/api/reports";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { EmptyState } from "@/components/shared/EmptyState";
import { FileText, Calendar, CheckCircle2, Building } from "lucide-react";
import type { ReportFilterValues } from "./ReportFilters";
import { getEffectiveUnitId } from "./ReportFilters";

interface Props {
  filters: ReportFilterValues;
}

export function QualitativeTab({ filters }: Props) {
  const unitId = getEffectiveUnitId(filters);
  const params: Record<string, string> = { year: filters.year.toString() };
  if (unitId) params.unit_id = unitId;

  const { data: items, isLoading } = useQuery({
    queryKey: ["qualitative-report", params],
    queryFn: () => getQualitativeReport(params),
  });

  if (isLoading) return <LoadingSpinner size="lg" />;

  if (!items || items.length === 0) {
    return (
      <div className="space-y-4">
        <InfoBanner />
        <EmptyState message="لا توجد منجزات نوعية معتمدة لهذه الفلاتر." />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <InfoBanner count={items.length} />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {items.map((item) => (
          <article
            key={item.id}
            className="bg-white rounded-xl shadow-sm border p-5 hover:shadow-md transition-shadow"
          >
            {/* Header */}
            <div className="flex items-start justify-between mb-3 pb-3 border-b border-gray-100">
              <div className="flex-1 min-w-0">
                <h4 className="font-semibold text-gray-900 mb-1">
                  {item.indicator_name}
                </h4>
                <div className="flex items-center gap-1 text-xs text-gray-500">
                  <Building className="w-3 h-3" />
                  <span>{item.qism_name}</span>
                </div>
              </div>
              <div className="flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium bg-green-50 text-green-700 border border-green-100">
                <CheckCircle2 className="w-3 h-3" />
                معتمد
              </div>
            </div>

            {/* Details */}
            <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
              {item.qualitative_details || (
                <span className="text-gray-400 italic">
                  لا توجد تفاصيل مُدخلة
                </span>
              )}
            </p>

            {/* Footer */}
            <div className="mt-4 pt-3 border-t border-gray-100 flex items-center justify-between text-xs text-gray-500 flex-wrap gap-2">
              <div className="flex items-center gap-1">
                <Calendar className="w-3 h-3" />
                <span>الأسبوع {item.week_number}</span>
              </div>
              {item.approved_by && (
                <div className="flex items-center gap-1">
                  <span className="text-gray-400">اعتمد بواسطة:</span>
                  <span className="font-medium text-gray-700">
                    {item.approved_by}
                  </span>
                </div>
              )}
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

function InfoBanner({ count }: { count?: number }) {
  return (
    <div className="bg-blue-50 border border-blue-100 rounded-xl p-4 flex items-start gap-3">
      <FileText className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
      <div>
        <p className="text-sm font-medium text-blue-900">
          {count !== undefined
            ? `تم العثور على ${count} منجز نوعي معتمد`
            : "المنجزات النوعية المعتمدة"}
        </p>
        <p className="text-xs text-blue-700 mt-0.5">
          هذه المنجزات النصية التي تمّت الموافقة عليها من قسم الإحصاء بعد اعتماد
          قسم التخطيط. يمكنك فلترتها بالفترة والنطاق.
        </p>
      </div>
    </div>
  );
}
