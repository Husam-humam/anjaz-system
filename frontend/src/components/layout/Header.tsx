"use client";

import { useAuthStore } from "@/stores/authStore";
import { useAuth } from "@/hooks/useAuth";
import { ROLE_LABELS } from "@/lib/constants";
import { NotificationBell } from "./NotificationBell";
import { LogOut } from "lucide-react";

export function Header() {
  const user = useAuthStore((s) => s.user);
  const { logout } = useAuth();

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-gray-200 bg-white px-6 shadow-sm">
      {/* عنوان النظام */}
      <div className="flex items-center gap-3">
        <h2 className="text-lg font-bold text-primary-700">نظام أنجز</h2>
      </div>

      {/* معلومات المستخدم والإجراءات */}
      <div className="flex items-center gap-4">
        {/* جرس الإشعارات */}
        <NotificationBell />

        {/* اسم المستخدم والدور */}
        {user && (
          <div className="hidden text-left sm:block">
            <p className="text-sm font-semibold text-gray-800">
              {user.full_name}
            </p>
            <p className="text-xs text-gray-500">
              {ROLE_LABELS[user.role] || user.role}
            </p>
          </div>
        )}

        {/* زر تسجيل الخروج */}
        <button
          type="button"
          onClick={logout}
          className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-gray-500 transition-colors hover:bg-red-50 hover:text-red-600"
          aria-label="تسجيل الخروج"
        >
          <LogOut className="h-4 w-4" />
          <span className="hidden sm:inline">خروج</span>
        </button>
      </div>
    </header>
  );
}
