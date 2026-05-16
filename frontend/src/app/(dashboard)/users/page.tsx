"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getUsers, createUser, updateUser } from "@/lib/api/users";
import {
  getOrganizationUnits,
  getViewScopeForUser,
  upsertViewScope,
  deleteViewScope,
} from "@/lib/api/organization";
import type { User } from "@/types/submissions";
import type { OrganizationUnit } from "@/types/organization";
import { ROLE_LABELS } from "@/lib/constants";
import { LoadingSpinner } from "@/components/shared/LoadingSpinner";
import { ErrorState } from "@/components/shared/ErrorState";
import { EmptyState } from "@/components/shared/EmptyState";
import { StatusBadge } from "@/components/shared/StatusBadge";
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
import { Plus, Search, Pencil, AlertCircle, Eye } from "lucide-react";
import { getErrorMessage } from "@/lib/utils";

interface UserFormData {
  username: string;
  full_name: string;
  password: string;
  role: string;
  unit: number | undefined;
}

const initialFormData: UserFormData = {
  username: "",
  full_name: "",
  password: "",
  role: "section_manager",
  unit: undefined,
};

export default function UsersPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [activeFilter, setActiveFilter] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [formData, setFormData] = useState<UserFormData>(initialFormData);
  const [editingId, setEditingId] = useState<number | null>(null);
  // نطاق الاطّلاع لدور viewer / planning_section الموسَّع
  const [viewScopeUserId, setViewScopeUserId] = useState<number | null>(null);
  const [viewScopeUnits, setViewScopeUnits] = useState<number[]>([]);
  const [existingScopeId, setExistingScopeId] = useState<number | undefined>();
  const [scopeError, setScopeError] = useState<string | null>(null);

  const params: Record<string, string> = {};
  if (search) params.search = search;
  if (roleFilter) params.role = roleFilter;
  if (activeFilter) params.is_active = activeFilter;

  const { data: usersData, isLoading, isError, refetch } = useQuery({
    queryKey: ["users", params],
    queryFn: () => getUsers(params),
  });

  const { data: unitsData } = useQuery({
    queryKey: ["organization-units-all"],
    queryFn: () => getOrganizationUnits({ page_size: "1000" }),
  });

  const createMutation = useMutation({
    mutationFn: (data: {
      username: string;
      full_name: string;
      password: string;
      role: string;
      unit?: number;
    }) => createUser(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      closeDialog();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<User> }) =>
      updateUser(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      closeDialog();
    },
  });

  const scopeSaveMutation = useMutation({
    mutationFn: (payload: {
      id?: number;
      user: number;
      viewable_units: number[];
    }) => upsertViewScope(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["view-scopes"] });
      closeScopeDialog();
    },
    onError: (err) => {
      setScopeError(getErrorMessage(err));
    },
  });

  const scopeDeleteMutation = useMutation({
    mutationFn: (id: number) => deleteViewScope(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["view-scopes"] });
      closeScopeDialog();
    },
  });

  const openAddDialog = () => {
    setFormData(initialFormData);
    setEditingId(null);
    setDialogOpen(true);
  };

  const openEditDialog = (user: User) => {
    setFormData({
      username: user.username,
      full_name: user.full_name,
      password: "",
      role: user.role,
      unit: user.unit?.id,
    });
    setEditingId(user.id);
    setDialogOpen(true);
  };

  const closeDialog = () => {
    setDialogOpen(false);
    setFormData(initialFormData);
    setEditingId(null);
    createMutation.reset();
    updateMutation.reset();
  };

  const openScopeDialog = async (user: User) => {
    setViewScopeUserId(user.id);
    setScopeError(null);
    setExistingScopeId(undefined);
    setViewScopeUnits([]);
    try {
      const existing = await getViewScopeForUser(user.id);
      if (existing) {
        setExistingScopeId(existing.id);
        setViewScopeUnits(existing.viewable_units);
      }
    } catch (err) {
      setScopeError(getErrorMessage(err));
    }
  };

  const closeScopeDialog = () => {
    setViewScopeUserId(null);
    setViewScopeUnits([]);
    setExistingScopeId(undefined);
    setScopeError(null);
    scopeSaveMutation.reset();
    scopeDeleteMutation.reset();
  };

  const handleRoleChange = (newRole: string) => {
    setFormData((prev) => ({
      ...prev,
      role: newRole,
      unit: prev.role === newRole ? prev.unit : undefined,
    }));
  };

  const handleSubmit = () => {
    if (editingId) {
      const updateData: Record<string, unknown> = {
        full_name: formData.full_name,
        role: formData.role,
      };
      if (formData.password) updateData.password = formData.password;
      if (formData.unit) updateData.unit = formData.unit;
      updateMutation.mutate({ id: editingId, data: updateData as Partial<User> });
    } else {
      createMutation.mutate({
        username: formData.username,
        full_name: formData.full_name,
        password: formData.password,
        role: formData.role,
        unit: formData.unit,
      });
    }
  };

  const handleToggleActive = (user: User) => {
    updateMutation.mutate({
      id: user.id,
      data: { is_active: !user.is_active } as Partial<User>,
    });
  };

  const isMutating = createMutation.isPending || updateMutation.isPending;
  const users = usersData?.results || [];
  const units = unitsData?.results || [];

  // الوحدات المتاحة لكل دور (بعد إلغاء qism_role):
  // - section_manager: قسم غير قسم تخطيط (is_planning=false)
  // - planning_section: قسم له PlanningAssignment (is_planning=true)
  // - statistics_admin / viewer: أيّ وحدة (الوحدة اختياريّة لكليهما)
  const getFilteredUnitsForRole = (role: string): OrganizationUnit[] => {
    if (role === "section_manager") {
      return units.filter(
        (u: OrganizationUnit) => u.unit_type === "qism" && !u.is_planning,
      );
    }
    if (role === "planning_section") {
      return units.filter(
        (u: OrganizationUnit) => u.unit_type === "qism" && u.is_planning === true,
      );
    }
    if (role === "statistics_admin" || role === "viewer") {
      return units;
    }
    return [];
  };

  const filteredUnitsForForm = getFilteredUnitsForRole(formData.role);

  const formatUnitLabel = (unit: OrganizationUnit): string => {
    const parentName = unit.parent_name ? ` — ${unit.parent_name}` : "";
    return `${unit.name}${parentName}`;
  };

  const toggleScopeUnit = (unitId: number) => {
    setViewScopeUnits((prev) =>
      prev.includes(unitId)
        ? prev.filter((id) => id !== unitId)
        : [...prev, unitId],
    );
  };

  if (isLoading) return <LoadingSpinner size="lg" />;
  if (isError) return <ErrorState onRetry={() => refetch()} />;

  const userNeedsScope = (role: string) =>
    role === "viewer" || role === "planning_section";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">إدارة المستخدمين</h1>
          <p className="text-gray-500 mt-1">عرض وإدارة حسابات المستخدمين</p>
        </div>
        <Button onClick={openAddDialog}>
          <Plus className="w-4 h-4 ml-2" />
          إضافة مستخدم
        </Button>
      </div>

      <div className="bg-white rounded-xl shadow-sm border p-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="relative">
            <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <Input
              placeholder="بحث عن مستخدم..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pr-10"
            />
          </div>
          <select
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-right"
            dir="rtl"
          >
            <option value="">جميع الأدوار</option>
            {Object.entries(ROLE_LABELS).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
          <select
            value={activeFilter}
            onChange={(e) => setActiveFilter(e.target.value)}
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-right"
            dir="rtl"
          >
            <option value="">الكل</option>
            <option value="true">نشط</option>
            <option value="false">غير نشط</option>
          </select>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
        {users.length === 0 ? (
          <EmptyState message="لا يوجد مستخدمون مطابقون لمعايير البحث." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50">
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    اسم المستخدم
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    الاسم الكامل
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    الدور
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    الوحدة التنظيمية
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    الحالة
                  </th>
                  <th className="text-right py-3 px-4 font-semibold text-gray-700">
                    إجراءات
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {users.map((user: User) => (
                  <tr key={user.id} className="hover:bg-gray-50 transition">
                    <td className="py-3 px-4 font-mono text-gray-900">
                      {user.username}
                    </td>
                    <td className="py-3 px-4 font-medium text-gray-900">
                      {user.full_name}
                    </td>
                    <td className="py-3 px-4">
                      <span className="inline-flex items-center rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-semibold text-blue-700">
                        {ROLE_LABELS[user.role] || user.role}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-gray-600">
                      {user.unit?.name || "—"}
                    </td>
                    <td className="py-3 px-4">
                      <StatusBadge
                        status={user.is_active ? "approved" : "rejected"}
                      />
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openEditDialog(user)}
                        >
                          <Pencil className="w-4 h-4 ml-1" />
                          تعديل
                        </Button>
                        {userNeedsScope(user.role) && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openScopeDialog(user)}
                          >
                            <Eye className="w-4 h-4 ml-1" />
                            نطاق الاطّلاع
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleToggleActive(user)}
                          className={
                            user.is_active
                              ? "text-red-600 hover:text-red-700"
                              : "text-green-600 hover:text-green-700"
                          }
                        >
                          {user.is_active ? "تعطيل" : "تفعيل"}
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* مربع حوار إضافة/تعديل المستخدم */}
      <Dialog
        open={dialogOpen}
        onOpenChange={(open) => (open ? setDialogOpen(true) : closeDialog())}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editingId ? "تعديل المستخدم" : "إضافة مستخدم جديد"}
            </DialogTitle>
            <DialogDescription>
              {editingId
                ? "قم بتعديل بيانات المستخدم"
                : "أدخل بيانات المستخدم الجديد"}
            </DialogDescription>
          </DialogHeader>

          {(createMutation.isError || updateMutation.isError) && (
            <div className="bg-red-50 border border-red-200 rounded-md p-3 flex items-start gap-2">
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-red-700">
                {getErrorMessage(createMutation.error || updateMutation.error)}
              </p>
            </div>
          )}

          <div className="space-y-4 py-4">
            {!editingId && (
              <div className="space-y-2">
                <Label htmlFor="user-username">اسم المستخدم</Label>
                <Input
                  id="user-username"
                  value={formData.username}
                  onChange={(e) =>
                    setFormData((prev) => ({ ...prev, username: e.target.value }))
                  }
                  placeholder="أدخل اسم المستخدم"
                  dir="ltr"
                />
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="user-fullname">الاسم الكامل</Label>
              <Input
                id="user-fullname"
                value={formData.full_name}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, full_name: e.target.value }))
                }
                placeholder="أدخل الاسم الكامل"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="user-password">
                {editingId
                  ? "كلمة المرور الجديدة (اتركها فارغة لعدم التغيير)"
                  : "كلمة المرور"}
              </Label>
              <Input
                id="user-password"
                type="password"
                value={formData.password}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, password: e.target.value }))
                }
                placeholder={
                  editingId ? "اترك فارغاً لعدم التغيير" : "أدخل كلمة المرور"
                }
                dir="ltr"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="user-role">الدور</Label>
              <select
                id="user-role"
                value={formData.role}
                onChange={(e) => handleRoleChange(e.target.value)}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-right"
                dir="rtl"
              >
                {Object.entries(ROLE_LABELS).map(([key, label]) => (
                  <option key={key} value={key}>
                    {label}
                  </option>
                ))}
              </select>
            </div>

            {formData.role !== "viewer" && formData.role !== "statistics_admin" && (
              <div className="space-y-2">
                <Label htmlFor="user-unit">
                  {formData.role === "planning_section"
                    ? "قسم التخطيط"
                    : "قسم العمل"}
                </Label>
                <select
                  id="user-unit"
                  value={formData.unit?.toString() || ""}
                  onChange={(e) =>
                    setFormData((prev) => ({
                      ...prev,
                      unit: e.target.value ? parseInt(e.target.value) : undefined,
                    }))
                  }
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-right"
                  dir="rtl"
                  disabled={filteredUnitsForForm.length === 0}
                >
                  <option value="">
                    {filteredUnitsForForm.length === 0
                      ? "لا توجد أقسام متاحة لهذا الدور"
                      : "-- اختر --"}
                  </option>
                  {filteredUnitsForForm.map((unit: OrganizationUnit) => (
                    <option key={unit.id} value={unit.id.toString()}>
                      {formatUnitLabel(unit)}
                    </option>
                  ))}
                </select>
                {formData.role === "planning_section" &&
                  filteredUnitsForForm.length === 0 && (
                    <p className="text-xs text-amber-700 bg-amber-50 border border-amber-100 rounded p-2">
                      ⚠️ لا يوجد قسم تخطيط مُسنَد بعد. أنشئه من صفحة «إدارة
                      تخصيصات التخطيط» أولاً.
                    </p>
                  )}
              </div>
            )}

            {formData.role === "viewer" && (
              <div className="bg-blue-50 border border-blue-100 rounded-md p-3 text-xs text-blue-700">
                <strong>دور المُطّلِع:</strong> قراءة فقط — لا يستطيع الإرسال أو
                الاعتماد أو التعديل. بعد إنشاء المستخدم، حدّد نطاق اطّلاعه من
                زر «نطاق الاطّلاع».
              </div>
            )}
          </div>

          <DialogFooter>
            <Button
              onClick={handleSubmit}
              disabled={
                isMutating ||
                !formData.full_name ||
                (!editingId && (!formData.username || !formData.password))
              }
            >
              {isMutating
                ? "جارٍ الحفظ..."
                : editingId
                ? "حفظ التعديلات"
                : "إضافة المستخدم"}
            </Button>
            <Button variant="outline" onClick={closeDialog}>
              إلغاء
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* مربع حوار نطاق الاطّلاع */}
      <Dialog
        open={viewScopeUserId !== null}
        onOpenChange={(open) => {
          if (!open) closeScopeDialog();
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>تحديد نطاق الاطّلاع</DialogTitle>
            <DialogDescription>
              اختر الوحدات التي يمكن لهذا المستخدم الاطّلاع على منجزاتها (دون
              التحكّم بها).
            </DialogDescription>
          </DialogHeader>

          {scopeError && (
            <div className="bg-red-50 border border-red-200 rounded-md p-3 flex items-start gap-2">
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-red-700">{scopeError}</p>
            </div>
          )}

          <div className="space-y-2 py-2 max-h-80 overflow-y-auto border rounded-md p-3">
            {units
              .filter((u: OrganizationUnit) => u.unit_type === "qism" && u.is_active)
              .map((u: OrganizationUnit) => (
                <label
                  key={u.id}
                  className="flex items-center gap-2 text-sm hover:bg-gray-50 px-2 py-1 rounded cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={viewScopeUnits.includes(u.id)}
                    onChange={() => toggleScopeUnit(u.id)}
                    className="rounded"
                  />
                  <span className="flex-1">{u.name}</span>
                  <span className="text-xs text-gray-400">
                    {u.parent_name || "—"}
                  </span>
                </label>
              ))}
          </div>

          <DialogFooter>
            <Button
              onClick={() => {
                if (!viewScopeUserId) return;
                scopeSaveMutation.mutate({
                  id: existingScopeId,
                  user: viewScopeUserId,
                  viewable_units: viewScopeUnits,
                });
              }}
              disabled={scopeSaveMutation.isPending}
            >
              {scopeSaveMutation.isPending ? "جارٍ الحفظ..." : "حفظ"}
            </Button>
            {existingScopeId && (
              <Button
                variant="outline"
                className="text-red-600"
                onClick={() => {
                  if (
                    existingScopeId &&
                    confirm("حذف نطاق الاطّلاع لهذا المستخدم؟")
                  ) {
                    scopeDeleteMutation.mutate(existingScopeId);
                  }
                }}
                disabled={scopeDeleteMutation.isPending}
              >
                حذف النطاق
              </Button>
            )}
            <Button variant="outline" onClick={closeScopeDialog}>
              إلغاء
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
