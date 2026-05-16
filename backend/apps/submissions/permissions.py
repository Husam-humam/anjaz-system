"""
صلاحيات تطبيق المنجزات — التحقق من صلاحيات الوصول الخاصة بالمنجزات.
"""
from rest_framework import permissions


class CanViewSubmission(permissions.BasePermission):
    """
    التحقق من صلاحية **عرض** المنجز حسب نطاق الرؤية للمستخدم:
    - statistics_admin: جميع المنجزات
    - planning_section: المُدار + ViewScope
    - viewer: ViewScope فقط
    - section_manager: منجزات قسمه فقط
    """
    message = 'ليس لديك صلاحية لعرض هذا المنجز.'

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.role == 'statistics_admin':
            return True
        if user.role == 'section_manager':
            return obj.qism_id == user.unit_id
        if user.role in ('planning_section', 'viewer'):
            from .services import _user_view_scope_qism_ids
            scope_ids = _user_view_scope_qism_ids(user)
            if scope_ids is None:
                return True  # legacy central planner
            return obj.qism_id in scope_ids
        return False


class CanEditSubmission(permissions.BasePermission):
    """التحقق من إمكانية تعديل المنجز — مدير القسم فقط ومنجز قسمه"""
    message = 'ليس لديك صلاحية لتعديل هذا المنجز.'

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.role != 'section_manager':
            return False
        return obj.qism_id == user.unit_id


class IsNotViewer(permissions.BasePermission):
    """
    يمنع دور `viewer` من أي إجراء (POST/PATCH/PUT/DELETE).
    يُستخدم على endpoints التي تُعدِّل البيانات.

    GET requests تُسمح دائماً (صلاحيات الرؤية تُفحص بشكل منفصل).
    """
    message = 'حساب المُطّلِع لا يستطيع تنفيذ هذا الإجراء.'

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return getattr(request.user, 'role', None) != 'viewer'
