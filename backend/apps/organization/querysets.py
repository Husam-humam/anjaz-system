from django.db import models
from mptt.managers import TreeManager


class OrganizationUnitQuerySet(models.QuerySet):

    def active(self):
        return self.filter(is_active=True)

    def dairas(self):
        return self.filter(unit_type='daira')

    def mudiriyas(self):
        return self.filter(unit_type='mudiriya')

    def qisms(self):
        return self.filter(unit_type='qism')

    def regular_qisms(self):
        return self.filter(unit_type='qism', qism_role='regular')

    def planning_qisms(self):
        return self.filter(unit_type='qism', qism_role='planning')

    def statistics_qisms(self):
        return self.filter(unit_type='qism', qism_role='statistics')

    def root_units(self):
        return self.filter(parent__isnull=True)

    def for_user_scope(self, user):
        """تصفية الوحدات حسب صلاحيات المستخدم"""
        if user.role == 'statistics_admin':
            return self.all()
        elif user.role == 'planning_section':
            # قسم التخطيط يرى وحدات مديريته فقط
            parent = user.unit.parent
            if parent:
                return self.filter(
                    models.Q(pk=parent.pk) |
                    models.Q(parent=parent) |
                    models.Q(parent__parent=parent)
                )
            return self.filter(pk=user.unit.pk)
        else:
            # مدير القسم يرى قسمه فقط
            return self.filter(pk=user.unit.pk)


class OrganizationUnitManager(TreeManager.from_queryset(OrganizationUnitQuerySet)):
    """
    Manager مُدمَج: يجمع بين TreeManager (الذي يُوفّر MPTT operations مثل
    `rebuild()`, `disable_mptt_updates()`, ...) والـ queryset المخصّص
    لـ OrganizationUnit (active(), for_user_scope() ...).
    """
    pass
