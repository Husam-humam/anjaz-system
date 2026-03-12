"use client";

import { useAuthStore } from "@/stores/authStore";
import { useRouter, usePathname } from "next/navigation";
import { useEffect } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";

// المسارات المتاحة فقط لمدير قسم الإحصاء
const ADMIN_ONLY_ROUTES = ["/users", "/periods", "/organization"];
// المسارات المتاحة لمدير الإحصاء وقسم التخطيط
const ADMIN_PLANNING_ROUTES = ["/approvals", "/targets", "/indicators"];

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, token } = useAuthStore();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
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
        if (
          ADMIN_PLANNING_ROUTES.some((r) => pathname.startsWith(r)) &&
          pathname !== "/approvals"
        ) {
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
    }
  }, [token, user, pathname, router]);

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
