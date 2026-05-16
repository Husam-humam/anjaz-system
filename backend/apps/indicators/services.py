from django.core.exceptions import ValidationError
from django.db import transaction

from apps.audit.models import AuditLog
from apps.audit.services import AuditService

from .models import Indicator, IndicatorCategory


class IndicatorService:
    """خدمة إدارة المؤشرات"""

    @staticmethod
    def create_indicator(data, created_by):
        """إنشاء مؤشر جديد"""
        indicator = Indicator(**data)
        indicator.created_by = created_by
        indicator.full_clean()
        indicator.save()

        # سجل التدقيق — قاعدة عمل #14
        AuditService.log(
            action_type=AuditLog.ActionType.INDICATOR_CREATED,
            actor=created_by,
            target=indicator,
            qism=None,
            metadata={
                'name': indicator.name,
                'unit_type': indicator.unit_type,
                'accumulation_type': indicator.accumulation_type,
            },
        )
        return indicator

    # الحقول الحسّاسة التي تُغيِّر سلوك aggregation التاريخي للمؤشر.
    # تغييرها بعد وجود إجابات يكسر التقارير السابقة.
    LOCKED_FIELDS_AFTER_ANSWERS = ('unit_type', 'accumulation_type')

    @staticmethod
    def update_indicator(indicator, data, actor=None):
        """
        تحديث مؤشر.
        - `unit_type` و `accumulation_type` مقفلان إذا وُجدت إجابات تستند للمؤشر،
          لأن تغييرهما يُبطل صحّة التقارير التاريخية (مثلاً sum → last_value).
        """
        sensitive_changed = any(
            field in data
            and getattr(indicator, field) != data[field]
            for field in IndicatorService.LOCKED_FIELDS_AFTER_ANSWERS
        )
        if sensitive_changed:
            from apps.submissions.models import SubmissionAnswer
            has_answers = SubmissionAnswer.objects.filter(
                form_item__indicator=indicator
            ).exists()
            if has_answers:
                raise ValidationError(
                    'لا يمكن تغيير نوع المؤشر أو طريقة تراكمه بعد وجود '
                    'إجابات سابقة لأنه يُبطل صحّة التقارير التاريخية.'
                )

        # نلتقط الحقول المُتغيّرة قبل التحديث
        changes = {}
        for key, value in data.items():
            old = getattr(indicator, key, None)
            old_repr = old.pk if hasattr(old, 'pk') else old
            new_repr = value.pk if hasattr(value, 'pk') else value
            if old_repr != new_repr:
                changes[key] = {'old': old_repr, 'new': new_repr}
            setattr(indicator, key, value)
        indicator.full_clean()
        indicator.save()

        if actor is not None and changes:
            AuditService.log(
                action_type=AuditLog.ActionType.INDICATOR_UPDATED,
                actor=actor,
                target=indicator,
                qism=None,
                metadata={'name': indicator.name, 'changes': changes},
            )
        return indicator

    @staticmethod
    @transaction.atomic
    def deactivate_indicator(indicator, actor=None):
        """تعطيل مؤشر (حذف ناعم)"""
        # التحقق من عدم استخدام المؤشر في استمارات نشطة
        from apps.forms.models import FormTemplateItem
        active_usage = FormTemplateItem.objects.filter(
            indicator=indicator,
            form_template__status__in=['approved', 'pending'],
        ).exists()
        if active_usage:
            raise ValidationError(
                "لا يمكن تعطيل مؤشر مستخدم في استمارات نشطة أو معلقة"
            )
        indicator.is_active = False
        indicator.save(update_fields=['is_active'])

        if actor is not None:
            AuditService.log(
                action_type=AuditLog.ActionType.INDICATOR_DEACTIVATED,
                actor=actor,
                target=indicator,
                qism=None,
                metadata={'name': indicator.name},
            )
        return indicator


class IndicatorCategoryService:
    """خدمة إدارة تصنيفات المؤشرات"""

    @staticmethod
    def create_category(data):
        """إنشاء تصنيف جديد"""
        category = IndicatorCategory(**data)
        category.full_clean()
        category.save()
        return category

    @staticmethod
    def update_category(category, data):
        """تحديث تصنيف"""
        for key, value in data.items():
            setattr(category, key, value)
        category.full_clean()
        category.save()
        return category

    @staticmethod
    def deactivate_category(category):
        """تعطيل تصنيف (حذف ناعم)"""
        # التحقق من عدم وجود مؤشرات نشطة مرتبطة بالتصنيف
        active_indicators = category.indicators.filter(is_active=True)
        if active_indicators.exists():
            raise ValidationError(
                'لا يمكن تعطيل تصنيف يحتوي على مؤشرات نشطة'
            )
        category.is_active = False
        category.save(update_fields=['is_active'])
        return category
