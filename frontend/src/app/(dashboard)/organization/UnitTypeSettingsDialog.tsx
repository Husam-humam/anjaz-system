"use client";

import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getUnitTypeMappings,
  refreshUnitTypeMappings,
  updateUnitTypeMapping,
} from "@/lib/api/organization";
import type {
  ExternalUnitTypeMapping,
  UnitTypeTreatment,
} from "@/types/organization";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { getErrorMessage } from "@/lib/utils";
import { AlertCircle, CheckCircle2, RefreshCw } from "lucide-react";

interface Props {
  open: boolean;
  onClose: () => void;
}

const TREATMENT_LABELS: Record<string, string> = {
  daira: "دائرة",
  mudiriya: "مديرية",
  qism: "قسم",
  ignore: "تجاهل",
};

const TREATMENT_DESCRIPTIONS: Record<string, string> = {
  daira: "وحدة جذريّة في الهيكل",
  mudiriya: "تتبع دائرة",
  qism: "تُرسل المنجزات",
  ignore: "لا تُستورَد",
};

const TREATMENT_COLORS: Record<string, string> = {
  daira: "bg-purple-50 text-purple-700 border-purple-200",
  mudiriya: "bg-blue-50 text-blue-700 border-blue-200",
  qism: "bg-teal-50 text-teal-700 border-teal-200",
  ignore: "bg-gray-50 text-gray-500 border-gray-200",
};

export function UnitTypeSettingsDialog({ open, onClose }: Props) {
  const queryClient = useQueryClient();
  const [actionError, setActionError] = useState<string | null>(null);
  const [refreshReport, setRefreshReport] = useState<{
    created: number;
    existing: number;
  } | null>(null);

  useEffect(() => {
    if (!open) {
      setActionError(null);
      setRefreshReport(null);
    }
  }, [open]);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["unit-type-mappings"],
    queryFn: getUnitTypeMappings,
    enabled: open,
  });

  const refreshMutation = useMutation({
    mutationFn: () => refreshUnitTypeMappings(),
    onSuccess: (report) => {
      setRefreshReport({ created: report.created, existing: report.existing });
      setActionError(null);
      queryClient.invalidateQueries({ queryKey: ["unit-type-mappings"] });
    },
    onError: (err) => setActionError(getErrorMessage(err)),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, treat_as }: { id: number; treat_as: UnitTypeTreatment }) =>
      updateUnitTypeMapping(id, treat_as),
    onSuccess: () => {
      setActionError(null);
      queryClient.invalidateQueries({ queryKey: ["unit-type-mappings"] });
    },
    onError: (err) => setActionError(getErrorMessage(err)),
  });

  const mappings = data?.results ?? [];
  const unmappedCount = mappings.filter((m) => !m.treat_as).length;

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto">
        <DialogHeader className="pl-8">
          <DialogTitle className="text-xl">إعدادات أنواع الوحدات</DialogTitle>
          <DialogDescription>
            حدّد كيف تُعامَل كل نوع وحدة من النظام الخارجي. الأنواع الجديدة تُكتشف
            تلقائياً عند كل مزامنة.
          </DialogDescription>
        </DialogHeader>

        {actionError && (
          <div className="bg-red-50 border border-red-200 rounded-md p-3 flex items-start gap-2">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-red-700 break-words">{actionError}</p>
          </div>
        )}

        {refreshReport && (
          <div className="bg-emerald-50 border border-emerald-200 rounded-md p-3 flex items-start gap-2">
            <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-emerald-700">
              تم جلب الأنواع: <strong>{refreshReport.created}</strong> جديد،{" "}
              <strong>{refreshReport.existing}</strong> موجود مسبقاً.
            </p>
          </div>
        )}

        {/* شريط أعلى الجدول */}
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="text-sm text-gray-600">
            {mappings.length} نوعاً
            {unmappedCount > 0 && (
              <span className="mr-2 inline-flex items-center rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-800">
                {unmappedCount} غير محدَّد
              </span>
            )}
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => refreshMutation.mutate()}
            disabled={refreshMutation.isPending}
          >
            <RefreshCw
              className={`w-4 h-4 ml-1 ${
                refreshMutation.isPending ? "animate-spin" : ""
              }`}
            />
            {refreshMutation.isPending ? "جارٍ الجلب..." : "جلب من النظام الخارجي"}
          </Button>
        </div>

        {isLoading ? (
          <LoadingSpinner size="md" />
        ) : isError ? (
          <div className="text-center text-sm text-red-600 py-6">
            تعذّر تحميل الإعدادات.{" "}
            <button onClick={() => refetch()} className="underline">
              إعادة المحاولة
            </button>
          </div>
        ) : mappings.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            لا توجد أنواع بعد. اضغط «جلب من النظام الخارجي».
          </div>
        ) : (
          <div className="border rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b text-right">
                  <th className="py-2.5 px-4 font-semibold text-gray-700">
                    اسم النوع (خارجي)
                  </th>
                  <th className="py-2.5 px-4 font-semibold text-gray-700">
                    يُعامَل كـ
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {mappings.map((m: ExternalUnitTypeMapping) => (
                  <tr key={m.id} className="hover:bg-gray-50">
                    <td className="py-2.5 px-4">
                      <div className="font-medium text-gray-900">
                        {m.external_type_name}
                      </div>
                      {m.external_type_id != null && (
                        <div className="text-xs text-gray-400 font-mono">
                          ID: {m.external_type_id}
                        </div>
                      )}
                    </td>
                    <td className="py-2.5 px-4">
                      <div className="flex items-center gap-2">
                        <select
                          value={m.treat_as ?? ""}
                          onChange={(e) => {
                            const val = e.target.value || null;
                            updateMutation.mutate({
                              id: m.id,
                              treat_as: val as UnitTypeTreatment,
                            });
                          }}
                          disabled={updateMutation.isPending}
                          className={`flex-1 h-9 rounded-md border px-2 text-sm text-right ${
                            m.treat_as
                              ? TREATMENT_COLORS[m.treat_as] ?? "border-input"
                              : "border-amber-300 bg-amber-50 text-amber-900"
                          }`}
                          dir="rtl"
                        >
                          <option value="">— غير محدَّد —</option>
                          {Object.entries(TREATMENT_LABELS).map(([k, label]) => (
                            <option key={k} value={k}>
                              {label} — {TREATMENT_DESCRIPTIONS[k]}
                            </option>
                          ))}
                        </select>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="bg-blue-50 border border-blue-100 rounded-md p-3 text-xs text-blue-700">
          <p className="leading-relaxed">
            <strong>ملاحظة:</strong> الأنواع غير المحدّدة (تظهر باللون البرتقالي)
            تُتجاهَل أثناء المزامنة. التغييرات تُطبَّق في المزامنة التالية.
          </p>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            إغلاق
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
