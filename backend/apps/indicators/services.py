from django.core.exceptions import ValidationError
from django.db import transaction

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
        return indicator

    @staticmethod
    def update_indicator(indicator, data):
        """تحديث مؤشر"""
        for key, value in data.items():
            setattr(indicator, key, value)
        indicator.full_clean()
        indicator.save()
        return indicator

    @staticmethod
    @transaction.atomic
    def deactivate_indicator(indicator):
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
