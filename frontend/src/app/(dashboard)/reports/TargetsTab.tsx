"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  PolarAngleAxis,
  RadialBar,
  RadialBarChart,
  ResponsiveContainer,
} from "recharts";
import { getTargets } from "@/lib/api/targets";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { EmptyState } from "@/components/shared/EmptyState";
import { formatNumber, formatPercent } from "@/lib/utils";
import type { Target, TargetScopeLevel } from "@/types/submissions";
import { Building2, FolderTree, Layers, Target as TargetIcon } from "lucide-react";
import type { ReportFilterValues } from "./ReportFilters";

interface Props {
  filters: ReportFilterValues;
}

const SCOPE_LEVEL_CONFIG: Record<
  TargetScopeLevel,
  { label: string; icon: React.ComponentType<{ className?: string }>; color: string; bg: string }
> = {
  institution: {
    label: "المؤسسة كاملة",
    icon: Building2,
    color: "text-purple-700",
    bg: "bg-purple-50 border-purple-200",
  },
  daira: {
    label: "دائرة",
    icon: FolderTree,
    color: "text-blue-700",
    bg: "bg-blue-50 border-blue-200",
  },
  mudiriya: {
    label: "مديرية",
    icon: Layers,
    color: "text-emerald-700",
    bg: "bg-emerald-50 border-emerald-200",
  },
  qism: {
    label: "قسم",
    icon: TargetIcon,
    color: "text-amber-700",
    bg: "bg-amber-50 border-amber-200",
  },
};

export function TargetsTab({ filters }: Props) {
  // المستوى المختار — مؤسسة افتراضياً (رؤية عامة نظيفة)
  const [activeLevel, setActiveLevel] = useState<TargetScopeLevel>("institution");

  const queryParams: Record<string, string> = {
    with_progress: "true",
    year: filters.year.toString(),
    scope_level: activeLevel,
  };
  if (filters.categoryId) queryParams.indicator__category = filters.categoryId;

  // فلتر نطاق محدّد: يعمل فقط عندما يتطابق مع المستوى المختار
  // مثلاً: مستوى "دائرة" + اختيار دائرة معيّنة → يفلتر لتلك الدائرة فقط
  if (activeLevel === "daira" && filters.dairaId) {
    queryParams.scope_unit = filters.dairaId;
  } else if (activeLevel === "mudiriya" && filters.mudiriyaId) {
    queryParams.scope_unit = filters.mudiriyaId;
  } else if (activeLevel === "qism" && filters.qismId) {
    queryParams.scope_unit = filters.qismId;
  }

  const { data: targetsData, isLoading } = useQuery({
    queryKey: ["targets-report-tab", queryParams],
    queryFn: () => getTargets(queryParams),
  });

  const targets = targetsData?.results || [];

  // إحصاءات المستوى المختار
  const stats = useMemo(() => {
    const withProgress = targets.filter((t: Target) => t.progress);
    if (withProgress.length === 0) {
      return { total: targets.length, avgProgress: 0, achieved: 0, atRisk: 0 };
    }
    const totalPct = withProgress.reduce(
      (acc: number, t: Target) => acc + (t.progress?.progress_percentage || 0),
      0
    );
    const achieved = withProgress.filter(
      (t: Target) => (t.progress?.progress_percentage || 0) >= 100
    ).length;
    const atRisk = withProgress.filter(
      (t: Target) => (t.progress?.progress_percentage || 0) < 50
    ).length;
    return {
      total: targets.length,
      avgProgress: totalPct / withProgress.length,
      achieved,
      atRisk,
    };
  }, [targets]);

  // ترتيب تنازلي لجدول المستهدفات
  const sortedTargets = useMemo(() => {
    return [...targets].sort(
      (a: Target, b: Target) =>
        (b.progress?.progress_percentage || 0) -
        (a.progress?.progress_percentage || 0)
    );
  }, [targets]);

  const gaugeData = [
    {
      name: "الإنجاز",
      value: Math.round(stats.avgProgress * 10) / 10,
      fill:
        stats.avgProgress >= 90
          ? "#10b981"
          : stats.avgProgress >= 50
          ? "#3b82f6"
          : "#f59e0b",
    },
  ];

  const levelConfig = SCOPE_LEVEL_CONFIG[activeLevel];

  return (
    <div className="space-y-6">
      {/* ── اختيار المستوى ── */}
      <div className="bg-white rounded-xl shadow-sm border p-4">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-sm font-medium text-gray-700">
            عرض المستهدفات على مستوى:
          </span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {(
            ["institution", "daira", "mudiriya", "qism"] as TargetScopeLevel[]
          ).map((level) => {
            const config = SCOPE_LEVEL_CONFIG[level];
            const Icon = config.icon;
            const isActive = activeLevel === level;
            return (
              <button
                key={level}
                onClick={() => setActiveLevel(level)}
                className={`flex items-center gap-2 p-3 rounded-lg border-2 transition ${
                  isActive
                    ? config.bg + " border-current " + config.color
                    : "bg-white border-gray-200 text-gray-600 hover:bg-gray-50"
                }`}
              >
                <Icon className="w-5 h-5" />
                <span className="font-medium text-sm">{config.label}</span>
              </button>
            );
          })}
        </div>
        {activeLevel !== "institution" && (
          <p className="text-xs text-gray-500 mt-3">
            💡 استخدم فلتر ({SCOPE_LEVEL_CONFIG[activeLevel].label}) في الأعلى
            للتركيز على مستهدفات وحدة معيّنة فقط.
          </p>
        )}
      </div>

      {isLoading ? (
        <LoadingSpinner size="lg" />
      ) : targets.length === 0 ? (
        <EmptyState
          message={`لا توجد مستهدفات على مستوى ${levelConfig.label}.`}
        />
      ) : (
        <>
          {/* ── KPIs ── */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <StatCard
              label="إجمالي المستهدفات"
              value={formatNumber(stats.total)}
              bg="bg-gray-50"
              color="text-gray-700"
            />
            <StatCard
              label="متوسط نسبة التقدم"
              value={formatPercent(stats.avgProgress)}
              bg="bg-blue-50"
              color="text-blue-700"
            />
            <StatCard
              label="مستهدفات محقّقة"
              value={formatNumber(stats.achieved)}
              hint="التقدم ≥ 100%"
              bg="bg-green-50"
              color="text-green-700"
            />
            <StatCard
              label="مستهدفات متعثّرة"
              value={formatNumber(stats.atRisk)}
              hint="التقدم < 50%"
              bg="bg-red-50"
              color="text-red-700"
            />
          </div>

          {/* ── عدّاد دائري ── */}
          <div className="bg-white rounded-xl shadow-sm border p-4">
            <h3 className="font-semibold text-gray-900 mb-1">
              متوسط التقدم الإجمالي
            </h3>
            <p className="text-xs text-gray-500 mb-3">
              متوسط نسب تحقّق كل المستهدفات على مستوى {levelConfig.label}
            </p>
            <ResponsiveContainer width="100%" height={220}>
              <RadialBarChart
                cx="50%"
                cy="50%"
                innerRadius="60%"
                outerRadius="100%"
                data={gaugeData}
                startAngle={90}
                endAngle={-270}
              >
                <PolarAngleAxis
                  type="number"
                  domain={[0, 100]}
                  angleAxisId={0}
                  tick={false}
                />
                <RadialBar
                  background
                  dataKey="value"
                  cornerRadius={10}
                  fill={gaugeData[0].fill}
                />
                <text
                  x="50%"
                  y="50%"
                  textAnchor="middle"
                  dominantBaseline="middle"
                  className="fill-gray-900"
                  style={{ fontSize: 32, fontWeight: 700 }}
                >
                  {formatPercent(stats.avgProgress)}
                </text>
              </RadialBarChart>
            </ResponsiveContainer>
          </div>

          {/* ── جدول المستهدفات ── */}
          <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
            <div className="p-4 border-b bg-gray-50">
              <h3 className="font-semibold text-gray-900">
                جميع مستهدفات {levelConfig.label} ({formatNumber(stats.total)})
              </h3>
              <p className="text-xs text-gray-500 mt-0.5">
                مرتّبة تنازلياً حسب نسبة التقدم
              </p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-gray-50">
                    <th className="text-right py-3 px-4 font-semibold text-gray-700">
                      المستهدف
                    </th>
                    <th className="text-right py-3 px-4 font-semibold text-gray-700">
                      النطاق
                    </th>
                    <th className="text-right py-3 px-4 font-semibold text-gray-700">
                      التصنيف
                    </th>
                    <th className="text-left py-3 px-4 font-semibold text-gray-700">
                      المحقّق / المستهدف
                    </th>
                    <th className="text-left py-3 px-4 font-semibold text-gray-700 min-w-[180px]">
                      التقدم
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {sortedTargets.map((target: Target) => {
                    const pct = target.progress?.progress_percentage || 0;
                    return (
                      <tr
                        key={target.id}
                        className="hover:bg-gray-50 transition"
                      >
                        <td className="py-3 px-4 font-medium text-gray-900">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span>{target.name}</span>
                            {target.indicators.length > 1 && (
                              <span
                                className="inline-block px-2 py-0.5 rounded-md text-[10px] font-medium bg-indigo-50 text-indigo-700 border border-indigo-200"
                                title={target.indicators
                                  .map((i) => i.name)
                                  .join("، ")}
                              >
                                {target.indicators.length.toLocaleString(
                                  "ar-IQ"
                                )}{" "}
                                مكوّنات
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="py-3 px-4 text-gray-700">
                          {target.scope_unit_name || "المؤسسة كاملة"}
                        </td>
                        <td className="py-3 px-4">
                          {(() => {
                            const cats = Array.from(
                              new Set(
                                target.indicators
                                  .map((i) => i.category_name)
                                  .filter((n): n is string => !!n)
                              )
                            );
                            if (cats.length === 0) {
                              return (
                                <span className="text-xs text-gray-400">—</span>
                              );
                            }
                            return (
                              <div className="flex flex-wrap gap-1">
                                {cats.map((name) => (
                                  <span
                                    key={name}
                                    className="inline-block px-2 py-0.5 rounded-md text-xs bg-gray-100 text-gray-700"
                                  >
                                    {name}
                                  </span>
                                ))}
                              </div>
                            );
                          })()}
                        </td>
                        <td className="py-3 px-4 text-gray-700" dir="ltr">
                          {target.progress ? (
                            <>
                              <span className="font-bold text-gray-900">
                                {formatNumber(
                                  target.progress.cumulative_value
                                )}
                              </span>
                              <span className="text-gray-400 mx-1">/</span>
                              <span>
                                {formatNumber(target.progress.target_value)}
                              </span>
                            </>
                          ) : (
                            <span className="text-gray-400">—</span>
                          )}
                        </td>
                        <td className="py-3 px-4">
                          {target.progress ? (
                            <div className="space-y-1">
                              <div className="flex items-center justify-between text-xs">
                                <span
                                  className={`font-bold ${
                                    pct >= 100
                                      ? "text-green-600"
                                      : pct >= 75
                                      ? "text-blue-600"
                                      : pct >= 50
                                      ? "text-amber-600"
                                      : "text-red-600"
                                  }`}
                                  dir="ltr"
                                >
                                  {formatPercent(pct)}
                                </span>
                              </div>
                              <div className="w-full bg-gray-100 rounded-full h-2">
                                <div
                                  className={`h-2 rounded-full ${
                                    pct >= 100
                                      ? "bg-green-500"
                                      : pct >= 75
                                      ? "bg-blue-500"
                                      : pct >= 50
                                      ? "bg-amber-500"
                                      : "bg-red-500"
                                  }`}
                                  style={{ width: `${Math.min(pct, 100)}%` }}
                                />
                              </div>
                            </div>
                          ) : (
                            <span className="text-xs text-gray-400">—</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function StatCard({
  label,
  value,
  hint,
  bg,
  color,
}: {
  label: string;
  value: string;
  hint?: string;
  bg: string;
  color: string;
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

