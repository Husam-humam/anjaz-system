"use client";

import { useAuthHasHydrated, useAuthStore } from "@/stores/authStore";
import { useRouter, usePathname } from "next/navigation";
import { useEffect } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";

// المسارات المتاحة فقط لمدير قسم الإحصاء
const ADMIN_ONLY_ROUTES = [
  "/users",
  "/periods",
  "/organization",
  "/achievements",
];
// المسارات المتاحة لمدير الإحصاء وقسم التخطيط (محظورة على section_manager)
const ADMIN_PLANNING_ROUTES = [
  "/approvals",
  "/targets",
  "/indicators",
  "/reports",
  "/forms",
];
// المسارات الوحيدة المسموحة لدور المُطّلِع (قراءة فقط — لا إجراءات).
const VIEWER_ALLOWED_ROUTES = [
  "/dashboard",
  "/reports",
  "/notifications",
  "/profile",
];

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const hasHydrated = useAuthHasHydrated();
  const user = useAuthStore((s) => s.user);
  const token = useAuthStore((s) => s.token);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    // لا نتخذ أي قرار قبل اكتمال استرجاع الـ auth من localStorage
    if (!hasHydrated) return;

    if (!token) {
      router.replace("/login");
      return;
    }

    if (user) {
      const role = user.role;

      // مدير القسم: لا يمكنه الوصول إلى صفحات الإدارة أو التخطيط
      if (role === "section_manager") {
        if (ADMIN_ONLY_ROUTES.some((r) => pathname.startsWith(r))) {
          router.replace("/dashboard");
          return;
        }
        if (ADMIN_PLANNING_ROUTES.some((r) => pathname.startsWith(r))) {
          router.replace("/dashboard");
          return;
        }
      }

      // قسم التخطيط: لا يمكنه الوصول إلى صفحات الإدارة فقط
      if (role === "planning_section") {
        if (ADMIN_ONLY_ROUTES.some((r) => pathname.startsWith(r))) {
          router.replace("/dashboard");
          return;
        }
      }

      // المُطّلِع: قراءة فقط — يُسمح بقائمة صريحة، أي شيء آخر يُعاد توجيهه.
      if (role === "viewer") {
        const allowed = VIEWER_ALLOWED_ROUTES.some((r) =>
          pathname.startsWith(r),
        );
        if (!allowed) {
          router.replace("/dashboard");
          return;
        }
      }
    }
  }, [hasHydrated, token, user, pathname, router]);

  // شاشة تحميل أثناء استرجاع الـ auth (تجنّب وميض "تسجيل دخول")
  if (!hasHydrated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (!token) return null;

  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar />
      <div className="flex flex-1 flex-col">
        <Header />
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}
