"use client";

import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/stores/authStore";
import { getSummary } from "@/lib/api/reports";
import { STATUS_LABELS } from "@/lib/constants";

export default function DashboardPage() {
  const user = useAuthStore((s) => s.user);
  const currentYear = new Date().getFullYear();

  const { data: summary, isLoading } = useQuery({
    queryKey: ["report-summary", currentYear],
    queryFn: () => getSummary({ year: currentYear.toString() }),
  });

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="h-8 bg-gray-200 rounded w-48 animate-pulse" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="bg-white rounded-xl p-6 shadow-sm animate-pulse">
              <div className="h-4 bg-gray-200 rounded w-24 mb-3" />
              <div className="h-8 bg-gray-200 rounded w-16" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* العنوان */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">لوحة التحكم</h1>
          <p className="text-gray-500 mt-1">
            مرحباً {user?.full_name}
          </p>
        </div>
        {summary?.period && (
          <div className="bg-white rounded-lg px-4 py-2 shadow-sm border">
            <span className="text-sm text-gray-500">الأسبوع الحالي: </span>
            <span className="font-semibold">
              الأسبوع {summary.period.week_number} / {summary.period.year}
            </span>
            <span
              className={`mr-2 inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                summary.period.status === "open"
                  ? "bg-green-100 text-green-700"
                  : "bg-gray-100 text-gray-700"
              }`}
            >
              {STATUS_LABELS[summary.period.status] || summary.period.status}
            </span>
          </div>
        )}
      </div>

      {/* بطاقات الإحصائيات */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="إجمالي المنجزات"
          value={summary?.total_submissions ?? 0}
          icon="📊"
          color="blue"
        />
        <StatCard
          title="المنجزات المعتمدة"
          value={summary?.approved_submissions ?? 0}
          icon="✅"
          color="green"
        />
        <StatCard
          title="نسبة الامتثال"
          value={`${summary?.compliance_rate ?? 0}%`}
          icon="📈"
          color="purple"
        />
        <StatCard
          title="منجزات نوعية معلقة"
          value={summary?.pending_qualitative ?? 0}
          icon="⏳"
          color="amber"
        />
      </div>

      {/* تقدم المستهدفات */}
      {summary?.target_progress && summary.target_progress.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm p-6">
          <h2 className="text-lg font-semibold mb-4">المستهدفات السنوية</h2>
          <div className="space-y-4">
            {summary.target_progress.map(
              (
                target: {
                  indicator_name: string;
                  qism_name: string;
                  cumulative_value: number;
                  target_value: number;
                  progress_percentage: number;
                },
                idx: number
              ) => (
                <div key={idx}>
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-sm font-medium text-gray-700">
                      {target.indicator_name}
                      {user?.role !== "section_manager" && (
                        <span className="text-gray-400 text-xs mr-2">
                          ({target.qism_name})
                        </span>
                      )}
                    </span>
                    <span className="text-sm text-gray-500">
                      {target.cumulative_value.toLocaleString("ar-IQ")} /{" "}
                      {target.target_value.toLocaleString("ar-IQ")} (
                      {target.progress_percentage}%)
                    </span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2.5">
                    <div
                      className={`h-2.5 rounded-full transition-all ${
                        target.progress_percentage >= 90
                          ? "bg-green-500"
                          : target.progress_percentage >= 50
                          ? "bg-blue-500"
                          : "bg-amber-500"
                      }`}
                      style={{
                        width: `${Math.min(target.progress_percentage, 100)}%`,
                      }}
                    />
                  </div>
                </div>
              )
            )}
          </div>
        </div>
      )}

      {/* توزيع الحالات */}
      {summary?.status_breakdown && (
        <div className="bg-white rounded-xl shadow-sm p-6">
          <h2 className="text-lg font-semibold mb-4">توزيع حالات المنجزات</h2>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {Object.entries(summary.status_breakdown).map(
              ([statusKey, count]) => (
                <div
                  key={statusKey}
                  className="text-center p-3 bg-gray-50 rounded-lg"
                >
                  <div className="text-2xl font-bold text-gray-900">
                    {String(count)}
                  </div>
                  <div className="text-sm text-gray-500 mt-1">
                    {STATUS_LABELS[statusKey] || statusKey}
                  </div>
                </div>
              )
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({
  title,
  value,
  icon,
  color,
}: {
  title: string;
  value: number | string;
  icon: string;
  color: string;
}) {
  const colorMap: Record<string, string> = {
    blue: "bg-blue-50 border-blue-200",
    green: "bg-green-50 border-green-200",
    purple: "bg-purple-50 border-purple-200",
    amber: "bg-amber-50 border-amber-200",
  };

  return (
    <div
      className={`rounded-xl p-6 border ${colorMap[color] || "bg-white border-gray-200"}`}
    >
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-600">{title}</p>
          <p className="text-2xl font-bold mt-1">{value}</p>
        </div>
        <span className="text-3xl">{icon}</span>
      </div>
    </div>
  );
}
