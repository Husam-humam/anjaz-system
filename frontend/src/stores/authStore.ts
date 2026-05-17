"use client";

import { useEffect, useState } from "react";
import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { User } from "@/types/submissions";

interface AuthState {
  user: User | null;
  token: string | null;
  refreshToken: string | null;
  setAuth: (user: User, token: string, refreshToken: string) => void;
  setToken: (token: string) => void;
  /** يمسح كل بيانات الـ auth محلياً (لا يستدعي API). */
  clearAuth: () => void;
  isAuthenticated: () => boolean;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      refreshToken: null,
      setAuth: (user, token, refreshToken) =>
        set({ user, token, refreshToken }),
      setToken: (token) => set({ token }),
      clearAuth: () => set({ user: null, token: null, refreshToken: null }),
      isAuthenticated: () => !!get().token,
    }),
    {
      name: "anjaz-auth",
    }
  )
);

/**
 * Hook للتأكد من اكتمال استرجاع الـ auth من localStorage.
 * ضروري عند التحميل الأولي لأن persist يحتاج tick بعد الـ mount.
 * يرجع true عندما يصبح الـ store جاهزاً للقراءة.
 *
 * ملاحظة: نبدأ بـ false دائماً (متوافق مع SSR) ونُحدّث في useEffect.
 */
export function useAuthHasHydrated(): boolean {
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    // الـ persist API متوفّر فقط في المتصفّح بعد التركيب
    const persistApi = useAuthStore.persist;
    if (!persistApi) {
      // في بيئات SSR أو قبل تثبيت الـ middleware
      setHydrated(true);
      return;
    }

    // لو انتهت الهيدرة بالفعل قبل هذا الـ effect
    if (persistApi.hasHydrated()) {
      setHydrated(true);
    }

    // استمع لإشعار اكتمال الهيدرة
    const unsub = persistApi.onFinishHydration(() => setHydrated(true));
    return () => {
      unsub();
    };
  }, []);

  return hydrated;
}
