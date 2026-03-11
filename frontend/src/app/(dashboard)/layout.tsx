"use client";

import { useAuthStore } from "@/stores/authStore";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, token } = useAuthStore();
  const router = useRouter();

  useEffect(() => {
    if (!token) {
      router.push("/login");
    }
  }, [token, router]);

  if (!token || !user) return null;

  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar />
      <div className="flex flex-1 flex-col">
        <Header />
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}
