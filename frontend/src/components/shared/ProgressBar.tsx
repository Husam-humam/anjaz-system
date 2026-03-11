"use client";

import { cn } from "@/lib/utils";

interface ProgressBarProps {
  value: number;
  target: number;
  label: string;
  unit?: string;
}

export function ProgressBar({ value, target, label, unit }: ProgressBarProps) {
  const percentage = target > 0 ? Math.min(Math.round((value / target) * 100), 100) : 0;

  const barColor =
    percentage >= 100
      ? "bg-green-500"
      : percentage >= 75
        ? "bg-blue-500"
        : percentage >= 50
          ? "bg-yellow-500"
          : "bg-red-500";

  return (
    <div className="w-full space-y-1">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium text-foreground">{label}</span>
        <span className="text-muted-foreground">
          {value.toLocaleString("ar-IQ")} / {target.toLocaleString("ar-IQ")}
          {unit && ` ${unit}`}
          {" "}({percentage}%)
        </span>
      </div>
      <div className="h-2.5 w-full rounded-full bg-gray-200">
        <div
          className={cn("h-2.5 rounded-full transition-all duration-300", barColor)}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}
