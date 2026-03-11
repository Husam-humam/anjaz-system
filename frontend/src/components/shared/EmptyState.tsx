import { Inbox } from "lucide-react";
import { cn } from "@/lib/utils";

interface EmptyStateProps {
  message?: string;
  className?: string;
}

export function EmptyState({
  message = "لا توجد بيانات لعرضها.",
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-gray-300 bg-gray-50 p-12 text-center",
        className
      )}
    >
      <Inbox className="h-12 w-12 text-gray-400" />
      <p className="text-sm font-medium text-gray-500">{message}</p>
    </div>
  );
}
