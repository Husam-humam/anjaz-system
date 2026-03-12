import apiClient from "./client";
import type { User } from "@/types/submissions";
import type { ApiResponse } from "@/types/api";

// --- المستخدمون ---

export async function getUsers(params?: Record<string, string>): Promise<ApiResponse<User>> {
  const { data } = await apiClient.get<ApiResponse<User>>("/users/", { params });
  return data;
}

export async function getUser(id: number): Promise<User> {
  const { data } = await apiClient.get<User>(`/users/${id}/`);
  return data;
}

export async function createUser(userData: {
  username: string;
  full_name: string;
  password: string;
  role: string;
  unit?: number;
}): Promise<User> {
  const { data } = await apiClient.post<User>("/users/", userData);
  return data;
}

export async function updateUser(id: number, userData: Partial<User & { password?: string }>): Promise<User> {
  const { data } = await apiClient.patch<User>(`/users/${id}/`, userData);
  return data;
}

export async function changePassword(data: {
  old_password: string;
  new_password: string;
}): Promise<void> {
  await apiClient.post("/auth/change-password/", data);
}

export async function resetPassword(userId: number, newPassword: string): Promise<void> {
  await apiClient.post(`/users/${userId}/reset_password/`, { new_password: newPassword });
}
