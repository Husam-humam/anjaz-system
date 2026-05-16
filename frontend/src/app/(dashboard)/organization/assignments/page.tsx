"use client";

import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import {
  addSupervisedUnit,
  createPlanningAssignment,
  deletePlanningAssignment,
  getOrganizationUnits,
  getPlanningAssignments,
  removeSupervisedUnit,
} from "@/lib/api/organization";
import type { OrganizationUnit, PlanningAssignment } from "@/types/organization";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { ErrorState } from "@/components/shared/ErrorState";
import { EmptyState } from "@/components/shared/EmptyState";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { usePermissions } from "@/hooks/usePermissions";
import { getErrorMessage } from "@/lib/utils";
import { AlertCircle, ArrowRight, Plus, Trash2, X } from "lucide-react";

export default function PlanningAssignmentsPage() {
  const queryClient = useQueryClient();
  const { isAdmin } = usePermissions();
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [selectedPlanningUnit, setSelectedPlanningUnit] = useState<number | "">("");
  const [selectedContextParent, setSelectedContextParent] = useState<number | "">("");
  const [editingAssignment, setEditingAssignment] = useState<PlanningAssignment | null>(
    null,
  );
  const [unitToAdd, setUnitToAdd] = useState<number | "">("");

  const { data: assignmentsData, isLoading, isError, refetch } = useQuery({
    queryKey: ["planning-assignments"],
    queryFn: () => getPlanningAssignments(),
  });

  const { data: unitsData } = useQuery({
    queryKey: ["organization-units-all"],
    queryFn: () => getOrganizationUnits({ page_size: "1000" }),
  });

  const assignments = useMemo(
    () => assignmentsData?.results ?? [],
    [assignmentsData],
  );
  const allUnits = useMemo(() => unitsData?.results ?? [], [unitsData]);

  // الأقسام المتاحة لتكون «قسم تخطيط جديد»: type=qism وغير مُسنَدة كتخطيط
  const planningUnitsAlreadyAssigned = useMemo(
    () => new Set(assignments.map((a) => a.planning_unit)),
    [assignments],
  );
  const availablePlanningCandidates = useMemo(
    () =>
      allUnits.filter(
        (u: OrganizationUnit) =>
          u.unit_type === "qism" &&
          u.is_active &&
          !planningUnitsAlreadyAssigned.has(u.id),
      ),
    [allUnits, planningUnitsAlreadyAssigned],
  );

  // الأقسام المتاحة لتكون «مُشرَفاً عليها»: type=qism غير مُسنَدة كتخطيط وغير
  // مُشرَف عليها بالفعل (نعتمد على is_supervised).
  const supervisedAlreadyTakenIds = useMemo(() => {
    const ids = new Set<number>();
    assignments.forEach((a) =>
      a.supervised_units.forEach((s) => ids.add(s.unit)),
    );
    return ids;
  }, [assignments]);

  const availableSupervisedCandidates = useMemo(
    () =>
      allUnits.filter(
        (u: OrganizationUnit) =>
          u.unit_type === "qism" &&
          u.is_active &&
          !planningUnitsAlreadyAssigned.has(u.id) &&
          !supervisedAlreadyTakenIds.has(u.id),
      ),
    [allUnits, planningUnitsAlreadyAssigned, supervisedAlreadyTakenIds],
  );

  const createMutation = useMutation({
    mutationFn: (data: { planning_unit: number; context_parent?: number | null }) =>
      createPlanningAssignment(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["planning-assignments"] });
      queryClient.invalidateQueries({ queryKey: ["organization-tree"] });
      closeCreateDialog();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deletePlanningAssignment(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["planning-assignments"] });
      queryClient.invalidateQueries({ queryKey: ["organization-tree"] });
      setEditingAssignment(null);
    },
  });

  const addUnitMutation = useMutation({
    mutationFn: ({ assignmentId, unitId }: { assignmentId: number; unitId: number }) =>
      addSupervisedUnit(assignmentId, unitId),
    onSuccess: async (_data, vars) => {
      await queryClient.invalidateQueries({ queryKey: ["planning-assignments"] });
      await queryClient.invalidateQueries({ queryKey: ["organization-tree"] });
      const fresh = (
        await queryClient.fetchQuery({
          queryKey: ["planning-assignments"],
          queryFn: () => getPlanningAssignments(),
        })
      ).results.find((a) => a.id === vars.assignmentId);
      if (fresh) setEditingAssignment(fresh);
      setUnitToAdd("");
    },
  });

  const removeUnitMutation = useMutation({
    mutationFn: ({ assignmentId, unitId }: { assignmentId: number; unitId: number }) =>
      removeSupervisedUnit(assignmentId, unitId),
    onSuccess: async (_data, vars) => {
      await queryClient.invalidateQueries({ queryKey: ["planning-assignments"] });
      await queryClient.invalidateQueries({ queryKey: ["organization-tree"] });
      const fresh = (
        await queryClient.fetchQuery({
          queryKey: ["planning-assignments"],
          queryFn: () => getPlanningAssignments(),
        })
      ).results.find((a) => a.id === vars.assignmentId);
      if (fresh) setEditingAssignment(fresh);
    },
  });

  function closeCreateDialog() {
    setCreateDialogOpen(false);
    setSelectedPlanningUnit("");
    setSelectedContextParent("");
    createMutation.reset();
  }

  function handleCreate() {
    if (!selectedPlanningUnit) return;
    createMutation.mutate({
      planning_unit: Number(selectedPlanningUnit),
      context_parent: selectedContextParent ? Number(selectedContextParent) : null,
    });
  }

  if (!isAdmin()) {
    return (
      <div className="bg-amber-50 border border-amber-200 rounded-lg p-6 text-amber-800">
        هذه الصفحة متاحة لمدير قسم الإحصاء فقط.
      </div>
    );
  }

  if (isLoading) return <LoadingSpinner size="lg" />;
  if (isError) return <ErrorState onRetry={() => refetch()} />;

  const formatUnitLabel = (u: OrganizationUnit) =>
    u.parent_name ? `${u.name} — ${u.parent_name}` : u.name;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/organization"
            className="text-gray-500 hover:text-gray-700 transition"
          >
            <ArrowRight className="w-5 h-5" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              تخصيصات أقسام التخطيط
            </h1>
            <p className="text-gray-500 mt-1">
              حدّد أيّ قسم يعمل كـ «قسم تخطيط»، وأيّ الأقسام تحت إشرافه.
            </p>
          </div>
        </div>
        <Button
          onClick={() => setCreateDialogOpen(true)}
          disabled={availablePlanningCandidates.length === 0}
        >
          <Plus className="w-4 h-4 ml-2" />
          تخصيص قسم تخطيط جديد
        </Button>
      </div>

      {assignments.length === 0 ? (
        <EmptyState message="لم يُحدَّد أي قسم تخطيط بعد. ابدأ بتخصيص قسم." />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {assignments.map((assignment) => (
            <div
              key={assignment.id}
              className="bg-white rounded-xl shadow-sm border p-5 space-y-3"
            >
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="font-bold text-gray-900 text-lg">
                    {assignment.planning_unit_name}
                  </h2>
                  <p className="text-xs text-gray-400 font-mono">
                    {assignment.planning_unit_code}
                  </p>
                  {assignment.context_parent_name && (
                    <p className="text-sm text-gray-500 mt-1">
                      ضمن: {assignment.context_parent_name}
                    </p>
                  )}
                </div>
                <span className="inline-flex items-center rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-700">
                  تخطيط
                </span>
              </div>

              <div className="border-t pt-3">
                <p className="text-sm font-semibold text-gray-700 mb-2">
                  الأقسام المُشرَف عليها ({assignment.supervised_units.length})
                </p>
                {assignment.supervised_units.length === 0 ? (
                  <p className="text-sm text-gray-400 italic">لا توجد أقسام بعد</p>
                ) : (
                  <ul className="space-y-1 max-h-32 overflow-y-auto">
                    {assignment.supervised_units.map((s) => (
                      <li
                        key={s.id}
                        className="flex items-center justify-between text-sm bg-gray-50 rounded px-2 py-1"
                      >
                        <span>{s.unit_name}</span>
                        <span className="text-xs text-gray-400 font-mono">
                          {s.unit_code}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div className="flex gap-2 pt-2 border-t">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setEditingAssignment(assignment)}
                >
                  إدارة الأقسام المُشرَف عليها
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-red-600 hover:text-red-700"
                  onClick={() => {
                    if (
                      confirm(
                        `حذف تخصيص ${assignment.planning_unit_name}؟ سيُلغى دور التخطيط لهذا القسم.`,
                      )
                    ) {
                      deleteMutation.mutate(assignment.id);
                    }
                  }}
                  disabled={deleteMutation.isPending}
                >
                  <Trash2 className="w-4 h-4 ml-1" />
                  حذف
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* مربع حوار: إنشاء تخصيص جديد */}
      <Dialog
        open={createDialogOpen}
        onOpenChange={(open) => (open ? setCreateDialogOpen(true) : closeCreateDialog())}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>تخصيص قسم تخطيط جديد</DialogTitle>
            <DialogDescription>
              اختر القسم الذي سيعمل كقسم تخطيط. يمكنك إضافة الأقسام المُشرَف عليها لاحقاً.
            </DialogDescription>
          </DialogHeader>

          {createMutation.isError && (
            <div className="bg-red-50 border border-red-200 rounded-md p-3 flex items-start gap-2">
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-red-700">
                {getErrorMessage(createMutation.error)}
              </p>
            </div>
          )}

          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="planning-unit">القسم الذي سيعمل كقسم تخطيط</Label>
              <select
                id="planning-unit"
                value={selectedPlanningUnit}
                onChange={(e) =>
                  setSelectedPlanningUnit(
                    e.target.value ? Number(e.target.value) : "",
                  )
                }
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-right"
                dir="rtl"
              >
                <option value="">-- اختر --</option>
                {availablePlanningCandidates.map((u) => (
                  <option key={u.id} value={u.id}>
                    {formatUnitLabel(u)}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="context-parent">
                المديرية / الدائرة الأم (اختياري — للعرض في التقارير)
              </Label>
              <select
                id="context-parent"
                value={selectedContextParent}
                onChange={(e) =>
                  setSelectedContextParent(
                    e.target.value ? Number(e.target.value) : "",
                  )
                }
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-right"
                dir="rtl"
              >
                <option value="">— بدون —</option>
                {allUnits
                  .filter(
                    (u: OrganizationUnit) =>
                      u.unit_type === "daira" || u.unit_type === "mudiriya",
                  )
                  .map((u) => (
                    <option key={u.id} value={u.id}>
                      {formatUnitLabel(u)}
                    </option>
                  ))}
              </select>
            </div>
          </div>

          <DialogFooter>
            <Button
              onClick={handleCreate}
              disabled={!selectedPlanningUnit || createMutation.isPending}
            >
              {createMutation.isPending ? "جارٍ الإنشاء..." : "إنشاء التخصيص"}
            </Button>
            <Button variant="outline" onClick={closeCreateDialog}>
              إلغاء
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* مربع حوار: إدارة الأقسام المُشرَف عليها */}
      <Dialog
        open={editingAssignment !== null}
        onOpenChange={(open) => {
          if (!open) {
            setEditingAssignment(null);
            setUnitToAdd("");
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              إدارة الأقسام المُشرَف عليها — {editingAssignment?.planning_unit_name}
            </DialogTitle>
            <DialogDescription>
              أضِف أو احذف أقساماً تحت إشراف هذا القسم.
            </DialogDescription>
          </DialogHeader>

          {(addUnitMutation.isError || removeUnitMutation.isError) && (
            <div className="bg-red-50 border border-red-200 rounded-md p-3 flex items-start gap-2">
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-red-700">
                {getErrorMessage(
                  addUnitMutation.error || removeUnitMutation.error,
                )}
              </p>
            </div>
          )}

          <div className="space-y-4 py-2">
            <div className="flex gap-2">
              <select
                value={unitToAdd}
                onChange={(e) =>
                  setUnitToAdd(e.target.value ? Number(e.target.value) : "")
                }
                className="flex-1 h-10 rounded-md border border-input bg-background px-3 py-2 text-sm text-right"
                dir="rtl"
              >
                <option value="">-- اختر قسماً لإضافته --</option>
                {availableSupervisedCandidates.map((u) => (
                  <option key={u.id} value={u.id}>
                    {formatUnitLabel(u)}
                  </option>
                ))}
              </select>
              <Button
                onClick={() => {
                  if (!editingAssignment || !unitToAdd) return;
                  addUnitMutation.mutate({
                    assignmentId: editingAssignment.id,
                    unitId: Number(unitToAdd),
                  });
                }}
                disabled={!unitToAdd || addUnitMutation.isPending}
              >
                إضافة
              </Button>
            </div>

            <div className="border rounded-lg max-h-72 overflow-y-auto">
              {editingAssignment && editingAssignment.supervised_units.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-6">
                  لا توجد أقسام بعد
                </p>
              ) : (
                <ul className="divide-y">
                  {editingAssignment?.supervised_units.map((s) => (
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
                        onClick={() => {
                          if (!editingAssignment) return;
                          removeUnitMutation.mutate({
                            assignmentId: editingAssignment.id,
                            unitId: s.unit,
                          });
                        }}
                        disabled={removeUnitMutation.isPending}
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

          <DialogFooter>
            <Button variant="outline" onClick={() => setEditingAssignment(null)}>
              إغلاق
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
