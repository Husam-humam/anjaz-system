"use client";

import { useAuthStore } from "@/stores/authStore";
import { useRouter } from "next/navigation";
import { useCallback } from "react";
import { login as loginApi, logout as logoutApi } from "@/lib/api/auth";

export function useAuth() {
  const { user, token, refreshToken, setAuth, logout: clearAuth } =
    useAuthStore();
  const router = useRouter();

  const login = useCallback(
    async (username: string, password: string) => {
      const data = await loginApi(username, password);
      setAuth(data.user, data.access, data.refresh);
      router.push("/dashboard");
    },
    [setAuth, router]
  );

  const logout = useCallback(async () => {
    if (refreshToken) {
      try {
        await logoutApi(refreshToken);
      } catch {
        // تجاهل أخطاء تسجيل الخروج من الخادم
      }
    }
    clearAuth();
    router.push("/login");
  }, [refreshToken, clearAuth, router]);

  return { user, token, isAuthenticated: !!token, login, logout };
}
