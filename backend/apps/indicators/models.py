from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class IndicatorCategory(models.Model):
    """تصنيف المؤشرات"""
    name = models.CharField(
        max_length=100, unique=True,
        verbose_name='اسم التصنيف'
    )
    is_active = models.BooleanField(default=True, verbose_name='نشط')

    class Meta:
        db_table = 'indicator_categories'
        verbose_name = 'تصنيف مؤشر'
        verbose_name_plural = 'تصنيفات المؤشرات'

    def __str__(self):
        return self.name


class Indicator(models.Model):
    """المؤشرات"""

    class UnitType(models.TextChoices):
        NUMBER = 'number', 'رقم'
        PERCENTAGE = 'percentage', 'نسبة مئوية'
        TEXT = 'text', 'نص'
        HOURS = 'hours', 'ساعات'
        DAYS = 'days', 'أيام'

    class AccumulationType(models.TextChoices):
        SUM = 'sum', 'مجموع'
        AVERAGE = 'average', 'متوسط'
        LAST_VALUE = 'last_value', 'آخر قيمة'

    name = models.CharField(max_length=300, verbose_name='اسم المؤشر')
    description = models.TextField(blank=True, default='', verbose_name='الوصف')
    unit_type = models.CharField(
        max_length=20, choices=UnitType.choices,
        verbose_name='وحدة القياس'
    )
    unit_label = models.CharField(
        max_length=50, blank=True, default='',
        verbose_name='تسمية الوحدة'
    )
    accumulation_type = models.CharField(
        max_length=20, choices=AccumulationType.choices,
        verbose_name='طريقة التجميع'
    )
    category = models.ForeignKey(
        IndicatorCategory, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='indicators',
        verbose_name='التصنيف'
    )
    is_active = models.BooleanField(default=True, verbose_name='نشط')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='created_indicators',
        verbose_name='أنشئ بواسطة'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')

    class Meta:
        db_table = 'indicators'
        verbose_name = 'مؤشر'
        verbose_name_plural = 'المؤشرات'

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        # المؤشرات النصية يجب أن تستخدم "آخر قيمة" فقط
        if self.unit_type == self.UnitType.TEXT and self.accumulation_type != self.AccumulationType.LAST_VALUE:
            raise ValidationError({
                'accumulation_type': 'المؤشرات النصية يجب أن تستخدم طريقة تجميع "آخر قيمة" فقط'
            })

    @property
    def is_numeric(self):
        return self.unit_type != self.UnitType.TEXT
