"use client";

import { AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface ErrorStateProps {
  message?: string;
  onRetry?: () => void;
  className?: string;
}

export function ErrorState({
  message = "حدث خطأ أثناء تحميل البيانات. يرجى المحاولة مرة أخرى.",
  onRetry,
  className,
}: ErrorStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-4 rounded-lg border border-red-200 bg-red-50 p-8 text-center",
        className
      )}
    >
      <AlertCircle className="h-12 w-12 text-red-500" />
      <p className="text-sm font-medium text-red-700">{message}</p>
      {onRetry && (
        <Button variant="outline" onClick={onRetry} size="sm">
          إعادة المحاولة
        </Button>
      )}
    </div>
  );
}
