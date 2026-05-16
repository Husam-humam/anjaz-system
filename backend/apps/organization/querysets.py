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
        """
        الأقسام «العاديّة» — أي قسم ليس قسم تخطيط.
        قسم التخطيط = أي وحدة لها PlanningAssignment.
        """
        return self.filter(unit_type='qism').exclude(
            planning_assignment__isnull=False
        )

    def planning_qisms(self):
        """أقسام التخطيط — أي وحدة لها PlanningAssignment."""
        return self.filter(planning_assignment__isnull=False)

    def root_units(self):
        return self.filter(parent__isnull=True)

    def for_user_scope(self, user):
        """
        تصفية الوحدات حسب نطاق الرؤية للمستخدم.

        - statistics_admin: كل الوحدات
        - section_manager: وحدته فقط
        - planning_section / viewer: نطاق الرؤية (SupervisedUnit + ViewScope)
          مع تضمين الأجداد للعرض الهرمي (لقسم التخطيط فقط)
        """
        if user.role == 'statistics_admin':
            return self.all()
        if user.role == 'section_manager':
            return self.filter(pk=user.unit_id) if user.unit_id else self.none()
        if user.role in ('planning_section', 'viewer'):
            from apps.submissions.services import _user_view_scope_qism_ids
            scope_ids = _user_view_scope_qism_ids(user)
            if scope_ids is None:
                return self.all()  # legacy central planner
            if not scope_ids:
                return self.none()
            # للـ planner: نشمل أجداد الوحدات أيضاً (للعرض الهرمي)
            ids_to_show = set(scope_ids)
            if user.role == 'planning_section' and user.unit and user.unit.parent_id:
                # الأجداد الخاصّة بقسم التخطيط
                parent = user.unit.parent
                ids_to_show.update(
                    parent.get_ancestors(include_self=True).values_list('id', flat=True)
                )
            return self.filter(pk__in=ids_to_show)
        return self.none()


class OrganizationUnitManager(TreeManager.from_queryset(OrganizationUnitQuerySet)):
    """
    Manager مُدمَج: يجمع بين TreeManager (الذي يُوفّر MPTT operations مثل
    `rebuild()`, `disable_mptt_updates()`, ...) والـ queryset المخصّص
    لـ OrganizationUnit (active(), for_user_scope() ...).
    """
    pass
