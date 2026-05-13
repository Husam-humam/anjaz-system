"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { getOrganizationUnits } from "@/lib/api/organization";
import { getIndicatorCategories } from "@/lib/api/indicators";
import type { OrganizationUnit } from "@/types/organization";
import type { IndicatorCategory } from "@/types/indicators";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Filter, RotateCcw } from "lucide-react";

export interface ReportFilterValues {
  year: number;
  dairaId: string;
  mudiriyaId: string;
  qismId: string;
  categoryId: string;
  periodType?: string;
  periodNumber?: number;
  fromDate?: string;
  toDate?: string;
}

interface ReportFiltersProps {
  values: ReportFilterValues;
  onChange: (next: ReportFilterValues) => void;
  showPeriodType?: boolean;
  showPeriodNumber?: boolean;
  showCategory?: boolean;
  showDateRange?: boolean;
}

export function ReportFilters({
  values,
  onChange,
  showPeriodType = false,
  showPeriodNumber = false,
  showCategory = true,
  showDateRange = false,
}: ReportFiltersProps) {
  const currentYear = new Date().getFullYear();

  // دوائر + مديريات + أقسام للـ cascading
  const { data: dairasData } = useQuery({
    queryKey: ["org-units-daira-for-reports"],
    queryFn: () => getOrganizationUnits({ unit_type: "daira" }),
  });
  const { data: mudiriyasData } = useQuery({
    queryKey: ["org-units-mudiriya-for-reports", values.dairaId],
    queryFn: () => {
      const params: Record<string, string> = { unit_type: "mudiriya" };
      if (values.dairaId) params.parent = values.dairaId;
      return getOrganizationUnits(params);
    },
  });
  const { data: qismsData } = useQuery({
    queryKey: [
      "org-units-qism-for-reports",
      values.dairaId,
      values.mudiriyaId,
    ],
    queryFn: () => {
      const params: Record<string, string> = { unit_type: "qism" };
      if (values.mudiriyaId) params.parent = values.mudiriyaId;
      else if (values.dairaId) params.parent = values.dairaId;
      return getOrganizationUnits(params);
    },
  });

  const { data: categoriesData } = useQuery({
    queryKey: ["indicator-categories-for-reports"],
    queryFn: () => getIndicatorCategories(),
  });

  const dairas = dairasData?.results || [];
  const mudiriyas = mudiriyasData?.results || [];
  const qisms = useMemo(
    () =>
      (qismsData?.results || []).filter(
        (q: OrganizationUnit) => q.qism_role === "regular"
      ),
    [qismsData]
  );
  const categories = categoriesData?.results || [];

  const hasAnyFilter =
    values.dairaId ||
    values.mudiriyaId ||
    values.qismId ||
    values.categoryId ||
    values.fromDate ||
    values.toDate ||
    (values.year !== currentYear);

  const reset = () => {
    onChange({
      year: currentYear,
      dairaId: "",
      mudiriyaId: "",
      qismId: "",
      categoryId: "",
      periodType: values.periodType,
      periodNumber: values.periodNumber,
      fromDate: "",
      toDate: "",
    });
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2 text-gray-700">
          <Filter className="w-4 h-4" />
          <span className="text-sm font-medium">فلاتر التقرير</span>
        </div>
        {hasAnyFilter && (
          <Button variant="ghost" size="sm" onClick={reset}>
            <RotateCcw className="w-3.5 h-3.5 ml-1" />
            إعادة التعيين
          </Button>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        {/* date range (اختياري) */}
        {showDateRange && (
          <>
            <div className="space-y-1">
              <Label className="text-xs">من تاريخ</Label>
              <Input
                type="date"
                value={values.fromDate || ""}
                onChange={(e) =>
                  onChange({ ...values, fromDate: e.target.value })
                }
                className="h-10"
                dir="ltr"
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">إلى تاريخ</Label>
              <Input
                type="date"
                value={values.toDate || ""}
                onChange={(e) =>
                  onChange({ ...values, toDate: e.target.value })
                }
                className="h-10"
                dir="ltr"
              />
            </div>
          </>
        )}

        {/* السنة — تُعرض فقط إذا لم يكن date range نشطاً */}
        {!showDateRange && (
          <div className="space-y-1">
            <Label className="text-xs">السنة</Label>
            <select
              value={values.year}
              onChange={(e) =>
                onChange({
                  ...values,
                  year: parseInt(e.target.value) || currentYear,
                })
              }
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              dir="ltr"
            >
              {Array.from({ length: 5 }, (_, i) => currentYear - 2 + i).map(
                (year) => (
                  <option key={year} value={year}>
                    {year}
                  </option>
                )
              )}
            </select>
          </div>
        )}

        {/* الدائرة */}
        <div className="space-y-1">
          <Label className="text-xs">الدائرة</Label>
          <select
            value={values.dairaId}
            onChange={(e) =>
              onChange({
                ...values,
                dairaId: e.target.value,
                mudiriyaId: "",
                qismId: "",
              })
            }
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-right"
            dir="rtl"
          >
            <option value="">جميع الدوائر</option>
            {dairas.map((d: OrganizationUnit) => (
              <option key={d.id} value={d.id.toString()}>
                {d.name}
              </option>
            ))}
          </select>
        </div>

        {/* المديرية */}
        <div className="space-y-1">
          <Label className="text-xs">المديرية</Label>
          <select
            value={values.mudiriyaId}
            onChange={(e) =>
              onChange({
                ...values,
                mudiriyaId: e.target.value,
                qismId: "",
              })
            }
            disabled={mudiriyas.length === 0}
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-right disabled:opacity-60"
            dir="rtl"
          >
            <option value="">جميع المديريات</option>
            {mudiriyas.map((m: OrganizationUnit) => (
              <option key={m.id} value={m.id.toString()}>
                {m.name}
              </option>
            ))}
          </select>
        </div>

        {/* القسم */}
        <div className="space-y-1">
          <Label className="text-xs">القسم</Label>
          <select
            value={values.qismId}
            onChange={(e) => onChange({ ...values, qismId: e.target.value })}
            disabled={qisms.length === 0}
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-right disabled:opacity-60"
            dir="rtl"
          >
            <option value="">جميع الأقسام</option>
            {qisms.map((q: OrganizationUnit) => (
              <option key={q.id} value={q.id.toString()}>
                {q.name}
              </option>
            ))}
          </select>
        </div>

        {/* تصنيف المؤشر (اختياري) */}
        {showCategory && (
          <div className="space-y-1">
            <Label className="text-xs">تصنيف المؤشر</Label>
            <select
              value={values.categoryId}
              onChange={(e) =>
                onChange({ ...values, categoryId: e.target.value })
              }
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-right"
              dir="rtl"
            >
              <option value="">جميع التصنيفات</option>
              {categories.map((c: IndicatorCategory) => (
                <option key={c.id} value={c.id.toString()}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>
    </div>
  );
}

/** يحسب unit_id المؤثر — الأولوية: qism > mudiriya > daira */
export function getEffectiveUnitId(values: ReportFilterValues): string {
  return values.qismId || values.mudiriyaId || values.dairaId || "";
}
