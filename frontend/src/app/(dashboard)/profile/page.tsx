"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useAuthStore } from "@/stores/authStore";
import { changePassword } from "@/lib/api/users";
import { ROLE_LABELS } from "@/lib/constants";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { User, Shield, Building, Lock, CheckCircle, AlertCircle } from "lucide-react";

export default function ProfilePage() {
  const user = useAuthStore((s) => s.user);
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  const passwordMutation = useMutation({
    mutationFn: (data: { old_password: string; new_password: string }) =>
      changePassword(data),
    onSuccess: () => {
      setSuccessMessage("تم تغيير كلمة المرور بنجاح");
      setErrorMessage("");
      setOldPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setTimeout(() => setSuccessMessage(""), 5000);
    },
    onError: () => {
      setErrorMessage("فشل تغيير كلمة المرور. تأكد من صحة كلمة المرور الحالية.");
      setSuccessMessage("");
    },
  });

  const handleChangePassword = () => {
    setErrorMessage("");
    setSuccessMessage("");

    if (newPassword !== confirmPassword) {
      setErrorMessage("كلمة المرور الجديدة وتأكيدها غير متطابقتين.");
      return;
    }

    if (newPassword.length < 8) {
      setErrorMessage("يجب أن تكون كلمة المرور الجديدة 8 أحرف على الأقل.");
      return;
    }

    passwordMutation.mutate({
      old_password: oldPassword,
      new_password: newPassword,
    });
  };

  if (!user) return null;

  return (
    <div className="space-y-6 max-w-2xl">
      {/* العنوان */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">الملف الشخصي</h1>
        <p className="text-gray-500 mt-1">عرض معلومات الحساب وتغيير كلمة المرور</p>
      </div>

      {/* معلومات المستخدم */}
      <div className="bg-white rounded-xl shadow-sm border p-6">
        {/* الصورة الرمزية والاسم */}
        <div className="flex items-center gap-5 pb-6 border-b border-gray-100">
          <div className="w-20 h-20 bg-primary-100 text-primary-600 rounded-full flex items-center justify-center text-3xl font-bold flex-shrink-0">
            {user.full_name.charAt(0)}
          </div>
          <div>
            <h2 className="text-xl font-bold text-gray-900">
              {user.full_name}
            </h2>
            <span className="inline-flex items-center rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700 mt-1">
              {ROLE_LABELS[user.role] || user.role}
            </span>
          </div>
        </div>

        {/* تفاصيل الحساب */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-6">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-lg bg-gray-100 flex items-center justify-center flex-shrink-0">
              <User className="w-5 h-5 text-gray-500" />
            </div>
            <div>
              <p className="text-sm text-gray-500">اسم المستخدم</p>
              <p className="font-medium text-gray-900" dir="ltr">
                {user.username}
              </p>
            </div>
          </div>

          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-lg bg-gray-100 flex items-center justify-center flex-shrink-0">
              <Shield className="w-5 h-5 text-gray-500" />
            </div>
            <div>
              <p className="text-sm text-gray-500">الدور</p>
              <p className="font-medium text-gray-900">
                {ROLE_LABELS[user.role] || user.role}
              </p>
            </div>
          </div>

          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-lg bg-gray-100 flex items-center justify-center flex-shrink-0">
              <Building className="w-5 h-5 text-gray-500" />
            </div>
            <div>
              <p className="text-sm text-gray-500">الوحدة التنظيمية</p>
              <p className="font-medium text-gray-900">
                {user.unit?.name || "غير محدد"}
              </p>
              {user.unit?.code && (
                <p className="text-xs text-gray-400" dir="ltr">
                  {user.unit.code}
                </p>
              )}
            </div>
          </div>

          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-lg bg-gray-100 flex items-center justify-center flex-shrink-0">
              <CheckCircle className="w-5 h-5 text-gray-500" />
            </div>
            <div>
              <p className="text-sm text-gray-500">حالة الحساب</p>
              <p className="font-medium text-green-600">
                {user.is_active ? "نشط" : "غير نشط"}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* تغيير كلمة المرور */}
      <div className="bg-white rounded-xl shadow-sm border p-6">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-lg bg-amber-100 flex items-center justify-center">
            <Lock className="w-5 h-5 text-amber-600" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-gray-900">
              تغيير كلمة المرور
            </h3>
            <p className="text-sm text-gray-500">
              قم بتحديث كلمة المرور الخاصة بك
            </p>
          </div>
        </div>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="old-password">كلمة المرور الحالية</Label>
            <Input
              id="old-password"
              type="password"
              value={oldPassword}
              onChange={(e) => setOldPassword(e.target.value)}
              placeholder="أدخل كلمة المرور الحالية"
              dir="ltr"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="new-password">كلمة المرور الجديدة</Label>
            <Input
              id="new-password"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="أدخل كلمة المرور الجديدة (8 أحرف على الأقل)"
              dir="ltr"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="confirm-password">تأكيد كلمة المرور الجديدة</Label>
            <Input
              id="confirm-password"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="أعد إدخال كلمة المرور الجديدة"
              dir="ltr"
            />
          </div>

          {/* رسائل النجاح والخطأ */}
          {successMessage && (
            <div className="flex items-center gap-2 bg-green-50 border border-green-200 text-green-700 rounded-lg px-4 py-3 text-sm">
              <CheckCircle className="w-4 h-4 flex-shrink-0" />
              {successMessage}
            </div>
          )}

          {errorMessage && (
            <div className="flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              {errorMessage}
            </div>
          )}

          <div className="pt-2">
            <Button
              onClick={handleChangePassword}
              disabled={
                passwordMutation.isPending ||
                !oldPassword ||
                !newPassword ||
                !confirmPassword
              }
            >
              {passwordMutation.isPending
                ? "جارٍ تغيير كلمة المرور..."
                : "تغيير كلمة المرور"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
