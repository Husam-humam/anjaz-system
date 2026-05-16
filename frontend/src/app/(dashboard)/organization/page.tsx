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
import { Input } from "@/components/ui/input";
import { UnitTypeSettingsDialog } from "./UnitTypeSettingsDialog";
import {
  AlertCircle,
  ChevronDown,
  ChevronLeft,
  Plus,
  RefreshCw,
  Search,
  Settings,
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

/** يبحث عن عقدة بـ id داخل شجرة متفرّعة. */
function findNode(
  nodes: OrganizationUnit[],
  id: number,
): OrganizationUnit | null {
  for (const node of nodes) {
    if (node.id === id) return node;
    if (node.children?.length) {
      const found = findNode(node.children, id);
      if (found) return found;
    }
  }
  return null;
}

/** يجمع كل أحفاد عقدة معيّنة الذين هم أقسام نشطة، مع مسار الأب للعرض. */
function collectDescendantQisms(
  root: OrganizationUnit,
  parentPath: string | null = null,
): Array<OrganizationUnit & { parent_path: string | null }> {
  const out: Array<OrganizationUnit & { parent_path: string | null }> = [];
  const walk = (node: OrganizationUnit, path: string | null) => {
    if (node.unit_type === "qism" && node.is_active) {
      out.push({ ...node, parent_path: path });
    }
    if (node.children?.length) {
      const childPath = path ? `${path} / ${node.name}` : node.name;
      for (const child of node.children) walk(child, childPath);
    }
  };
  // نبدأ من children مباشرة لأن root نفسه نريد استثناءه (لو كان قسماً)
  for (const child of root.children ?? []) {
    walk(child, root.name);
  }
  return out;
}

/** يُسطِّح الشجرة كاملةً إلى قائمة كل الأقسام النشطة مع مسار الأب. */
function collectAllQisms(
  nodes: OrganizationUnit[],
): Array<OrganizationUnit & { parent_path: string | null }> {
  const out: Array<OrganizationUnit & { parent_path: string | null }> = [];
  const walk = (node: OrganizationUnit, path: string | null) => {
    if (node.unit_type === "qism" && node.is_active) {
      out.push({ ...node, parent_path: path });
    }
    if (node.children?.length) {
      const childPath = path ? `${path} / ${node.name}` : node.name;
      for (const child of node.children) walk(child, childPath);
    }
  };
  for (const node of nodes) walk(node, null);
  return out;
}

export default function OrganizationPage() {
  const queryClient = useQueryClient();
  const { isAdmin } = usePermissions();
  const [expandedNodes, setExpandedNodes] = useState<Set<number>>(new Set());
  const [syncReport, setSyncReport] = useState<OrganizationSyncReport | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [selectedQism, setSelectedQism] = useState<OrganizationUnit | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);

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
        <div className="flex items-center gap-3">
          {isAdmin() && syncMutation.isPending && (
            <span className="inline-flex items-center text-sm text-gray-500">
              <RefreshCw className="w-4 h-4 ml-2 animate-spin" />
              جارٍ المزامنة...
            </span>
          )}
          {isAdmin() && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setSettingsOpen(true)}
              title="إعدادات أنواع الوحدات"
            >
              <Settings className="w-4 h-4 ml-1" />
              إعدادات الأنواع
            </Button>
          )}
        </div>
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
        tree={tree ?? []}
        onClose={() => setSelectedQism(null)}
      />

      <UnitTypeSettingsDialog
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
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
  tree: OrganizationUnit[];
  onClose: () => void;
}

function QismAssignmentDialog({
  qism,
  assignments,
  tree,
  onClose,
}: QismAssignmentDialogProps) {
  const queryClient = useQueryClient();
  const [searchTerm, setSearchTerm] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);

  // عند فتح drawer لقسم جديد، نُصفّر حالة الإدخال
  useEffect(() => {
    setSearchTerm("");
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
      setSearchTerm("");
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

  // الأقسام المتاحة للإشراف = كل أقسام المؤسسة النشطة غير المُسنَدة كتخطيط
  // ولا المُشرَف عليها بالفعل. لا نُقيّد بالفرع — يستخدم الأدمن البحث للوصول.
  const planningUnitIds = new Set(assignments.map((a) => a.planning_unit));
  const supervisedUnitIds = new Set(
    assignments.flatMap((a) => a.supervised_units.map((s) => s.unit)),
  );

  // نُسطّح الشجرة كاملةً مع مسار الأب لكل قسم (يُساعد البحث على إيجاد الأقسام
  // بنفس الاسم في مديريّات مختلفة).
  const allQisms = collectAllQisms(tree);

  const availableForSupervision = allQisms.filter(
    (u) =>
      u.id !== qism.id &&
      !planningUnitIds.has(u.id) &&
      !supervisedUnitIds.has(u.id),
  );

  // تطبيق بحث المستخدم
  const term = searchTerm.trim().toLowerCase();
  const filteredAvailable = term
    ? availableForSupervision.filter(
        (u) =>
          u.name.toLowerCase().includes(term) ||
          u.code.toLowerCase().includes(term) ||
          (u.parent_path?.toLowerCase().includes(term) ?? false),
      )
    : availableForSupervision;

  return (
    <Dialog open={!!qism} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader className="pl-8">
          <DialogTitle className="text-xl">{qism.name}</DialogTitle>
          <DialogDescription className="flex flex-wrap items-center gap-x-2 gap-y-1">
            {qism.parent_name && (
              <span className="text-gray-600">ضمن: {qism.parent_name}</span>
            )}
            <span className="text-gray-400">•</span>
            <span>
              رمز: <span className="font-mono text-gray-700">{qism.code}</span>
            </span>
          </DialogDescription>
        </DialogHeader>

        {actionError && (
          <div className="bg-red-50 border border-red-200 rounded-md p-3 flex items-start gap-2">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-red-700 break-words">{actionError}</p>
          </div>
        )}

        {/* === القسم غير مُسنَد === */}
        {role === "unassigned" && (
          <div className="space-y-4">
            <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
              <p className="text-sm text-gray-700 leading-relaxed">
                هذا القسم لم يُسنَد بعد. يمكنه أن يعمل كقسم تخطيط (يُشرف على أقسام
                أخرى) أو يبقى عاديّاً ليُشرَف عليه من قِبَل قسم تخطيط آخر (من
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
          <div className="space-y-3">
            <div className="rounded-lg border border-teal-200 bg-teal-50 p-4">
              <p className="text-sm text-teal-900 mb-2">
                هذا القسم <strong>مُشرَف عليه</strong> من قِبَل قسم التخطيط:
              </p>
              <p className="text-base font-bold text-teal-900">
                {supervisor.planning_unit_name}
              </p>
              <p className="text-xs font-mono text-teal-700/70 mt-0.5">
                {supervisor.planning_unit_code}
              </p>
            </div>
            <p className="text-xs text-gray-500 px-1">
              لتعديل هذا الإشراف أو إزالته، افتح نافذة قسم التخطيط «{supervisor.planning_unit_name}» من الشجرة.
            </p>
          </div>
        )}

        {/* === القسم هو قسم تخطيط === */}
        {role === "planning" && planningAssignment && (
          <div className="space-y-5">
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 flex items-center justify-between gap-3">
              <div>
                <p className="text-sm text-amber-900">
                  يعمل كـ <strong>قسم تخطيط</strong>
                </p>
                <p className="text-xs text-amber-700 mt-0.5">
                  يُشرف على {planningAssignment.supervised_units.length} قسماً
                </p>
              </div>
              <span className="inline-flex items-center rounded-full bg-amber-100 px-3 py-1 text-xs font-bold text-amber-800">
                {planningAssignment.supervised_units.length}
              </span>
            </div>

            {/* صندوق إضافة قسم بالبحث */}
            <div className="space-y-2">
              <Label className="text-sm font-semibold">
                إضافة قسم تحت إشرافه
              </Label>
              <p className="text-xs text-gray-500">
                ابحث باسم القسم أو المديرية أو الرمز، ثم اضغط على القسم لإضافته.
              </p>
              <div className="relative">
                <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
                <Input
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  placeholder="ابحث عن قسم..."
                  className="pr-10"
                  dir="rtl"
                />
              </div>

              {/* لائحة النتائج */}
              <div className="border rounded-lg overflow-hidden bg-white">
                {availableForSupervision.length === 0 ? (
                  <p className="text-sm text-gray-400 text-center py-4">
                    كل الأقسام في المؤسسة إمّا أقسام تخطيط أو تحت إشراف بالفعل.
                  </p>
                ) : filteredAvailable.length === 0 ? (
                  <p className="text-sm text-gray-400 text-center py-4">
                    لا توجد نتائج مطابقة لـ «{searchTerm}»
                  </p>
                ) : (
                  <>
                    <div className="text-xs text-gray-500 px-3 py-1.5 bg-gray-50 border-b">
                      {term
                        ? `${filteredAvailable.length} من ${availableForSupervision.length} قسماً مطابقاً`
                        : `${availableForSupervision.length} قسماً متاحاً`}
                    </div>
                    <ul className="divide-y divide-gray-100 max-h-60 overflow-y-auto">
                      {filteredAvailable.slice(0, 100).map((u) => (
                        <li key={u.id}>
                          <button
                            type="button"
                            onClick={() =>
                              addSupervisedMutation.mutate({
                                assignmentId: planningAssignment.id,
                                unitId: u.id,
                              })
                            }
                            disabled={addSupervisedMutation.isPending}
                            className="w-full text-right px-4 py-2.5 hover:bg-blue-50 transition-colors flex items-center justify-between gap-3 disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            <div className="flex-1 min-w-0">
                              <p className="font-medium text-sm text-gray-900 truncate">
                                {u.name}
                              </p>
                              <p className="text-xs text-gray-400 truncate">
                                {u.parent_path ?? "—"}
                                <span className="mx-1.5">•</span>
                                <span className="font-mono">{u.code}</span>
                              </p>
                            </div>
                            <Plus className="w-4 h-4 text-blue-600 flex-shrink-0" />
                          </button>
                        </li>
                      ))}
                    </ul>
                    {filteredAvailable.length > 100 && (
                      <div className="text-xs text-gray-500 px-3 py-1.5 bg-gray-50 border-t text-center">
                        تم عرض أول 100 نتيجة — قلِّص البحث للوصول إلى المزيد.
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>

            {/* قائمة الأقسام المُشرَف عليها */}
            <div className="space-y-2">
              <Label className="text-sm font-semibold">
                الأقسام المُشرَف عليها
              </Label>
              <div className="border rounded-lg overflow-hidden bg-white">
                {planningAssignment.supervised_units.length === 0 ? (
                  <div className="text-center py-8 px-4">
                    <p className="text-sm text-gray-400">
                      لم تتم إضافة أي قسم بعد. استخدم القائمة أعلاه لإضافة الأقسام.
                    </p>
                  </div>
                ) : (
                  <ul className="divide-y divide-gray-100 max-h-72 overflow-y-auto">
                    {planningAssignment.supervised_units.map((s) => (
                      <li
                        key={s.id}
                        className="flex items-center justify-between gap-3 px-4 py-2.5 hover:bg-gray-50 transition-colors"
                      >
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-sm text-gray-900 truncate">
                            {s.unit_name}
                          </p>
                          <p className="text-xs text-gray-400 font-mono truncate">
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
                          className="h-8 w-8 flex-shrink-0 text-red-500 hover:text-red-700 hover:bg-red-50"
                          title="إزالة من الإشراف"
                        >
                          <X className="w-4 h-4" />
                        </Button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>

            {/* زر إلغاء دور التخطيط */}
            <div className="pt-3 border-t border-gray-200">
              <Button
                variant="ghost"
                className="text-red-600 hover:text-red-700 hover:bg-red-50 w-full justify-center"
                onClick={() => {
                  if (
                    confirm(
                      `إلغاء دور التخطيط لـ ${qism.name}؟ سيُحذف التخصيص وكل الأقسام المُشرَف عليها.`,
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

        <DialogFooter className="pt-2 border-t">
          <Button variant="outline" onClick={onClose}>
            إغلاق
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
