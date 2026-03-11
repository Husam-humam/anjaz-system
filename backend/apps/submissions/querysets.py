"""
استعلامات مخصصة لتطبيق المنجزات.
"""
from django.db import models


class SubmissionQuerySet(models.QuerySet):
    """استعلامات مخصصة لنموذج المنجز الأسبوعي"""

    def for_period(self, period_id):
        """تصفية حسب الفترة الأسبوعية"""
        return self.filter(weekly_period_id=period_id)

    def for_qism(self, qism_id):
        """تصفية حسب القسم"""
        return self.filter(qism_id=qism_id)

    def by_status(self, status):
        """تصفية حسب الحالة"""
        return self.filter(status=status)

    def for_user_scope(self, user):
        """
        تصفية المنجزات حسب صلاحيات المستخدم:
        - statistics_admin: جميع المنجزات
        - planning_section: منجزات الأقسام التابعة لنفس المديرية/الدائرة
        - section_manager: منجزات قسمه فقط
        """
        if user.role == 'statistics_admin':
            return self.all()

        elif user.role == 'planning_section':
            # قسم التخطيط يرى منجزات الأقسام التابعة لنفس الأب (مديرية أو دائرة)
            parent_unit = user.unit.parent if user.unit else None
            if parent_unit:
                from apps.organization.models import OrganizationUnit, UnitType
                # الأقسام العادية التي تتبع نفس الأب
                sibling_qism_ids = OrganizationUnit.objects.filter(
                    parent=parent_unit,
                    unit_type=UnitType.QISM,
                    qism_role='regular',
                    is_active=True,
                ).values_list('id', flat=True)

                # أيضاً الأقسام التابعة لمديريات تحت نفس الدائرة
                if parent_unit.unit_type == UnitType.DAIRA:
                    mudiriya_ids = OrganizationUnit.objects.filter(
                        parent=parent_unit,
                        unit_type=UnitType.MUDIRIYA,
                        is_active=True,
                    ).values_list('id', flat=True)

                    nested_qism_ids = OrganizationUnit.objects.filter(
                        parent_id__in=mudiriya_ids,
                        unit_type=UnitType.QISM,
                        qism_role='regular',
                        is_active=True,
                    ).values_list('id', flat=True)

                    all_qism_ids = set(sibling_qism_ids) | set(nested_qism_ids)
                    return self.filter(qism_id__in=all_qism_ids)

                return self.filter(qism_id__in=sibling_qism_ids)
            return self.none()

        elif user.role == 'section_manager':
            # مدير القسم يرى منجزات قسمه فقط
            if user.unit:
                return self.filter(qism=user.unit)
            return self.none()

        return self.none()
