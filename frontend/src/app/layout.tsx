import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "نظام أنجز - حصر المنجزات",
  description: "نظام حصر المنجزات الإداري المؤسسي",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ar" dir="rtl">
      <body className="font-arabic antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
