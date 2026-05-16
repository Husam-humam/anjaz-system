"use client";

import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import {
  getOrganizationTree,
  syncOrganizationFromExternal,
} from "@/lib/api/organization";
import type { OrganizationUnit, OrganizationSyncReport } from "@/types/organization";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { ErrorState } from "@/components/shared/ErrorState";
import { EmptyState } from "@/components/shared/EmptyState";
import { Button } from "@/components/ui/button";
import { usePermissions } from "@/hooks/usePermissions";
import {
  QISM_ASSIGNMENT_COLORS,
  QISM_ASSIGNMENT_LABELS,
} from "@/lib/constants";
import { ChevronDown, ChevronLeft, RefreshCw, Settings } from "lucide-react";

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

export default function OrganizationPage() {
  const queryClient = useQueryClient();
  const { isAdmin } = usePermissions();
  const [expandedNodes, setExpandedNodes] = useState<Set<number>>(new Set());
  const [syncReport, setSyncReport] = useState<OrganizationSyncReport | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);

  const {
    data: tree,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["organization-tree"],
    queryFn: getOrganizationTree,
  });

  const syncMutation = useMutation({
    mutationFn: () => syncOrganizationFromExternal(false),
    onSuccess: (report) => {
      setSyncReport(report);
      setSyncError(null);
      queryClient.invalidateQueries({ queryKey: ["organization-tree"] });
    },
    onError: (err: unknown) => {
      // axios error
      const message =
        (err as { response?: { data?: { detail?: string } }; message?: string })
          ?.response?.data?.detail ||
        (err as { message?: string })?.message ||
        "تعذّر إجراء المزامنة";
      setSyncError(message);
      setSyncReport(null);
    },
  });

  // مزامنة تلقائيّة عند فتح الصفحة — للأدمن فقط (هو الوحيد المُخوَّل).
  // نستخدم useEffect بدون dependency على syncMutation لتجنّب التشغيل المتكرّر.
  useEffect(() => {
    if (isAdmin()) {
      syncMutation.mutate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
            يتم التحديث آلياً من النظام المركزي عند كل فتح لهذه الصفحة. للتعديل، استخدم النظام الخارجي.
          </p>
        </div>
        {isAdmin() && (
          <div className="flex items-center gap-2">
            {syncMutation.isPending && (
              <span className="inline-flex items-center text-sm text-gray-500">
                <RefreshCw className="w-4 h-4 ml-2 animate-spin" />
                جارٍ المزامنة...
              </span>
            )}
            <Link href="/organization/assignments">
              <Button>
                <Settings className="w-4 h-4 ml-2" />
                إدارة تخصيصات التخطيط
              </Button>
            </Link>
          </div>
        )}
      </div>

      {isAdmin() && (syncReport || syncError || syncMutation.isPending) && (
        <div
          className={`rounded-lg border p-4 ${
            syncError
              ? "border-red-200 bg-red-50 text-red-800"
              : syncMutation.isPending
              ? "border-blue-200 bg-blue-50 text-blue-800"
              : "border-emerald-200 bg-emerald-50 text-emerald-800"
          }`}
        >
          {syncMutation.isPending && (
            <p className="text-sm">جارٍ مزامنة الهيكل التنظيمي من النظام المركزي...</p>
          )}
          {syncError && (
            <p className="text-sm">
              <strong>تعذّرت المزامنة:</strong> {syncError}
            </p>
          )}
          {syncReport && !syncMutation.isPending && !syncError && (
            <p className="text-sm">
              <strong>تمّت المزامنة:</strong> {syncReport.summary}
            </p>
          )}
        </div>
      )}

      <div className="bg-white rounded-xl shadow-sm border">
        {!tree || tree.length === 0 ? (
          <EmptyState message="لا توجد وحدات تنظيمية بعد. اضغط «مزامنة الآن» لجلبها من النظام المركزي." />
        ) : (
          <div className="divide-y divide-gray-50 p-2">
            {tree.map((node) => renderNode(node, 0))}
          </div>
        )}
      </div>
    </div>
  );
}
