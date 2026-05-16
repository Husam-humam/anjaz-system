"use client";

import { useAuthStore } from "@/stores/authStore";
import type { UserRole } from "@/types/submissions";

export function usePermissions() {
  const user = useAuthStore((s) => s.user);

  const hasRole = (role: UserRole) => user?.role === role;
  const isAdmin = () => user?.role === "statistics_admin";
  const isPlanning = () => user?.role === "planning_section";
  const isManager = () => user?.role === "section_manager";
  const isViewer = () => user?.role === "viewer";
  /**
   * هل يستطيع المستخدم القيام بإجراءات الكتابة (إرسال/اعتماد/تعديل)؟
   * الـ viewer = قراءة فقط؛ كل الباقي يستطيع.
   */
  const canAct = () => user != null && user.role !== "viewer";

  return { user, hasRole, isAdmin, isPlanning, isManager, isViewer, canAct };
}
