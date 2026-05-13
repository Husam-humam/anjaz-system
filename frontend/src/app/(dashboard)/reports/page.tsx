"use client";

import { useState } from "react";
import {
  BarChart3,
  CheckCircle2,
  FileText,
  LayoutDashboard,
  Target as TargetIcon,
} from "lucide-react";
import { ReportFilters, type ReportFilterValues } from "./ReportFilters";
import { OverviewTab } from "./OverviewTab";
import { PeriodicTab } from "./PeriodicTab";
import { ComplianceTab } from "./ComplianceTab";
import { QualitativeTab } from "./QualitativeTab";
import { TargetsTab } from "./TargetsTab";

type TabKey = "overview" | "periodic" | "compliance" | "qualitative" | "targets";

const TABS: Array<{
  key: TabKey;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
}> = [
  {
    key: "overview",
    label: "نظرة عامة",
    icon: LayoutDashboard,
    color: "text-blue-600",
  },
  {
    key: "periodic",
    label: "التقرير الدوري",
    icon: BarChart3,
    color: "text-emerald-600",
  },
  {
    key: "compliance",
    label: "الالتزام",
    icon: CheckCircle2,
    color: "text-green-600",
  },
  {
    key: "qualitative",
    label: "المنجزات النوعية",
    icon: FileText,
    color: "text-amber-600",
  },
  {
    key: "targets",
    label: "تقرير المستهدفات",
    icon: TargetIcon,
    color: "text-purple-600",
  },
];

const currentYear = new Date().getFullYear();

export default function ReportsPage() {
  const [activeTab, setActiveTab] = useState<TabKey>("overview");
  // افتراضي: الفترة الأخيرة (آخر 30 يوماً)
  const defaultToDate = new Date().toISOString().slice(0, 10);
  const defaultFromDate = (() => {
    const d = new Date();
    d.setDate(d.getDate() - 30);
    return d.toISOString().slice(0, 10);
  })();

  const [filters, setFilters] = useState<ReportFilterValues>({
    year: currentYear,
    dairaId: "",
    mudiriyaId: "",
    qismId: "",
    categoryId: "",
    fromDate: defaultFromDate,
    toDate: defaultToDate,
  });

  // ما يُعرض من الفلاتر يعتمد على التبويب
  const filterProps = (() => {
    if (activeTab === "periodic") {
      return {
        showDateRange: true,
        showCategory: true,
      };
    }
    if (activeTab === "targets") {
      return { showCategory: true };
    }
    return { showCategory: false };
  })();

  return (
    <div className="space-y-6">
      {/* العنوان */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">التقارير والتحليلات</h1>
        <p className="text-gray-500 mt-1">
          نظرة شاملة على الأداء، الالتزام، والمستهدفات
        </p>
      </div>

      {/* شريط التبويبات */}
      <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
        <div className="flex overflow-x-auto">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`flex items-center gap-2 px-6 py-4 border-b-2 font-medium text-sm transition whitespace-nowrap ${
                  isActive
                    ? "border-primary-600 text-primary-700 bg-primary-50/50"
                    : "border-transparent text-gray-600 hover:text-gray-900 hover:bg-gray-50"
                }`}
              >
                <Icon className={`w-5 h-5 ${isActive ? tab.color : ""}`} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* الفلاتر */}
      <ReportFilters
        values={filters}
        onChange={setFilters}
        showDateRange={filterProps.showDateRange || false}
        showCategory={filterProps.showCategory || false}
      />

      {/* محتوى التبويب النشط */}
      <div>
        {activeTab === "overview" && <OverviewTab filters={filters} />}
        {activeTab === "periodic" && <PeriodicTab filters={filters} />}
        {activeTab === "compliance" && <ComplianceTab filters={filters} />}
        {activeTab === "qualitative" && <QualitativeTab filters={filters} />}
        {activeTab === "targets" && <TargetsTab filters={filters} />}
      </div>
    </div>
  );
}
