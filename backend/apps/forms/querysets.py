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
        """تصفية القوالب حسب صلاحيات المستخدم"""
        if user.role == 'statistics_admin':
            return self.all()
        elif user.role == 'planning_section':
            # قسم التخطيط يرى قوالب أقسام مديريته فقط
            planning_unit = user.unit
            if planning_unit and planning_unit.parent:
                directorate = planning_unit.parent
                # الأقسام العادية التابعة لنفس المديرية/الدائرة
                return self.filter(
                    qism__parent=directorate,
                    qism__unit_type='qism',
                    qism__qism_role='regular',
                )
            return self.none()
        elif user.role == 'section_manager':
            # مدير القسم يرى قوالب قسمه فقط
            return self.filter(qism=user.unit)
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
