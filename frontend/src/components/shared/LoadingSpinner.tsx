import { cn } from "@/lib/utils";

interface LoadingSpinnerProps {
  className?: string;
  size?: "sm" | "md" | "lg";
}

export function LoadingSpinner({ className, size = "md" }: LoadingSpinnerProps) {
  const sizeClasses = {
    sm: "h-4 w-4 border-2",
    md: "h-8 w-8 border-2",
    lg: "h-12 w-12 border-3",
  };

  return (
    <div className="flex items-center justify-center p-4">
      <div
        className={cn(
          "animate-spin rounded-full border-primary-500 border-t-transparent",
          sizeClasses[size],
          className
        )}
        role="status"
        aria-label="جاري التحميل"
      >
        <span className="sr-only">جاري التحميل...</span>
      </div>
    </div>
  );
}
