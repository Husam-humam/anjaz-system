"use client";

import { useRouter } from "next/navigation";
import { useNotificationStore } from "@/stores/notificationStore";
import { Bell } from "lucide-react";

export function NotificationBell() {
  const router = useRouter();
  const unreadCount = useNotificationStore((s) => s.unreadCount);

  return (
    <button
      type="button"
      onClick={() => router.push("/notifications")}
      className="relative rounded-lg p-2 text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700"
      aria-label="الإشعارات"
    >
      <Bell className="h-5 w-5" />
      {unreadCount > 0 && (
        <span className="absolute -top-0.5 -left-0.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
          {unreadCount > 99 ? "99+" : unreadCount}
        </span>
      )}
    </button>
  );
}
