from django.db import models


class FormTemplateQuerySet(models.QuerySet):
    """مجموعة استعلامات مخصصة لقوالب الاستمارات"""

    def drafts(self):
        """القوالب ذات حالة المسودة"""
        return self.filter(status='draft')

    def pending_approval(self):
        """القوالب بانتظار الاعتماد"""
        return self.filter(status='pending_approval')

    def approved(self):
        """القوالب المعتمدة"""
        return self.filter(status='approved')

    def rejected(self):
        """القوالب المرفوضة"""
        return self.filter(status='rejected')

    def for_qism(self, qism_id):
        """القوالب الخاصة بقسم معين"""
        return self.filter(qism_id=qism_id)

    def for_user_scope(self, user):
        """
        تصفية القوالب حسب نطاق الرؤية للمستخدم (view scope).
        يستخدم `_user_view_scope_qism_ids` الموحَّد — يدعم planner و viewer
        و section_manager و statistics_admin.
        """
        if user.role == 'statistics_admin':
            return self.all()
        if user.role == 'section_manager':
            return self.filter(qism=user.unit)
        if user.role in ('planning_section', 'viewer'):
            from apps.submissions.services import _user_view_scope_qism_ids
            scope_ids = _user_view_scope_qism_ids(user)
            if scope_ids is None:
                return self.all()  # legacy central planner
            if not scope_ids:
                return self.none()
            return self.filter(qism_id__in=scope_ids)
        return self.none()

    def active_for_qism(self, qism_id, year=None, week_number=None):
        """
        الحصول على القالب النشط لقسم معين.
        إذا تم توفير السنة ورقم الأسبوع، يتم إرجاع القالب الساري في ذلك الأسبوع.
        """
        qs = self.filter(
            qism_id=qism_id,
            status='approved',
        ).exclude(
            effective_from_week__isnull=True
        ).exclude(
            effective_from_year__isnull=True
        )

        if year is not None and week_number is not None:
            # القالب الذي يسري قبل أو في الأسبوع المحدد
            qs = qs.filter(
                models.Q(effective_from_year__lt=year) |
                models.Q(
                    effective_from_year=year,
                    effective_from_week__lte=week_number,
                )
            )

        # ترتيب تنازلي للحصول على آخر قالب ساري
        return qs.order_by('-effective_from_year', '-effective_from_week')
