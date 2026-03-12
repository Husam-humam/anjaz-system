"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { User } from "@/types/submissions";

interface AuthState {
  user: User | null;
  token: string | null;
  refreshToken: string | null;
  setAuth: (user: User, token: string, refreshToken: string) => void;
  setToken: (token: string) => void;
  clearAuth: () => void;
  logout: () => void;
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
      logout: () => set({ user: null, token: null, refreshToken: null }),
      isAuthenticated: () => !!get().token,
    }),
    {
      name: "anjaz-auth",
    }
  )
);
