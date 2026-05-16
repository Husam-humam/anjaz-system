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
        تصفية المنجزات حسب نطاق **الرؤية** للمستخدم (read scope).

        ملاحظة: هذا مختلف عن نطاق **الإدارة** (الذي يُحدّد مَن يستطيع
        اعتماد/رفض/تعديل). الرؤية أوسع: تشمل المُدار + ViewScope additions.

        - statistics_admin: جميع المنجزات (نطاق كامل)
        - planning_section: المُدار + ViewScope (إن وُجد)
        - viewer: ViewScope فقط
        - section_manager: قسمه فقط
        """
        from .services import _user_view_scope_qism_ids

        if user.role == 'statistics_admin':
            return self.all()

        scope_ids = _user_view_scope_qism_ids(user)
        # None = نطاق كامل (legacy central planner)
        if scope_ids is None:
            return self.all()
        if not scope_ids:
            return self.none()
        return self.filter(qism_id__in=scope_ids)
