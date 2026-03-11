import apiClient from "./client";
import type { LoginResponse, User } from "@/types/submissions";

export async function login(username: string, password: string): Promise<LoginResponse> {
  const { data } = await apiClient.post<LoginResponse>("/auth/login/", { username, password });
  return data;
}

export async function logout(refreshToken: string): Promise<void> {
  await apiClient.post("/auth/logout/", { refresh: refreshToken });
}

export async function getMe(): Promise<User> {
  const { data } = await apiClient.get<User>("/auth/me/");
  return data;
}

export async function refreshToken(refresh: string): Promise<{ access: string }> {
  const { data } = await apiClient.post("/auth/token/refresh/", { refresh });
  return data;
}
