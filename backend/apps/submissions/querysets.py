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
        - planning_section: منجزات الأقسام التابعة لنفس المديرية/الدائرة،
          أو جميع المنجزات إذا كان قسم التخطيط مركزياً (بدون أب)
        - section_manager: منجزات قسمه فقط
        """
        if user.role == 'statistics_admin':
            return self.all()

        if user.role == 'planning_section':
            from .services import _planning_section_scope_qism_ids
            scope_ids = _planning_section_scope_qism_ids(user)
            if scope_ids is None:  # نطاق مركزي
                return self.all()
            if not scope_ids:
                return self.none()
            return self.filter(qism_id__in=scope_ids)

        if user.role == 'section_manager':
            if user.unit:
                return self.filter(qism=user.unit)
            return self.none()

        return self.none()
