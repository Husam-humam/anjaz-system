"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getPeriodicReport, exportReport } from "@/lib/api/reports";
import { getOrganizationUnits } from "@/lib/api/organization";
import type { OrganizationUnit } from "@/types/organization";
import { ACCUMULATION_TYPE_LABELS } from "@/lib/constants";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { ErrorState } from "@/components/shared/ErrorState";
import { EmptyState } from "@/components/shared/EmptyState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { FileText, FileSpreadsheet, Search } from "lucide-react";

const PERIOD_TYPE_LABELS: Record<string, string> = {
  weekly: "أسبوعي",
  monthly: "شهري",
  quarterly: "ربع سنوي",
  semi_annual: "نصف سنوي",
  annual: "سنوي",
};

interface ReportRow {
  qism_name: string;
  indicator_name: string;
  aggregated_value: number;
  accumulation_type: string;
  target_value?: number;
  progress_percentage?: number;
}

export default function ReportsPage() {
  const currentYear = new Date().getFullYear();
  const [periodType, setPeriodType] = useState("weekly");
  const [year, setYear] = useState(currentYear);
  const [periodNumber, setPeriodNumber] = useState(1);
  const [unitId, setUnitId] = useState("");
  const [shouldFetch, setShouldFetch] = useState(false);
  const [isExporting, setIsExporting] = useState(false);

  const params: Record<string, string> = {
    period_type: periodType,
    year: year.toString(),
    period_number: periodNumber.toString(),
  };
  if (unitId) params.unit_id = unitId;

  const { data: unitsData } = useQuery({
    queryKey: ["organization-units"],
    queryFn: () => getOrganizationUnits(),
  });

  const {
    data: reportData,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["report", params],
    queryFn: () => getPeriodicReport(params),
    enabled: shouldFetch,
  });

  const handleGenerate = () => {
    setShouldFetch(true);
    refetch();
  };

  const handleExport = async (format: "pdf" | "excel") => {
    setIsExporting(true);
    try {
      const blob = await exportReport({
        format,
        period_type: periodType,
        year: year.toString(),
        period_number: periodNumber.toString(),
        unit_id: unitId || undefined,
      });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `تقرير_${PERIOD_TYPE_LABELS[periodType]}_${year}_${periodNumber}.${
        format === "pdf" ? "pdf" : "xlsx"
      }`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch {
      // يمكن إضافة رسالة خطأ هنا
    } finally {
      setIsExporting(false);
    }
  };

  const units = unitsData?.results || [];
  const reportResults: ReportRow[] =
    (reportData as Record<string, unknown>)?.results as ReportRow[] || [];
  const weeksCount =
    ((reportData as Record<string, unknown>)?.weeks_count as number) || 0;

  return (
    <div className="space-y-6">
      {/* العنوان */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">التقارير</h1>
        <p className="text-gray-500 mt-1">
          توليد وتصدير التقارير الدورية
        </p>
      </div>

      {/* فلاتر التقرير */}
      <div className="bg-white rounded-xl shadow-sm border p-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 items-end">
          <div className="space-y-2">
            <Label htmlFor="report-type">نوع التقرير</Label>
            <select
              id="report-type"
              value={periodType}
              onChange={(e) => setPeriodType(e.target.value)}
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-right"
              dir="rtl"
            >
              {Object.entries(PERIOD_TYPE_LABELS).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="report-year">السنة</Label>
            <Input
              id="report-year"
              type="number"
              value={year}
              onChange={(e) => setYear(parseInt(e.target.value) || currentYear)}
              dir="ltr"
            />
          </div>

          {periodType !== "annual" && (
            <div className="space-y-2">
              <Label htmlFor="report-period">رقم الفترة</Label>
              <Input
                id="report-period"
                type="number"
                min={1}
                value={periodNumber}
                onChange={(e) =>
                  setPeriodNumber(parseInt(e.target.value) || 1)
                }
                dir="ltr"
              />
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="report-unit">الوحدة التنظيمية</Label>
            <select
              id="report-unit"
              value={unitId}
              onChange={(e) => setUnitId(e.target.value)}
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-right"
              dir="rtl"
            >
              <option value="">جميع الوحدات</option>
              {units.map((unit: OrganizationUnit) => (
                <option key={unit.id} value={unit.id.toString()}>
                  {unit.name}
                </option>
              ))}
            </select>
          </div>

          <Button onClick={handleGenerate} className="h-10">
            <Search className="w-4 h-4 ml-2" />
            توليد التقرير
          </Button>
        </div>
      </div>

      {/* نتائج التقرير */}
      {isLoading && <LoadingSpinner size="lg" />}

      {isError && <ErrorState onRetry={handleGenerate} />}

      {reportData && !isLoading && (
        <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
          {/* شريط الأدوات */}
          <div className="p-4 border-b flex items-center justify-between bg-gray-50">
            <div className="flex items-center gap-3">
              <span className="font-semibold text-gray-900">
                نتائج التقرير
              </span>
              {weeksCount > 0 && (
                <span className="text-sm text-gray-500">
                  ({weeksCount} أسبوع)
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleExport("pdf")}
                disabled={isExporting}
                className="text-red-600 border-red-200 hover:bg-red-50"
              >
                <FileText className="w-4 h-4 ml-1" />
                تصدير PDF
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleExport("excel")}
                disabled={isExporting}
                className="text-green-600 border-green-200 hover:bg-green-50"
              >
                <FileSpreadsheet className="w-4 h-4 ml-1" />
                تصدير Excel
              </Button>
            </div>
          </div>

          {/* جدول النتائج */}
          {reportResults.length === 0 ? (
            <EmptyState message="لا توجد بيانات لهذه الفترة." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-gray-50">
                    <th className="text-right py-3 px-4 font-semibold text-gray-700">
                      القسم
                    </th>
                    <th className="text-right py-3 px-4 font-semibold text-gray-700">
                      المؤشر
                    </th>
                    <th className="text-right py-3 px-4 font-semibold text-gray-700">
                      القيمة المجمعة
                    </th>
                    <th className="text-right py-3 px-4 font-semibold text-gray-700">
                      طريقة التجميع
                    </th>
                    <th className="text-right py-3 px-4 font-semibold text-gray-700">
                      المستهدف
                    </th>
                    <th className="text-right py-3 px-4 font-semibold text-gray-700">
                      نسبة الإنجاز
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {reportResults.map((row: ReportRow, idx: number) => (
                    <tr key={idx} className="hover:bg-gray-50 transition">
                      <td className="py-3 px-4 font-medium text-gray-900">
                        {row.qism_name}
                      </td>
                      <td className="py-3 px-4 text-gray-900">
                        {row.indicator_name}
                      </td>
                      <td className="py-3 px-4 font-semibold text-gray-900" dir="ltr">
                        {row.aggregated_value?.toLocaleString("ar-IQ") ?? "—"}
                      </td>
                      <td className="py-3 px-4 text-gray-500">
                        {ACCUMULATION_TYPE_LABELS[row.accumulation_type] ||
                          row.accumulation_type}
                      </td>
                      <td className="py-3 px-4 text-gray-600" dir="ltr">
                        {row.target_value?.toLocaleString("ar-IQ") ?? "—"}
                      </td>
                      <td className="py-3 px-4">
                        {row.progress_percentage !== undefined ? (
                          <div className="flex items-center gap-2">
                            <div className="flex-1 max-w-[100px] bg-gray-200 rounded-full h-2">
                              <div
                                className={`h-2 rounded-full transition-all ${
                                  row.progress_percentage >= 90
                                    ? "bg-green-500"
                                    : row.progress_percentage >= 50
                                    ? "bg-blue-500"
                                    : "bg-amber-500"
                                }`}
                                style={{
                                  width: `${Math.min(
                                    row.progress_percentage,
                                    100
                                  )}%`,
                                }}
                              />
                            </div>
                            <span className="text-xs font-medium text-gray-600 w-10 text-left" dir="ltr">
                              {row.progress_percentage}%
                            </span>
                          </div>
                        ) : (
                          <span className="text-gray-400">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* رسالة ابدأ */}
      {!reportData && !isLoading && !isError && (
        <div className="bg-white rounded-xl shadow-sm border p-12 text-center">
          <FileText className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-700 mb-2">
            اختر معايير التقرير
          </h3>
          <p className="text-sm text-gray-500">
            حدد نوع التقرير والفترة ثم اضغط على &quot;توليد التقرير&quot;
          </p>
        </div>
      )}
    </div>
  );
}
