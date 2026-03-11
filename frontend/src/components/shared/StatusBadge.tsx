"use client";

import { cn } from "@/lib/utils";
import { STATUS_LABELS, STATUS_COLORS } from "@/lib/constants";

interface StatusBadgeProps {
  status: string;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const label = STATUS_LABELS[status] || status;
  const colorClasses = STATUS_COLORS[status] || "bg-gray-100 text-gray-700";

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold",
        colorClasses,
        className
      )}
    >
      {label}
    </span>
  );
}
