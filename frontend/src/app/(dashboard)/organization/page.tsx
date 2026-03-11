"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getOrganizationTree,
  createOrganizationUnit,
  updateOrganizationUnit,
} from "@/lib/api/organization";
import type { OrganizationUnit } from "@/types/organization";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { ErrorState } from "@/components/shared/ErrorState";
import { EmptyState } from "@/components/shared/EmptyState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";
import { ChevronDown, ChevronLeft, Plus, Pencil, Ban } from "lucide-react";

const UNIT_TYPE_LABELS: Record<string, string> = {
  daira: "دائرة",
  mudiriya: "مديرية",
  qism: "قسم",
};

const UNIT_TYPE_COLORS: Record<string, string> = {
  daira: "bg-purple-100 text-purple-700",
  mudiriya: "bg-blue-100 text-blue-700",
  qism: "bg-teal-100 text-teal-700",
};

const QISM_ROLE_LABELS: Record<string, string> = {
  regular: "عادي",
  planning: "تخطيط",
  statistics: "إحصاء",
};

const QISM_ROLE_COLORS: Record<string, string> = {
  regular: "bg-gray-100 text-gray-600",
  planning: "bg-amber-100 text-amber-700",
  statistics: "bg-indigo-100 text-indigo-700",
};

interface UnitFormData {
  name: string;
  code: string;
  unit_type: "daira" | "mudiriya" | "qism";
  qism_role: "regular" | "planning" | "statistics";
  parent: number | null;
}

const initialFormData: UnitFormData = {
  name: "",
  code: "",
  unit_type: "daira",
  qism_role: "regular",
  parent: null,
};

export default function OrganizationPage() {
  const queryClient = useQueryClient();
  const [expandedNodes, setExpandedNodes] = useState<Set<number>>(new Set());
  const [dialogOpen, setDialogOpen] = useState(false);
  const [formData, setFormData] = useState<UnitFormData>(initialFormData);
  const [editingId, setEditingId] = useState<number | null>(null);

  const {
    data: tree,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["organization-tree"],
    queryFn: getOrganizationTree,
  });

  const createMutation = useMutation({
    mutationFn: (data: Partial<OrganizationUnit>) => createOrganizationUnit(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["organization-tree"] });
      closeDialog();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<OrganizationUnit> }) =>
      updateOrganizationUnit(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["organization-tree"] });
      closeDialog();
    },
  });

  const toggleNode = (id: number) => {
    setExpandedNodes((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const openAddDialog = (parentId: number | null = null, parentType?: string) => {
    let defaultType: "daira" | "mudiriya" | "qism" = "daira";
    if (parentType === "daira") defaultType = "mudiriya";
    if (parentType === "mudiriya" || parentType === "daira") defaultType = "qism";

    setFormData({ ...initialFormData, parent: parentId, unit_type: defaultType });
    setEditingId(null);
    setDialogOpen(true);
  };

  const openEditDialog = (unit: OrganizationUnit) => {
    setFormData({
      name: unit.name,
      code: unit.code,
      unit_type: unit.unit_type,
      qism_role: unit.qism_role,
      parent: unit.parent,
    });
    setEditingId(unit.id);
    setDialogOpen(true);
  };

  const closeDialog = () => {
    setDialogOpen(false);
    setFormData(initialFormData);
    setEditingId(null);
  };

  const handleSubmit = () => {
    if (editingId) {
      updateMutation.mutate({ id: editingId, data: formData });
    } else {
      createMutation.mutate(formData);
    }
  };

  const handleDeactivate = (unit: OrganizationUnit) => {
    updateMutation.mutate({
      id: unit.id,
      data: { is_active: !unit.is_active },
    });
  };

  const isMutating = createMutation.isPending || updateMutation.isPending;

  if (isLoading) {
    return <LoadingSpinner size="lg" />;
  }

  if (isError) {
    return <ErrorState onRetry={() => refetch()} />;
  }

  const renderNode = (node: OrganizationUnit, level: number = 0) => {
    const hasChildren = node.children && node.children.length > 0;
    const isExpanded = expandedNodes.has(node.id);

    return (
      <div key={node.id}>
        <div
          className={`flex items-center gap-3 py-3 px-4 hover:bg-gray-50 rounded-lg transition ${
            !node.is_active ? "opacity-50" : ""
          }`}
          style={{ paddingRight: `${level * 32 + 16}px` }}
        >
          {/* زر التوسيع */}
          <button
            onClick={() => toggleNode(node.id)}
            className={`w-6 h-6 flex items-center justify-center rounded transition ${
              hasChildren
                ? "hover:bg-gray-200 text-gray-600"
                : "text-transparent cursor-default"
            }`}
            disabled={!hasChildren}
          >
            {hasChildren &&
              (isExpanded ? (
                <ChevronDown className="w-4 h-4" />
              ) : (
                <ChevronLeft className="w-4 h-4" />
              ))}
          </button>

          {/* اسم الوحدة */}
          <div className="flex-1 min-w-0">
            <span className="font-medium text-gray-900">{node.name}</span>
            <span className="text-xs text-gray-400 mr-2">({node.code})</span>
          </div>

          {/* شارة نوع الوحدة */}
          <span
            className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${
              UNIT_TYPE_COLORS[node.unit_type] || ""
            }`}
          >
            {UNIT_TYPE_LABELS[node.unit_type] || node.unit_type}
          </span>

          {/* شارة دور القسم */}
          {node.unit_type === "qism" && (
            <span
              className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                QISM_ROLE_COLORS[node.qism_role] || ""
              }`}
            >
              {QISM_ROLE_LABELS[node.qism_role] || node.qism_role}
            </span>
          )}

          {/* أزرار الإجراءات */}
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={() => openEditDialog(node)}
              title="تعديل"
            >
              <Pencil className="w-4 h-4" />
            </Button>
            {node.unit_type !== "qism" && (
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={() => openAddDialog(node.id, node.unit_type)}
                title="إضافة وحدة فرعية"
              >
                <Plus className="w-4 h-4" />
              </Button>
            )}
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-red-500 hover:text-red-700"
              onClick={() => handleDeactivate(node)}
              title={node.is_active ? "تعطيل" : "تفعيل"}
            >
              <Ban className="w-4 h-4" />
            </Button>
          </div>
        </div>

        {/* العناصر الفرعية */}
        {hasChildren && isExpanded && (
          <div>
            {node.children!.map((child) => renderNode(child, level + 1))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* العنوان */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">الهيكل التنظيمي</h1>
          <p className="text-gray-500 mt-1">إدارة الوحدات التنظيمية للمؤسسة</p>
        </div>
        <Button onClick={() => openAddDialog(null)}>
          <Plus className="w-4 h-4 ml-2" />
          إضافة وحدة جذرية
        </Button>
      </div>

      {/* الشجرة */}
      <div className="bg-white rounded-xl shadow-sm border">
        {!tree || tree.length === 0 ? (
          <EmptyState message="لا توجد وحدات تنظيمية بعد. ابدأ بإضافة وحدة جذرية." />
        ) : (
          <div className="divide-y divide-gray-50 p-2">
            {tree.map((node) => renderNode(node, 0))}
          </div>
        )}
      </div>

      {/* مربع حوار الإضافة/التعديل */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editingId ? "تعديل الوحدة التنظيمية" : "إضافة وحدة تنظيمية"}
            </DialogTitle>
            <DialogDescription>
              {editingId
                ? "قم بتعديل بيانات الوحدة التنظيمية"
                : "أدخل بيانات الوحدة التنظيمية الجديدة"}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="name">اسم الوحدة</Label>
              <Input
                id="name"
                value={formData.name}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, name: e.target.value }))
                }
                placeholder="أدخل اسم الوحدة"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="code">الرمز</Label>
              <Input
                id="code"
                value={formData.code}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, code: e.target.value }))
                }
                placeholder="أدخل رمز الوحدة"
                dir="ltr"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="unit_type">نوع الوحدة</Label>
              <select
                id="unit_type"
                value={formData.unit_type}
                onChange={(e) =>
                  setFormData((prev) => ({
                    ...prev,
                    unit_type: e.target.value as UnitFormData["unit_type"],
                  }))
                }
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-right"
                dir="rtl"
              >
                <option value="daira">دائرة</option>
                <option value="mudiriya">مديرية</option>
                <option value="qism">قسم</option>
              </select>
            </div>

            {formData.unit_type === "qism" && (
              <div className="space-y-2">
                <Label htmlFor="qism_role">دور القسم</Label>
                <select
                  id="qism_role"
                  value={formData.qism_role}
                  onChange={(e) =>
                    setFormData((prev) => ({
                      ...prev,
                      qism_role: e.target.value as UnitFormData["qism_role"],
                    }))
                  }
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-right"
                  dir="rtl"
                >
                  <option value="regular">عادي</option>
                  <option value="planning">تخطيط</option>
                  <option value="statistics">إحصاء</option>
                </select>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button onClick={handleSubmit} disabled={isMutating || !formData.name || !formData.code}>
              {isMutating
                ? "جارٍ الحفظ..."
                : editingId
                ? "حفظ التعديلات"
                : "إضافة"}
            </Button>
            <Button variant="outline" onClick={closeDialog}>
              إلغاء
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
