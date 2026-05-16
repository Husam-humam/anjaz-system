from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class FormTemplate(models.Model):
    """قالب الاستمارة"""

    class Status(models.TextChoices):
        DRAFT = 'draft', 'مسودة'
        PENDING_APPROVAL = 'pending_approval', 'بانتظار الاعتماد'
        APPROVED = 'approved', 'معتمد'
        SUPERSEDED = 'superseded', 'مُستبدَل'
        REJECTED = 'rejected', 'مرفوض'

    qism = models.ForeignKey(
        'organization.OrganizationUnit', on_delete=models.PROTECT,
        related_name='form_templates',
        verbose_name='القسم'
    )
    version = models.PositiveIntegerField(verbose_name='رقم الإصدار')
    status = models.CharField(
        max_length=20, choices=Status.choices,
        default=Status.DRAFT, verbose_name='الحالة'
    )
    effective_from_week = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='يسري من الأسبوع'
    )
    effective_from_year = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='يسري من السنة'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='created_templates',
        verbose_name='أنشئ بواسطة'
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='approved_templates',
        verbose_name='اعتمد بواسطة'
    )
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='rejected_templates',
        verbose_name='رفض بواسطة'
    )
    rejection_reason = models.TextField(blank=True, default='', verbose_name='سبب الرفض')
    notes = models.TextField(blank=True, default='', verbose_name='ملاحظات')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='تاريخ الاعتماد')

    class Meta:
        db_table = 'form_templates'
        verbose_name = 'قالب استمارة'
        verbose_name_plural = 'قوالب الاستمارات'
        unique_together = ('qism', 'version')
        indexes = [
            models.Index(fields=['qism', 'status'], name='idx_form_qism_status'),
            models.Index(fields=['status'], name='idx_form_status'),
        ]
        constraints = [
            # طبقة دفاع على مستوى قاعدة البيانات: يستحيل وجود قالبَين معتمدَين
            # لنفس القسم يبدآن في نفس الأسبوع والسنة. يُفرَض مع منطق
            # approve_template الذي يُستبدِل الأقدم قبل اعتماد الجديد.
            models.UniqueConstraint(
                fields=['qism', 'effective_from_year', 'effective_from_week'],
                condition=Q(status='approved'),
                name='uniq_approved_effective_per_qism',
            ),
        ]

    def __str__(self):
        return f'{self.qism.name} - الإصدار {self.version}'

    def clean(self):
        super().clean()
        # القالب يجب أن يكون لقسم مُسنَد للتقديم (له SupervisedUnit)
        is_planning = hasattr(self.qism, 'planning_assignment')
        is_supervised = hasattr(self.qism, 'supervisor_link')
        if self.qism.unit_type != 'qism' or is_planning or not is_supervised:
            raise ValidationError({
                'qism': 'يجب أن تكون الاستمارة مرتبطة بقسم عادي فقط'
            })


class FormTemplateItem(models.Model):
    """بنود قالب الاستمارة"""
    form_template = models.ForeignKey(
        FormTemplate, on_delete=models.CASCADE,
        related_name='items', verbose_name='القالب'
    )
    indicator = models.ForeignKey(
        'indicators.Indicator', on_delete=models.CASCADE,
        related_name='form_items', verbose_name='المؤشر'
    )
    is_mandatory = models.BooleanField(default=False, verbose_name='إلزامي')
    display_order = models.PositiveIntegerField(default=0, verbose_name='ترتيب العرض')

    class Meta:
        db_table = 'form_template_items'
        verbose_name = 'بند استمارة'
        verbose_name_plural = 'بنود الاستمارة'
        unique_together = ('form_template', 'indicator')
        ordering = ['display_order']

    def __str__(self):
        return f'{self.form_template} - {self.indicator.name}'
