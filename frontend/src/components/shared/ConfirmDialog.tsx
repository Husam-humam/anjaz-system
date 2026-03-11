"use client";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title?: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel?: () => void;
  variant?: "default" | "destructive";
  loading?: boolean;
}

export function ConfirmDialog({
  open,
  onOpenChange,
  title = "تأكيد العملية",
  description = "هل أنت متأكد من أنك تريد المتابعة؟",
  confirmLabel = "تأكيد",
  cancelLabel = "إلغاء",
  onConfirm,
  onCancel,
  variant = "default",
  loading = false,
}: ConfirmDialogProps) {
  const handleCancel = () => {
    onCancel?.();
    onOpenChange(false);
  };

  const handleConfirm = () => {
    onConfirm();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button
            variant={variant === "destructive" ? "destructive" : "default"}
            onClick={handleConfirm}
            disabled={loading}
          >
            {loading ? "جاري التنفيذ..." : confirmLabel}
          </Button>
          <Button variant="outline" onClick={handleCancel} disabled={loading}>
            {cancelLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
