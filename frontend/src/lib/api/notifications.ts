import apiClient from "./client";
import type { Notification } from "@/types/submissions";
import type { ApiResponse } from "@/types/api";

export async function getNotifications(params?: Record<string, string>): Promise<ApiResponse<Notification>> {
  const { data } = await apiClient.get<ApiResponse<Notification>>("/notifications/", { params });
  return data;
}

export async function markAsRead(id: number): Promise<void> {
  await apiClient.post(`/notifications/${id}/read/`);
}

export async function markAllAsRead(): Promise<void> {
  await apiClient.post("/notifications/read_all/");
}

export async function getUnreadCount(): Promise<{ count: number }> {
  const { data } = await apiClient.get<{ count: number }>("/notifications/unread_count/");
  return data;
}
