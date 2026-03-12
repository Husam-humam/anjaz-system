from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models


class Target(models.Model):
    """المستهدفات السنوية"""
    qism = models.ForeignKey(
        'organization.OrganizationUnit', on_delete=models.CASCADE,
        related_name='targets', verbose_name='القسم'
    )
    indicator = models.ForeignKey(
        'indicators.Indicator', on_delete=models.CASCADE,
        related_name='targets', verbose_name='المؤشر'
    )
    year = models.PositiveIntegerField(verbose_name='السنة')
    target_value = models.FloatField(verbose_name='القيمة المستهدفة')
    set_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='set_targets',
        verbose_name='حُدد بواسطة'
    )
    notes = models.TextField(blank=True, default='', verbose_name='ملاحظات')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')

    class Meta:
        db_table = 'targets'
        verbose_name = 'مستهدف'
        verbose_name_plural = 'المستهدفات'
        unique_together = ('qism', 'indicator', 'year')
        indexes = [
            models.Index(fields=['qism', 'indicator', 'year'], name='idx_target_qism_ind_year'),
            models.Index(fields=['year'], name='idx_target_year'),
        ]

    def __str__(self):
        return f'{self.qism.name} - {self.indicator.name} ({self.year})'

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.target_value is not None and self.target_value <= 0:
            raise ValidationError({
                'target_value': 'القيمة المستهدفة يجب أن تكون أكبر من صفر'
            })
        if hasattr(self, 'indicator') and self.indicator_id:
            try:
                if self.indicator.unit_type == 'text':
                    raise ValidationError({
                        'indicator': 'لا يمكن تحديد مستهدف لمؤشر نصي'
                    })
            except (ValueError, ObjectDoesNotExist):
                pass  # indicator not yet loaded
