from rest_framework import permissions


class IsStatisticsAdmin(permissions.BasePermission):
    """السماح فقط لمدير قسم الإحصاء"""
    message = 'ليس لديك صلاحية للقيام بهذا الإجراء'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == 'statistics_admin'
        )


class IsPlanningSection(permissions.BasePermission):
    """السماح فقط لقسم التخطيط"""
    message = 'ليس لديك صلاحية للقيام بهذا الإجراء'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == 'planning_section'
        )


class IsPlanningSectionOrReadOnly(permissions.BasePermission):
    """السماح بالقراءة للجميع والتعديل لقسم التخطيط فقط"""
    message = 'ليس لديك صلاحية للقيام بهذا الإجراء'

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == 'planning_section'
        )


class FormTemplatePermission(permissions.BasePermission):
    """
    صلاحيات قوالب الاستمارات:
    - القراءة: جميع المستخدمين المصادق عليهم (حسب النطاق)
    - الإنشاء والتعديل: قسم التخطيط فقط
    - الاعتماد والرفض: مدير قسم الإحصاء فقط
    """
    message = 'ليس لديك صلاحية للقيام بهذا الإجراء'

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False

        # القراءة متاحة لجميع المستخدمين المصادق عليهم
        if request.method in permissions.SAFE_METHODS:
            return True

        # الإجراءات المخصصة - يتم التحقق من الصلاحيات في الإجراء نفسه
        if view.action in ('submit', 'approve', 'reject', 'active'):
            return True

        # الإنشاء والتعديل والحذف - قسم التخطيط فقط
        return request.user.role == 'planning_section'
