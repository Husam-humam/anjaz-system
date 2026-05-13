"""
صلاحيات تطبيق المنجزات — التحقق من صلاحيات الوصول الخاصة بالمنجزات.
"""
from rest_framework import permissions


class CanViewSubmission(permissions.BasePermission):
    """
    التحقق من صلاحية عرض المنجز حسب دور المستخدم:
    - statistics_admin: جميع المنجزات
    - planning_section: منجزات أقسام المديرية التابعة
    - section_manager: منجزات قسمه فقط
    """
    message = 'ليس لديك صلاحية لعرض هذا المنجز.'

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.role == 'statistics_admin':
            return True
        if user.role == 'planning_section':
            from .services import _planning_section_scope_qism_ids
            scope_ids = _planning_section_scope_qism_ids(user)
            if scope_ids is None:  # نطاق مركزي
                return True
            return obj.qism_id in scope_ids
        if user.role == 'section_manager':
            return obj.qism_id == user.unit_id
        return False


class CanEditSubmission(permissions.BasePermission):
    """التحقق من إمكانية تعديل المنجز — مدير القسم فقط ومنجز قسمه"""
    message = 'ليس لديك صلاحية لتعديل هذا المنجز.'

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.role != 'section_manager':
            return False
        return obj.qism_id == user.unit_id
