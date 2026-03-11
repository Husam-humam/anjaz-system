import axios from "axios";
import { useAuthStore } from "@/stores/authStore";

const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api",
  headers: {
    "Content-Type": "application/json",
  },
});

apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      const refreshToken = useAuthStore.getState().refreshToken;

      if (refreshToken) {
        try {
          const { data } = await axios.post(
            `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api"}/auth/token/refresh/`,
            { refresh: refreshToken }
          );

          useAuthStore.getState().setAuth(
            useAuthStore.getState().user!,
            data.access,
            refreshToken
          );

          originalRequest.headers.Authorization = `Bearer ${data.access}`;
          return apiClient(originalRequest);
        } catch {
          useAuthStore.getState().logout();
          if (typeof window !== "undefined") {
            window.location.href = "/login";
          }
        }
      } else {
        useAuthStore.getState().logout();
        if (typeof window !== "undefined") {
          window.location.href = "/login";
        }
      }
    }

    return Promise.reject(error);
  }
);

export default apiClient;
