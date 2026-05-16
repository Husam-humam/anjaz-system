"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getOrganizationTree,
  getPlanningAssignments,
  syncOrganizationFromExternal,
  createPlanningAssignment,
  deletePlanningAssignment,
  addSupervisedUnit,
  removeSupervisedUnit,
} from "@/lib/api/organization";
import type {
  OrganizationUnit,
  OrganizationSyncReport,
  PlanningAssignment,
} from "@/types/organization";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { ErrorState } from "@/components/shared/ErrorState";
import { EmptyState } from "@/components/shared/EmptyState";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { usePermissions } from "@/hooks/usePermissions";
import { getErrorMessage } from "@/lib/utils";
import {
  QISM_ASSIGNMENT_COLORS,
  QISM_ASSIGNMENT_LABELS,
} from "@/lib/constants";
import {
  AlertCircle,
  ChevronDown,
  ChevronLeft,
  Plus,
  RefreshCw,
  Trash2,
  X,
} from "lucide-react";

const UNIT_TYPE_LABELS: Record<string, string> = {
  daira: "دائرة",
  mudiriya: "مديرية",
  qism: "قسم",
};

const UNIT_TYPE_COLORS: Record<string, string> = {
  daira: "bg-purple-100 text-purple-700",
  mudiriya: "bg-blue-100 text-blue-700",
  qism: "bg-blue-50 text-blue-600",
};

function qismBadge(node: OrganizationUnit) {
  if (node.unit_type !== "qism") return null;
  if (node.is_planning) {
    return (
      <span
        className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${QISM_ASSIGNMENT_COLORS.planning}`}
      >
        {QISM_ASSIGNMENT_LABELS.planning}
      </span>
    );
  }
  if (node.is_supervised) {
    return (
      <span
        className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${QISM_ASSIGNMENT_COLORS.supervised}`}
      >
        {QISM_ASSIGNMENT_LABELS.supervised}
      </span>
    );
  }
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${QISM_ASSIGNMENT_COLORS.unassigned}`}
    >
      {QISM_ASSIGNMENT_LABELS.unassigned}
    </span>
  );
}

/** يجمع كل الأقسام في الشجرة بشكل مُسطَّح (للقوائم المنسدلة). */
function flattenQisms(nodes: OrganizationUnit[], parentName: string | null = null): Array<OrganizationUnit & { parent_path: string | null }> {
  const out: Array<OrganizationUnit & { parent_path: string | null }> = [];
  for (const node of nodes) {
    if (node.unit_type === "qism" && node.is_active) {
      out.push({ ...node, parent_path: parentName });
    }
    if (node.children?.length) {
      const childPath = parentName ? `${parentName} / ${node.name}` : node.name;
      out.push(...flattenQisms(node.children, childPath));
    }
  }
  return out;
}

export default function OrganizationPage() {
  const queryClient = useQueryClient();
  const { isAdmin } = usePermissions();
  const [expandedNodes, setExpandedNodes] = useState<Set<number>>(new Set());
  const [syncReport, setSyncReport] = useState<OrganizationSyncReport | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [selectedQism, setSelectedQism] = useState<OrganizationUnit | null>(null);

  const {
    data: tree,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["organization-tree"],
    queryFn: getOrganizationTree,
  });

  // كل التخصيصات — مطلوبة لمعرفة من يُشرف على كل قسم وللعرض في drawer
  const { data: assignmentsData } = useQuery({
    queryKey: ["planning-assignments"],
    queryFn: () => getPlanningAssignments({ page_size: "1000" }),
    enabled: !!tree && isAdmin(),
  });

  const allQisms = useMemo(
    () => (tree ? flattenQisms(tree) : []),
    [tree],
  );
  const assignments = useMemo(
    () => assignmentsData?.results ?? [],
    [assignmentsData],
  );

  const syncMutation = useMutation({
    mutationFn: () => syncOrganizationFromExternal(false),
    onSuccess: (report) => {
      setSyncReport(report);
      setSyncError(null);
      queryClient.invalidateQueries({ queryKey: ["organization-tree"] });
      queryClient.invalidateQueries({ queryKey: ["planning-assignments"] });
    },
    onError: (err: unknown) => {
      const message =
        (err as { response?: { data?: { detail?: string } }; message?: string })
          ?.response?.data?.detail ||
        (err as { message?: string })?.message ||
        "تعذّر إجراء المزامنة";
      setSyncError(message);
      setSyncReport(null);
    },
  });

  // مزامنة آليّة عند فتح الصفحة (للأدمن فقط — هو الوحيد المُخوَّل).
  useEffect(() => {
    if (isAdmin()) {
      syncMutation.mutate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggleNode = (id: number) => {
    setExpandedNodes((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  if (isLoading) return <LoadingSpinner size="lg" />;
  if (isError) return <ErrorState onRetry={() => refetch()} />;

  const renderNode = (node: OrganizationUnit, level: number = 0) => {
    const hasChildren = node.children && node.children.length > 0;
    const isExpanded = expandedNodes.has(node.id);
    const isClickable = isAdmin() && node.unit_type === "qism" && node.is_active;

    return (
      <div key={node.id}>
        <div
          className={`flex items-center gap-3 py-3 px-4 rounded-lg transition ${
            !node.is_active ? "opacity-50" : ""
          } ${isClickable ? "cursor-pointer hover:bg-blue-50" : "hover:bg-gray-50"}`}
          style={{ paddingRight: `${level * 32 + 16}px` }}
          onClick={() => {
            if (isClickable) setSelectedQism(node);
          }}
        >
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              toggleNode(node.id);
            }}
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

          <div className="flex-1 min-w-0">
            <span className="font-medium text-gray-900">{node.name}</span>
            <span className="text-xs text-gray-400 mr-2">({node.code})</span>
          </div>

          <span
            className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${
              UNIT_TYPE_COLORS[node.unit_type] || ""
            }`}
          >
            {UNIT_TYPE_LABELS[node.unit_type] || node.unit_type}
          </span>

          {qismBadge(node)}
        </div>

        {hasChildren && isExpanded && (
          <div>{node.children!.map((child) => renderNode(child, level + 1))}</div>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">الهيكل التنظيمي</h1>
          <p className="text-gray-500 mt-1">
            يتم التحديث آلياً من النظام المركزي عند كل فتح لهذه الصفحة.
            {isAdmin() && " اضغط على أي قسم لإدارة دوره (تخطيط / إشراف)."}
          </p>
        </div>
        {isAdmin() && syncMutation.isPending && (
          <span className="inline-flex items-center text-sm text-gray-500">
            <RefreshCw className="w-4 h-4 ml-2 animate-spin" />
            جارٍ المزامنة...
          </span>
        )}
      </div>

      {isAdmin() && (syncReport || syncError) && !syncMutation.isPending && (
        <div
          className={`rounded-lg border p-4 ${
            syncError
              ? "border-red-200 bg-red-50 text-red-800"
              : "border-emerald-200 bg-emerald-50 text-emerald-800"
          }`}
        >
          {syncError ? (
            <p className="text-sm">
              <strong>تعذّرت المزامنة:</strong> {syncError}
            </p>
          ) : (
            syncReport && (
              <p className="text-sm">
                <strong>تمّت المزامنة:</strong> {syncReport.summary}
              </p>
            )
          )}
        </div>
      )}

      <div className="bg-white rounded-xl shadow-sm border">
        {!tree || tree.length === 0 ? (
          <EmptyState message="لا توجد وحدات تنظيمية بعد. ستظهر بمجرد نجاح المزامنة." />
        ) : (
          <div className="divide-y divide-gray-50 p-2">
            {tree.map((node) => renderNode(node, 0))}
          </div>
        )}
      </div>

      <QismAssignmentDialog
        qism={selectedQism}
        assignments={assignments}
        allQisms={allQisms}
        onClose={() => setSelectedQism(null)}
      />
    </div>
  );
}

// ───────────────────────────────────────────────────────────
// Dialog إدارة تخصيص القسم
// ───────────────────────────────────────────────────────────

interface QismAssignmentDialogProps {
  qism: OrganizationUnit | null;
  assignments: PlanningAssignment[];
  allQisms: Array<OrganizationUnit & { parent_path: string | null }>;
  onClose: () => void;
}

function QismAssignmentDialog({
  qism,
  assignments,
  allQisms,
  onClose,
}: QismAssignmentDialogProps) {
  const queryClient = useQueryClient();
  const [unitToAdd, setUnitToAdd] = useState<number | "">("");
  const [actionError, setActionError] = useState<string | null>(null);

  // عند فتح drawer لقسم جديد، نُصفّر حالة الإدخال
  useEffect(() => {
    setUnitToAdd("");
    setActionError(null);
  }, [qism?.id]);

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ["planning-assignments"] });
    queryClient.invalidateQueries({ queryKey: ["organization-tree"] });
  };

  const handleError = (err: unknown) => setActionError(getErrorMessage(err));

  // الـ mutations يجب أن تُعرَّف قبل أي return مبكر لتثبيت ترتيب الـ hooks.
  // نستخدم `qism?.id` ونحرس داخل mutationFn بأن `qism` موجود وقت الاستدعاء.
  const createAssignmentMutation = useMutation({
    mutationFn: () => {
      if (!qism) throw new Error("لا يوجد قسم محدّد");
      return createPlanningAssignment({
        planning_unit: qism.id,
        context_parent: qism.parent,
      });
    },
    onSuccess: () => {
      invalidateAll();
      setActionError(null);
    },
    onError: handleError,
  });

  const deleteAssignmentMutation = useMutation({
    mutationFn: (id: number) => deletePlanningAssignment(id),
    onSuccess: () => {
      invalidateAll();
      onClose();
    },
    onError: handleError,
  });

  const addSupervisedMutation = useMutation({
    mutationFn: ({ assignmentId, unitId }: { assignmentId: number; unitId: number }) =>
      addSupervisedUnit(assignmentId, unitId),
    onSuccess: () => {
      setUnitToAdd("");
      setActionError(null);
      invalidateAll();
    },
    onError: handleError,
  });

  const removeSupervisedMutation = useMutation({
    mutationFn: ({ assignmentId, unitId }: { assignmentId: number; unitId: number }) =>
      removeSupervisedUnit(assignmentId, unitId),
    onSuccess: () => invalidateAll(),
    onError: handleError,
  });

  if (!qism) return null;

  // تحديد الحالة من البيانات المُحمَّلة
  const planningAssignment = assignments.find((a) => a.planning_unit === qism.id);
  const supervisor = assignments.find((a) =>
    a.supervised_units.some((s) => s.unit === qism.id),
  );

  const role: "planning" | "supervised" | "unassigned" = planningAssignment
    ? "planning"
    : supervisor
    ? "supervised"
    : "unassigned";

  // الأقسام المتاحة للإشراف عليها (غير مُسنَدة كتخطيط ولا مُشرَف عليها بالفعل)
  const planningUnitIds = new Set(assignments.map((a) => a.planning_unit));
  const supervisedUnitIds = new Set(
    assignments.flatMap((a) => a.supervised_units.map((s) => s.unit)),
  );
  const availableForSupervision = allQisms.filter(
    (u) =>
      u.id !== qism.id &&
      !planningUnitIds.has(u.id) &&
      !supervisedUnitIds.has(u.id),
  );

  return (
    <Dialog open={!!qism} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{qism.name}</DialogTitle>
          <DialogDescription>
            {qism.parent_name ? `ضمن: ${qism.parent_name} — ` : ""}
            رمز: <span className="font-mono">{qism.code}</span>
          </DialogDescription>
        </DialogHeader>

        {actionError && (
          <div className="bg-red-50 border border-red-200 rounded-md p-3 flex items-start gap-2">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-red-700">{actionError}</p>
          </div>
        )}

        {/* === القسم غير مُسنَد === */}
        {role === "unassigned" && (
          <div className="space-y-4 py-2">
            <div
              className={`rounded-lg border p-3 ${QISM_ASSIGNMENT_COLORS.unassigned} border-current/20`}
            >
              <p className="text-sm">
                هذا القسم لم يُسنَد بعد. يمكنه أن يعمل كقسم تخطيط (يُشرف على أقسام
                أخرى) أو يبقى عاديّاً ليُشرَف عليه من قبل قسم تخطيط آخر (من
                نافذة ذلك القسم).
              </p>
            </div>
            <Button
              onClick={() => createAssignmentMutation.mutate()}
              disabled={createAssignmentMutation.isPending}
              className="w-full"
            >
              {createAssignmentMutation.isPending
                ? "جارٍ التخصيص..."
                : "تخصيصه كقسم تخطيط"}
            </Button>
          </div>
        )}

        {/* === القسم تحت إشراف قسم تخطيط آخر === */}
        {role === "supervised" && supervisor && (
          <div className="py-2 space-y-2">
            <div
              className={`rounded-lg border p-3 ${QISM_ASSIGNMENT_COLORS.supervised} border-current/20`}
            >
              <p className="text-sm">
                هذا القسم <strong>مُشرَف عليه</strong> من قِبَل قسم التخطيط:
              </p>
              <p className="text-base font-bold mt-2">
                {supervisor.planning_unit_name}
              </p>
              <p className="text-xs font-mono text-gray-500">
                {supervisor.planning_unit_code}
              </p>
            </div>
            <p className="text-xs text-gray-500">
              لتعديل أو إزالة هذا الإشراف، افتح نافذة قسم التخطيط
              «{supervisor.planning_unit_name}».
            </p>
          </div>
        )}

        {/* === القسم هو قسم تخطيط === */}
        {role === "planning" && planningAssignment && (
          <div className="space-y-4 py-2">
            <div
              className={`rounded-lg border p-3 ${QISM_ASSIGNMENT_COLORS.planning} border-current/20`}
            >
              <p className="text-sm">
                هذا القسم يعمل كـ <strong>قسم تخطيط</strong>. يُشرف على{" "}
                {planningAssignment.supervised_units.length} قسماً.
              </p>
            </div>

            <div className="space-y-2">
              <Label>إضافة قسم تحت إشرافه</Label>
              <div className="flex gap-2">
                <select
                  value={unitToAdd}
                  onChange={(e) =>
                    setUnitToAdd(e.target.value ? Number(e.target.value) : "")
                  }
                  className="flex-1 h-10 rounded-md border border-input bg-background px-3 py-2 text-sm text-right"
                  dir="rtl"
                  disabled={availableForSupervision.length === 0}
                >
                  <option value="">
                    {availableForSupervision.length === 0
                      ? "لا توجد أقسام متاحة"
                      : "-- اختر قسماً --"}
                  </option>
                  {availableForSupervision.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.parent_path ? `${u.name} — ${u.parent_path}` : u.name}
                    </option>
                  ))}
                </select>
                <Button
                  onClick={() => {
                    if (!unitToAdd) return;
                    addSupervisedMutation.mutate({
                      assignmentId: planningAssignment.id,
                      unitId: Number(unitToAdd),
                    });
                  }}
                  disabled={!unitToAdd || addSupervisedMutation.isPending}
                >
                  <Plus className="w-4 h-4 ml-1" />
                  إضافة
                </Button>
              </div>
            </div>

            <div className="space-y-2">
              <Label>الأقسام المُشرَف عليها</Label>
              <div className="border rounded-lg max-h-60 overflow-y-auto">
                {planningAssignment.supervised_units.length === 0 ? (
                  <p className="text-sm text-gray-400 text-center py-6">
                    لا توجد أقسام بعد
                  </p>
                ) : (
                  <ul className="divide-y">
                    {planningAssignment.supervised_units.map((s) => (
                      <li
                        key={s.id}
                        className="flex items-center justify-between px-4 py-2 hover:bg-gray-50"
                      >
                        <div>
                          <p className="font-medium text-sm">{s.unit_name}</p>
                          <p className="text-xs text-gray-400 font-mono">
                            {s.unit_code}
                          </p>
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() =>
                            removeSupervisedMutation.mutate({
                              assignmentId: planningAssignment.id,
                              unitId: s.unit,
                            })
                          }
                          disabled={removeSupervisedMutation.isPending}
                          className="text-red-500 hover:text-red-700"
                        >
                          <X className="w-4 h-4" />
                        </Button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>

            <div className="pt-2 border-t">
              <Button
                variant="ghost"
                className="text-red-600 hover:text-red-700 w-full"
                onClick={() => {
                  if (
                    confirm(
                      `إلغاء دور التخطيط لـ ${qism.name}؟ سيُحذف التخصيص بكل الأقسام المُشرَف عليها.`,
                    )
                  ) {
                    deleteAssignmentMutation.mutate(planningAssignment.id);
                  }
                }}
                disabled={deleteAssignmentMutation.isPending}
              >
                <Trash2 className="w-4 h-4 ml-1" />
                إلغاء دور التخطيط لهذا القسم
              </Button>
            </div>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            إغلاق
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
