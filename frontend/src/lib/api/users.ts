import apiClient from "./client";
import type { User } from "@/types/submissions";
import type { ApiResponse } from "@/types/api";

// --- المستخدمون ---

export async function getUsers(params?: Record<string, string>): Promise<ApiResponse<User>> {
  const { data } = await apiClient.get<ApiResponse<User>>("/auth/users/", { params });
  return data;
}

export async function getUser(id: number): Promise<User> {
  const { data } = await apiClient.get<User>(`/auth/users/${id}/`);
  return data;
}

export async function createUser(userData: {
  username: string;
  full_name: string;
  password: string;
  role: string;
  unit?: number;
}): Promise<User> {
  const { data } = await apiClient.post<User>("/auth/users/", userData);
  return data;
}

export async function updateUser(id: number, userData: Partial<User & { password?: string }>): Promise<User> {
  const { data } = await apiClient.patch<User>(`/auth/users/${id}/`, userData);
  return data;
}

export async function changePassword(data: {
  old_password: string;
  new_password: string;
}): Promise<void> {
  await apiClient.post("/auth/change-password/", data);
}
