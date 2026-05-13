"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/stores/authStore";
import { cn, formatNumber } from "@/lib/utils";
import type { UserRole } from "@/types/submissions";
import { getPendingFormTemplatesCount } from "@/lib/api/forms";
import { getPendingAdminReviewCount } from "@/lib/api/submissions";
import {
  LayoutDashboard,
  Building2,
  BarChart3,
  Users,
  Calendar,
  Target,
  CheckCircle,
  FileText,
  Bell,
  ClipboardList,
  ClipboardCheck,
  History,
  Menu,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

type BadgeKey = "pending_forms" | "pending_admin_review";

interface SidebarItem {
  label: string;
  href: string;
  icon: LucideIcon;
  /** مفتاح لعرض badge ديناميكي — يُحدَّد تحت */
  badgeKey?: BadgeKey;
}

const sidebarItemsByRole: Record<UserRole, SidebarItem[]> = {
  statistics_admin: [
    { label: "لوحة التحكم", href: "/dashboard", icon: LayoutDashboard },
    { label: "الهيكل التنظيمي", href: "/organization", icon: Building2 },
    { label: "بنك المؤشرات", href: "/indicators", icon: BarChart3 },
    { label: "المستخدمون", href: "/users", icon: Users },
    { label: "الأسابيع", href: "/periods", icon: Calendar },
    {
      label: "قوالب الاستمارات",
      href: "/forms",
      icon: ClipboardList,
      badgeKey: "pending_forms",
    },
    {
      label: "المنجزات",
      href: "/achievements",
      icon: ClipboardCheck,
      badgeKey: "pending_admin_review",
    },
    { label: "المستهدفات", href: "/targets", icon: Target },
    { label: "التقارير", href: "/reports", icon: FileText },
    { label: "الإشعارات", href: "/notifications", icon: Bell },
  ],
  planning_section: [
    { label: "لوحة التحكم", href: "/dashboard", icon: LayoutDashboard },
    {
      label: "قوالب الاستمارات",
      href: "/forms",
      icon: ClipboardList,
      badgeKey: "pending_forms",
    },
    { label: "المنجزات بانتظار الاعتماد", href: "/approvals", icon: CheckCircle },
    { label: "التقارير", href: "/reports", icon: FileText },
    { label: "الإشعارات", href: "/notifications", icon: Bell },
  ],
  section_manager: [
    { label: "لوحة التحكم", href: "/dashboard", icon: LayoutDashboard },
    { label: "تقديم المنجز", href: "/submission", icon: ClipboardList },
    { label: "سجل المنجزات", href: "/history", icon: History },
    { label: "الإشعارات", href: "/notifications", icon: Bell },
  ],
};

export function Sidebar() {
  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const pathname = usePathname();
  const user = useAuthStore((s) => s.user);

  const role = user?.role;
  const items = role ? sidebarItemsByRole[role] : [];

  // عدّاد القوالب المعلّقة — يُعرض في الـ sidebar
  const { data: pendingFormsCount = 0 } = useQuery({
    queryKey: ["sidebar-pending-forms-count"],
    queryFn: getPendingFormTemplatesCount,
    enabled: role === "statistics_admin" || role === "planning_section",
    // يُحدَّث كل 30 ثانية للمزامنة الخفيفة
    refetchInterval: 30_000,
    staleTime: 10_000,
  });

  // عدّاد المنجزات بانتظار مراجعة الإحصاء — يُعرض للأدمن فقط
  const { data: pendingAdminReviewCount = 0 } = useQuery({
    queryKey: ["sidebar-pending-admin-review-count"],
    queryFn: getPendingAdminReviewCount,
    enabled: role === "statistics_admin",
    refetchInterval: 30_000,
    staleTime: 10_000,
  });

  const getBadgeCount = (badgeKey?: BadgeKey): number => {
    if (badgeKey === "pending_forms") return pendingFormsCount;
    if (badgeKey === "pending_admin_review") return pendingAdminReviewCount;
    return 0;
  };

  const getBadgeTitle = (badgeKey: BadgeKey | undefined, count: number): string => {
    if (badgeKey === "pending_forms") {
      return `${count} قالب بانتظار الاعتماد`;
    }
    if (badgeKey === "pending_admin_review") {
      return `${count} منجز بانتظار مراجعة الإحصاء`;
    }
    return "";
  };

  const isActive = (href: string) => {
    if (href === "/dashboard") {
      return pathname === "/dashboard";
    }
    return pathname.startsWith(href);
  };

  const sidebarContent = (
    <nav className="flex flex-col gap-1 p-4">
      {/* شعار النظام */}
      <div className="mb-6 px-3 py-4 text-center">
        <h1 className="text-xl font-bold text-white">نظام أنجز</h1>
        <p className="mt-1 text-xs text-primary-200">ج33 - قسم الاحصاء</p>
      </div>

      {/* عناصر القائمة */}
      {items.map((item) => {
        const Icon = item.icon;
        const active = isActive(item.href);
        const badgeCount = getBadgeCount(item.badgeKey);
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={() => setIsMobileOpen(false)}
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
              active
                ? "bg-primary-600 text-white shadow-sm"
                : "text-primary-100 hover:bg-primary-800 hover:text-white"
            )}
          >
            <Icon className="h-5 w-5 shrink-0" />
            <span className="flex-1">{item.label}</span>
            {badgeCount > 0 && (
              <span
                className="inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full bg-amber-500 text-white text-xs font-bold"
                title={getBadgeTitle(item.badgeKey, badgeCount)}
              >
                {formatNumber(badgeCount)}
              </span>
            )}
          </Link>
        );
      })}
    </nav>
  );

  return (
    <>
      {/* زر فتح القائمة الجانبية في الموبايل */}
      <button
        type="button"
        onClick={() => setIsMobileOpen(true)}
        className="fixed top-4 right-4 z-50 rounded-lg bg-primary-700 p-2 text-white shadow-lg md:hidden"
        aria-label="فتح القائمة"
      >
        <Menu className="h-5 w-5" />
      </button>

      {/* خلفية معتمة عند فتح القائمة في الموبايل */}
      {isMobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
          onClick={() => setIsMobileOpen(false)}
        />
      )}

      {/* القائمة الجانبية في الموبايل */}
      <aside
        className={cn(
          "fixed inset-y-0 right-0 z-50 w-64 transform bg-primary-900 transition-transform duration-300 md:hidden",
          isMobileOpen ? "translate-x-0" : "translate-x-full"
        )}
      >
        <div className="flex justify-start p-4">
          <button
            type="button"
            onClick={() => setIsMobileOpen(false)}
            className="rounded-lg p-1 text-primary-200 hover:text-white"
            aria-label="إغلاق القائمة"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        {sidebarContent}
      </aside>

      {/* القائمة الجانبية في الشاشات الكبيرة */}
      <aside className="hidden w-64 shrink-0 bg-primary-900 md:block">
        <div className="sticky top-0 h-screen overflow-y-auto">
          {sidebarContent}
        </div>
      </aside>
    </>
  );
}
