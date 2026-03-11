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


class IsStatisticsAdminOrReadOnly(permissions.BasePermission):
    """السماح بالقراءة للجميع والتعديل لمدير الإحصاء فقط"""
    message = 'ليس لديك صلاحية للقيام بهذا الإجراء'

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
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


class IsSectionManager(permissions.BasePermission):
    """السماح فقط لمدير القسم"""
    message = 'ليس لديك صلاحية للقيام بهذا الإجراء'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == 'section_manager'
        )


class IsStatisticsAdminOrPlanningSection(permissions.BasePermission):
    """السماح لمدير الإحصاء أو قسم التخطيط"""
    message = 'ليس لديك صلاحية للقيام بهذا الإجراء'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in ('statistics_admin', 'planning_section')
        )
