"use client";

import { useMemo, useState } from "react";
import { ChevronDown, ChevronLeft, FolderTree, Layers, Building } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { getOrganizationUnits } from "@/lib/api/organization";
import type { OrganizationUnit } from "@/types/organization";

/**
 * نموذج العقدة في الشجرة — يحتوي البيانات المُجمّعة للوحدة.
 * يُستخدم في التقارير لعرض دوائر → مديريات → أقسام بشكل هرمي.
 * metrics قد تحتوي نصاً أو رقماً أو JSX عنصراً (مثل شارة ملوّنة للحالات).
 */
export interface TreeNodeData {
  unit_id: number;
  unit_name: string;
  unit_code: string;
  unit_type: "daira" | "mudiriya" | "qism";
  metrics: Record<string, React.ReactNode>;
  children?: TreeNodeData[];
  hasData?: boolean;
}

interface HierarchicalTreeProps {
  /** البيانات المُقدّمة بالفعل في شكل شجرة، أو سنبنيها من flat data */
  data: TreeNodeData[];
  /** أسماء الأعمدة (المقاييس) مع label */
  columns: Array<{ key: string; label: string; align?: "left" | "right" }>;
  /** معرف الوحدة العليا لفلترة الشجرة (اختياري) */
  rootFilter?: "institution" | "daira" | "mudiriya" | "qism";
  /** callback عند النقر على عقدة — يُفعّل وضع "عرض التفصيل" */
  onNodeClick?: (node: TreeNodeData) => void;
}

export function HierarchicalTree({
  data,
  columns,
  onNodeClick,
}: HierarchicalTreeProps) {
  return (
    <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-gray-50">
            <th className="text-right py-3 px-4 font-semibold text-gray-700">
              الوحدة التنظيمية
            </th>
            {columns.map((col) => (
              <th
                key={col.key}
                className={`py-3 px-4 font-semibold text-gray-700 ${
                  col.align === "left" ? "text-left" : "text-right"
                }`}
              >
                {col.label}
              </th>
            ))}
            {onNodeClick && (
              <th className="py-3 px-4 font-semibold text-gray-700 w-20"></th>
            )}
          </tr>
        </thead>
        <tbody>
          {data.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length + (onNodeClick ? 2 : 1)}
                className="py-8 text-center text-gray-400 text-sm"
              >
                لا توجد بيانات للعرض
              </td>
            </tr>
          ) : (
            data.map((node) => (
              <TreeRow
                key={node.unit_id}
                node={node}
                level={0}
                columns={columns}
                onNodeClick={onNodeClick}
              />
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

interface TreeRowProps {
  node: TreeNodeData;
  level: number;
  columns: Array<{ key: string; label: string; align?: "left" | "right" }>;
  onNodeClick?: (node: TreeNodeData) => void;
}

function TreeRow({ node, level, columns, onNodeClick }: TreeRowProps) {
  // الدوائر مفتوحة افتراضياً، البقية مغلقة
  const [expanded, setExpanded] = useState(level === 0);

  const hasChildren = Boolean(node.children && node.children.length > 0);
  const Icon =
    node.unit_type === "daira"
      ? FolderTree
      : node.unit_type === "mudiriya"
      ? Layers
      : Building;
  const iconColor =
    node.unit_type === "daira"
      ? "text-blue-600"
      : node.unit_type === "mudiriya"
      ? "text-emerald-600"
      : "text-amber-600";
  const typeLabel =
    node.unit_type === "daira"
      ? "دائرة"
      : node.unit_type === "mudiriya"
      ? "مديرية"
      : "قسم";

  const toggle = () => {
    if (hasChildren) setExpanded((v) => !v);
  };

  return (
    <>
      <tr
        className={`border-b border-gray-100 ${
          hasChildren ? "cursor-pointer hover:bg-gray-50" : ""
        } ${level === 0 ? "bg-gray-50/50 font-medium" : ""}`}
        onClick={toggle}
      >
        <td className="py-2.5 px-4">
          <div
            className="flex items-center gap-2"
            style={{ paddingInlineStart: `${level * 24}px` }}
          >
            <div className="w-4 h-4 flex-shrink-0">
              {hasChildren ? (
                expanded ? (
                  <ChevronDown className="w-4 h-4 text-gray-500" />
                ) : (
                  <ChevronLeft className="w-4 h-4 text-gray-500" />
                )
              ) : null}
            </div>
            <Icon className={`w-4 h-4 flex-shrink-0 ${iconColor}`} />
            <div className="min-w-0">
              <span className="text-gray-900">{node.unit_name}</span>
              <span className="text-gray-400 text-xs mr-2">{typeLabel}</span>
            </div>
          </div>
        </td>
        {columns.map((col) => (
          <td
            key={col.key}
            className={`py-2.5 px-4 ${
              col.align === "left" ? "text-left" : "text-right"
            }`}
            dir={col.align === "left" ? "ltr" : undefined}
          >
            {node.metrics[col.key] ?? "—"}
          </td>
        ))}
        {onNodeClick && (
          <td className="py-2.5 px-4 text-left">
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onNodeClick(node);
              }}
              className="text-xs text-blue-600 hover:text-blue-800 font-medium hover:underline"
            >
              عرض
            </button>
          </td>
        )}
      </tr>
      {expanded &&
        node.children?.map((child) => (
          <TreeRow
            key={child.unit_id}
            node={child}
            level={level + 1}
            columns={columns}
            onNodeClick={onNodeClick}
          />
        ))}
    </>
  );
}

// ═══════════════════════════════════════════════════════════
// Helper: بناء شجرة من bytes data + org units
// ═══════════════════════════════════════════════════════════

/**
 * يبني شجرة من بيانات مسطّحة (لكل قسم) باستخدام الهيكل التنظيمي.
 * القيم على مستوى الدائرة/المديرية تُحسب من sum أو avg لأقسامها.
 */
export function useBuildHierarchy<T extends { qism_id: number }>(
  flatData: T[],
  computeMetrics: (node: {
    unit: OrganizationUnit;
    descendantQismIds: number[];
    ownData: T | null;
  }) => Record<string, React.ReactNode>,
  opts: { includeEmpty?: boolean } = {}
): TreeNodeData[] {
  const { data: unitsData } = useQuery({
    queryKey: ["org-units-all-for-tree"],
    queryFn: () => getOrganizationUnits({ page_size: "1000" }),
  });

  return useMemo(() => {
    const units = unitsData?.results || [];
    if (units.length === 0) return [];

    // فهرس الأقسام حسب id
    const flatByQismId = new Map<number, T>();
    flatData.forEach((item) => flatByQismId.set(item.qism_id, item));

    // بناء فهرس للوحدات
    const unitsById = new Map<number, OrganizationUnit>();
    units.forEach((u: OrganizationUnit) => unitsById.set(u.id, u));

    // بناء شجرة الأطفال
    const childrenByParent = new Map<number | null, OrganizationUnit[]>();
    units.forEach((u: OrganizationUnit) => {
      const key = u.parent || null;
      if (!childrenByParent.has(key)) childrenByParent.set(key, []);
      childrenByParent.get(key)!.push(u);
    });

    const getDescendantQismIds = (unit: OrganizationUnit): number[] => {
      if (unit.unit_type === "qism") return [unit.id];
      const result: number[] = [];
      const stack: OrganizationUnit[] = [...(childrenByParent.get(unit.id) || [])];
      while (stack.length > 0) {
        const node = stack.pop()!;
        if (node.unit_type === "qism" && !node.is_planning) {
          result.push(node.id);
        }
        const children = childrenByParent.get(node.id) || [];
        stack.push(...children);
      }
      return result;
    };

    const buildNode = (unit: OrganizationUnit): TreeNodeData | null => {
      if (!unit.is_active) return null;
      // استثناء أقسام التخطيط (لا تُرسل منجزات)
      if (unit.unit_type === "qism" && unit.is_planning) {
        return null;
      }

      const descendantQismIds = getDescendantQismIds(unit);
      const ownData = unit.unit_type === "qism" ? flatByQismId.get(unit.id) || null : null;

      // هل هذه العقدة (أو أحفادها) تحتوي بيانات؟
      const hasData =
        descendantQismIds.some((id) => flatByQismId.has(id)) || Boolean(ownData);

      if (!hasData && !opts.includeEmpty) return null;

      const children: TreeNodeData[] = [];
      for (const child of childrenByParent.get(unit.id) || []) {
        const childNode = buildNode(child);
        if (childNode) children.push(childNode);
      }

      const metrics = computeMetrics({
        unit,
        descendantQismIds,
        ownData,
      });

      return {
        unit_id: unit.id,
        unit_name: unit.name,
        unit_code: unit.code,
        unit_type: unit.unit_type as "daira" | "mudiriya" | "qism",
        metrics,
        children: children.length > 0 ? children : undefined,
        hasData,
      };
    };

    // الجذور: الدوائر + المديريات بدون أب
    const roots: TreeNodeData[] = [];
    const rootUnits = units.filter(
      (u: OrganizationUnit) =>
        (u.unit_type === "daira" && !u.parent) ||
        (u.unit_type === "mudiriya" && !u.parent)
    );
    for (const root of rootUnits) {
      const node = buildNode(root);
      if (node) roots.push(node);
    }
    return roots;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [unitsData, flatData]);
}
