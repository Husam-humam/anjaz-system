"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getNotifications,
  markAsRead,
  markAllAsRead,
} from "@/lib/api/notifications";
import type { Notification } from "@/types/submissions";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { ErrorState } from "@/components/shared/ErrorState";
import { EmptyState } from "@/components/shared/EmptyState";
import { Button } from "@/components/ui/button";
import { formatDateTime } from "@/lib/utils";
import { Bell, CheckCheck, Check } from "lucide-react";

const NOTIFICATION_TYPE_ICONS: Record<string, string> = {
  submission_submitted: "bg-blue-100 text-blue-600",
  submission_approved: "bg-green-100 text-green-600",
  submission_rejected: "bg-red-100 text-red-600",
  template_submitted: "bg-purple-100 text-purple-600",
  template_approved: "bg-green-100 text-green-600",
  template_rejected: "bg-red-100 text-red-600",
  week_opened: "bg-amber-100 text-amber-600",
  week_closed: "bg-gray-100 text-gray-600",
  deadline_reminder: "bg-orange-100 text-orange-600",
  extension_granted: "bg-teal-100 text-teal-600",
};

export default function NotificationsPage() {
  const queryClient = useQueryClient();

  const {
    data: notificationsData,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["notifications"],
    queryFn: () => getNotifications(),
  });

  const readMutation = useMutation({
    mutationFn: (id: number) => markAsRead(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
      queryClient.invalidateQueries({ queryKey: ["unread-count"] });
    },
  });

  const readAllMutation = useMutation({
    mutationFn: () => markAllAsRead(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
      queryClient.invalidateQueries({ queryKey: ["unread-count"] });
    },
  });

  const notifications = notificationsData?.results || [];
  const unreadCount = notifications.filter(
    (n: Notification) => !n.is_read
  ).length;

  if (isLoading) {
    return <LoadingSpinner size="lg" />;
  }

  if (isError) {
    return <ErrorState onRetry={() => refetch()} />;
  }

  return (
    <div className="space-y-6">
      {/* العنوان */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">الإشعارات</h1>
          <p className="text-gray-500 mt-1">
            {unreadCount > 0
              ? `لديك ${unreadCount} إشعار غير مقروء`
              : "جميع الإشعارات مقروءة"}
          </p>
        </div>
        {unreadCount > 0 && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => readAllMutation.mutate()}
            disabled={readAllMutation.isPending}
          >
            <CheckCheck className="w-4 h-4 ml-2" />
            {readAllMutation.isPending
              ? "جارٍ التعليم..."
              : "تعليم الكل كمقروء"}
          </Button>
        )}
      </div>

      {/* قائمة الإشعارات */}
      <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
        {notifications.length === 0 ? (
          <EmptyState message="لا توجد إشعارات." />
        ) : (
          <div className="divide-y divide-gray-100">
            {notifications.map((notif: Notification) => {
              const colorClasses =
                NOTIFICATION_TYPE_ICONS[notif.notification_type] ||
                "bg-gray-100 text-gray-600";

              return (
                <div
                  key={notif.id}
                  className={`flex items-start gap-4 p-4 transition ${
                    !notif.is_read
                      ? "bg-blue-50/40 hover:bg-blue-50/60"
                      : "hover:bg-gray-50"
                  }`}
                >
                  {/* أيقونة */}
                  <div
                    className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${colorClasses}`}
                  >
                    <Bell className="w-5 h-5" />
                  </div>

                  {/* المحتوى */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <h3
                          className={`text-sm ${
                            !notif.is_read
                              ? "font-bold text-gray-900"
                              : "font-medium text-gray-700"
                          }`}
                        >
                          {notif.title}
                        </h3>
                        <p className="text-sm text-gray-600 mt-0.5 leading-relaxed">
                          {notif.message}
                        </p>
                      </div>

                      {/* مؤشر غير مقروء */}
                      {!notif.is_read && (
                        <div className="w-2.5 h-2.5 rounded-full bg-blue-500 flex-shrink-0 mt-1.5" />
                      )}
                    </div>

                    <div className="flex items-center justify-between mt-2">
                      <span className="text-xs text-gray-400">
                        {formatDateTime(notif.created_at)}
                      </span>

                      {!notif.is_read && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-xs h-7"
                          onClick={() => readMutation.mutate(notif.id)}
                          disabled={readMutation.isPending}
                        >
                          <Check className="w-3 h-3 ml-1" />
                          تعليم كمقروء
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
