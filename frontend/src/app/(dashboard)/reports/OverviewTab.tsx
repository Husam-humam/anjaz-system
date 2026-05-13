"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getSummary, getComplianceReport } from "@/lib/api/reports";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { EmptyState } from "@/components/shared/EmptyState";
import {
  TrendingUp,
  CheckCircle2,
  Clock,
  Target as TargetIcon,
} from "lucide-react";
import { formatNumber, formatPercent } from "@/lib/utils";
import type { ReportFilterValues } from "./ReportFilters";
import { getEffectiveUnitId } from "./ReportFilters";

const STATUS_COLORS: Record<string, string> = {
  approved: "#10b981",
  submitted: "#3b82f6",
  draft: "#f59e0b",
  late: "#ef4444",
  extended: "#8b5cf6",
  returned: "#ec4899",
};

const STATUS_LABELS: Record<string, string> = {
  approved: "معتمد",
  submitted: "مُرسل",
  draft: "مسودة",
  late: "متأخر",
  extended: "مُمدَّد",
  returned: "مُرجَع",
};

interface Props {
  filters: ReportFilterValues;
}

export function OverviewTab({ filters }: Props) {
  const unitId = getEffectiveUnitId(filters);

  const summaryParams: Record<string, string> = {
    year: filters.year.toString(),
  };
  if (unitId) summaryParams.unit_id = unitId;

  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ["overview-summary", summaryParams],
    queryFn: () => getSummary(summaryParams),
  });

  const complianceParams: Record<string, string> = {
    year: filters.year.toString(),
  };
  if (unitId) complianceParams.unit_id = unitId;

  const { data: compliance, isLoading: complianceLoading } = useQuery({
    queryKey: ["overview-compliance", complianceParams],
    queryFn: () => getComplianceReport(complianceParams),
  });

  const statusData = useMemo(() => {
    if (!summary?.status_breakdown) return [];
    return Object.entries(summary.status_breakdown)
      .filter(([, count]) => count > 0)
      .map(([status, count]) => ({
        name: STATUS_LABELS[status] || status,
        value: count,
        color: STATUS_COLORS[status] || "#9ca3af",
      }));
  }, [summary]);

  // ترتيب تنازلي حسب نسبة الالتزام — أول 10
  const topCompliance = useMemo(() => {
    if (!compliance) return [];
    return [...compliance]
      .sort((a, b) => b.compliance_rate - a.compliance_rate)
      .slice(0, 10)
      .map((row) => ({
        name: row.qism_name,
        rate: row.compliance_rate,
      }));
  }, [compliance]);

  if (summaryLoading || complianceLoading) {
    return <LoadingSpinner size="lg" />;
  }

  if (!summary) {
    return <EmptyState message="لا توجد بيانات للعرض." />;
  }

  return (
    <div className="space-y-6">
      {/* ── بطاقات KPI ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          icon={<CheckCircle2 className="w-5 h-5 text-green-600" />}
          label="المنجزات المعتمدة"
          value={formatNumber(summary.approved_submissions)}
          subtext={`من ${formatNumber(summary.total_submissions)} منجز`}
          bg="bg-green-50"
        />
        <KPICard
          icon={<TrendingUp className="w-5 h-5 text-blue-600" />}
          label="نسبة الالتزام"
          value={formatPercent(summary.compliance_rate)}
          bg="bg-blue-50"
        />
        <KPICard
          icon={<Clock className="w-5 h-5 text-amber-600" />}
          label="منجزات نوعية معلّقة"
          value={formatNumber(summary.pending_qualitative)}
          bg="bg-amber-50"
        />
        <KPICard
          icon={<TargetIcon className="w-5 h-5 text-purple-600" />}
          label="عدد المستهدفات النشطة"
          value={formatNumber(summary.target_progress?.length || 0)}
          bg="bg-purple-50"
        />
      </div>

      {/* ── الرسوم البيانية ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* شريطي أفقي: الأقسام الأعلى التزاماً (بدون تداخل — أسماء خارجية) */}
        <ChartCard
          title="الأقسام الأعلى التزاماً بالتسليم"
          subtitle="أعلى 10 أقسام حسب نسبة الالتزام"
        >
          {topCompliance.length > 0 ? (
            <ResponsiveContainer width="100%" height={340}>
              <BarChart
                data={topCompliance}
                layout="vertical"
                margin={{ top: 5, right: 50, left: 10, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                <XAxis
                  type="number"
                  domain={[0, 100]}
                  tick={{ fontSize: 11 }}
                  tickFormatter={(v) => `${v}%`}
                />
                <YAxis
                  dataKey="name"
                  type="category"
                  tick={{ fontSize: 11 }}
                  width={160}
                  interval={0}
                />
                <Tooltip
                  formatter={(v: number) => [`${v}%`, "نسبة الالتزام"]}
                  contentStyle={{ direction: "rtl", fontSize: 12 }}
                />
                <Bar dataKey="rate" radius={[0, 4, 4, 0]}>
                  {topCompliance.map((entry, idx) => (
                    <Cell
                      key={idx}
                      fill={
                        entry.rate >= 90
                          ? "#10b981"
                          : entry.rate >= 70
                          ? "#3b82f6"
                          : entry.rate >= 50
                          ? "#f59e0b"
                          : "#ef4444"
                      }
                    />
                  ))}
                  <LabelList
                    dataKey="rate"
                    position="right"
                    formatter={(value: React.ReactNode) => `${value}%`}
                    style={{ fontSize: 11, fill: "#374151" }}
                  />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState message="لا توجد بيانات التزام." />
          )}
        </ChartCard>

        {/* دائري: توزيع حالات المنجزات — بدون labels داخلية */}
        <ChartCard
          title="توزيع حالات المنجزات"
          subtitle={`إجمالي ${formatNumber(summary.total_submissions)} منجز`}
        >
          {statusData.length > 0 ? (
            <ResponsiveContainer width="100%" height={340}>
              <PieChart>
                <Pie
                  data={statusData}
                  cx="50%"
                  cy="45%"
                  innerRadius={65}
                  outerRadius={100}
                  paddingAngle={3}
                  dataKey="value"
                  nameKey="name"
                >
                  {statusData.map((entry, idx) => (
                    <Cell key={idx} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(v: number) => [formatNumber(v), "عدد المنجزات"]}
                  contentStyle={{ direction: "rtl", fontSize: 12 }}
                />
                <Legend
                  verticalAlign="bottom"
                  height={36}
                  iconType="circle"
                  formatter={(value, entry) => {
                    const count = (entry?.payload as { value?: number })?.value;
                    return `${value}: ${formatNumber(count)}`;
                  }}
                  wrapperStyle={{ fontSize: 12 }}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState message="لا توجد بيانات حالات." />
          )}
        </ChartCard>
      </div>
    </div>
  );
}

// ── المكوّنات المساعدة ──

function KPICard({
  icon,
  label,
  value,
  subtext,
  bg,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  subtext?: string;
  bg: string;
}) {
  return (
    <div className={`rounded-xl p-4 ${bg} border border-white shadow-sm`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm text-gray-600 font-medium">{label}</span>
        {icon}
      </div>
      <div className="text-2xl font-bold text-gray-900" dir="ltr">
        {value}
      </div>
      {subtext && (
        <div className="text-xs text-gray-500 mt-1" dir="rtl">
          {subtext}
        </div>
      )}
    </div>
  );
}

function ChartCard({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-white rounded-xl shadow-sm border p-4">
      <div className="mb-3">
        <h3 className="font-semibold text-gray-900">{title}</h3>
        {subtitle && <p className="text-xs text-gray-500 mt-0.5">{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}
