from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class WeeklyPeriod(models.Model):
    """الفترة الأسبوعية"""

    class Status(models.TextChoices):
        OPEN = 'open', 'مفتوح'
        CLOSED = 'closed', 'مغلق'

    year = models.PositiveIntegerField(verbose_name='السنة')
    week_number = models.PositiveIntegerField(verbose_name='رقم الأسبوع')
    start_date = models.DateField(verbose_name='تاريخ البداية')
    end_date = models.DateField(verbose_name='تاريخ النهاية')
    deadline = models.DateTimeField(verbose_name='الموعد النهائي')
    status = models.CharField(
        max_length=10, choices=Status.choices,
        default=Status.OPEN, verbose_name='الحالة'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='created_periods',
        verbose_name='أنشئ بواسطة'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')

    class Meta:
        db_table = 'weekly_periods'
        verbose_name = 'فترة أسبوعية'
        verbose_name_plural = 'الفترات الأسبوعية'
        unique_together = ('year', 'week_number')
        ordering = ['-year', '-week_number']
        indexes = [
            models.Index(fields=['year', 'week_number'], name='idx_period_year_week'),
            models.Index(fields=['status'], name='idx_period_status'),
        ]

    def __str__(self):
        return f'الأسبوع {self.week_number} / {self.year}'

    def clean(self):
        super().clean()
        if self.week_number < 1 or self.week_number > 53:
            raise ValidationError({
                'week_number': 'رقم الأسبوع يجب أن يكون بين 1 و 53'
            })
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError({
                'end_date': 'تاريخ النهاية يجب أن يكون بعد تاريخ البداية'
            })

    @property
    def is_deadline_passed(self):
        return timezone.now() > self.deadline


class WeeklySubmission(models.Model):
    """المنجز الأسبوعي"""

    class Status(models.TextChoices):
        DRAFT = 'draft', 'مسودة'
        SUBMITTED = 'submitted', 'مُرسل'
        APPROVED = 'approved', 'معتمد'
        LATE = 'late', 'متأخر'
        EXTENDED = 'extended', 'مُمدَّد'

    qism = models.ForeignKey(
        'organization.OrganizationUnit', on_delete=models.CASCADE,
        related_name='submissions', verbose_name='القسم'
    )
    weekly_period = models.ForeignKey(
        WeeklyPeriod, on_delete=models.CASCADE,
        related_name='submissions', verbose_name='الفترة الأسبوعية'
    )
    form_template = models.ForeignKey(
        'forms.FormTemplate', on_delete=models.CASCADE,
        related_name='submissions', verbose_name='قالب الاستمارة'
    )
    status = models.CharField(
        max_length=15, choices=Status.choices,
        default=Status.DRAFT, verbose_name='الحالة'
    )
    submitted_at = models.DateTimeField(
        null=True, blank=True, verbose_name='تاريخ الإرسال'
    )
    planning_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='approved_submissions',
        verbose_name='اعتمد بواسطة (التخطيط)'
    )
    planning_approved_at = models.DateTimeField(
        null=True, blank=True, verbose_name='تاريخ الاعتماد'
    )
    notes = models.TextField(blank=True, default='', verbose_name='ملاحظات')

    class Meta:
        db_table = 'weekly_submissions'
        verbose_name = 'منجز أسبوعي'
        verbose_name_plural = 'المنجزات الأسبوعية'
        unique_together = ('qism', 'weekly_period')
        indexes = [
            models.Index(fields=['qism', 'weekly_period'], name='idx_sub_qism_period'),
            models.Index(fields=['weekly_period', 'status'], name='idx_sub_period_status'),
            models.Index(fields=['status'], name='idx_sub_status'),
        ]

    def __str__(self):
        return f'{self.qism.name} - {self.weekly_period}'

    def is_editable(self, extensions=None):
        """التحقق من قابلية التعديل"""
        if self.status not in ('draft', 'returned', 'extended'):
            return False
        period = self.weekly_period
        if period.status != 'open':
            return False
        now = timezone.now()
        if now <= period.deadline:
            return True
        # Check extensions
        if extensions is not None:
            return any(ext.new_deadline >= now for ext in extensions)
        return QismExtension.objects.filter(
            qism=self.qism,
            weekly_period=period,
            new_deadline__gte=now,
        ).exists()


class SubmissionAnswer(models.Model):
    """إجابات المنجز"""

    class QualitativeStatus(models.TextChoices):
        NONE = 'none', 'لا يوجد'
        PENDING_PLANNING = 'pending_planning', 'بانتظار اعتماد التخطيط'
        PENDING_STATISTICS = 'pending_statistics', 'بانتظار اعتماد الإحصاء'
        APPROVED = 'approved', 'معتمد'
        REJECTED = 'rejected', 'مرفوض'

    submission = models.ForeignKey(
        WeeklySubmission, on_delete=models.CASCADE,
        related_name='answers', verbose_name='المنجز'
    )
    form_item = models.ForeignKey(
        'forms.FormTemplateItem', on_delete=models.CASCADE,
        related_name='answers', verbose_name='بند الاستمارة'
    )
    numeric_value = models.FloatField(
        null=True, blank=True, verbose_name='القيمة الرقمية'
    )
    text_value = models.TextField(
        blank=True, default='', verbose_name='القيمة النصية'
    )
    is_qualitative = models.BooleanField(
        default=False, verbose_name='منجز نوعي'
    )
    qualitative_details = models.TextField(
        blank=True, default='', verbose_name='تفاصيل المنجز النوعي'
    )
    qualitative_status = models.CharField(
        max_length=25, choices=QualitativeStatus.choices,
        default=QualitativeStatus.NONE,
        verbose_name='حالة المنجز النوعي'
    )
    qualitative_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='approved_qualitatives',
        verbose_name='اعتمد نوعياً بواسطة'
    )
    qualitative_approved_at = models.DateTimeField(
        null=True, blank=True, verbose_name='تاريخ اعتماد النوعي'
    )
    rejection_reason = models.TextField(
        blank=True, default='', verbose_name='سبب الرفض'
    )

    class Meta:
        db_table = 'submission_answers'
        verbose_name = 'إجابة منجز'
        verbose_name_plural = 'إجابات المنجزات'
        unique_together = ('submission', 'form_item')
        indexes = [
            models.Index(fields=['submission', 'form_item'], name='idx_answer_sub_item'),
        ]

    def __str__(self):
        return f'{self.submission} - {self.form_item.indicator.name}'

    def clean(self):
        super().clean()
        # التحقق من تفاصيل المنجز النوعي
        if self.is_qualitative and not self.qualitative_details.strip():
            raise ValidationError({
                'qualitative_details': 'يجب إدخال تفاصيل المنجز النوعي'
            })
        # التحقق من قيمة النسبة المئوية
        if (self.form_item.indicator.unit_type == 'percentage'
                and self.numeric_value is not None
                and (self.numeric_value < 0 or self.numeric_value > 100)):
            raise ValidationError({
                'numeric_value': 'النسبة المئوية يجب أن تكون بين 0 و 100'
            })


class QismExtension(models.Model):
    """تمديد الموعد للقسم"""
    qism = models.ForeignKey(
        'organization.OrganizationUnit', on_delete=models.CASCADE,
        related_name='extensions', verbose_name='القسم'
    )
    weekly_period = models.ForeignKey(
        WeeklyPeriod, on_delete=models.CASCADE,
        related_name='extensions', verbose_name='الفترة الأسبوعية'
    )
    new_deadline = models.DateTimeField(verbose_name='الموعد الجديد')
    reason = models.TextField(verbose_name='السبب')
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='granted_extensions',
        verbose_name='منح بواسطة'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')

    class Meta:
        db_table = 'qism_extensions'
        verbose_name = 'تمديد موعد'
        verbose_name_plural = 'تمديدات المواعيد'
        unique_together = ('qism', 'weekly_period')

    def __str__(self):
        return f'تمديد {self.qism.name} - {self.weekly_period}'

    def clean(self):
        super().clean()
        if self.new_deadline and self.weekly_period_id:
            try:
                if self.new_deadline <= self.weekly_period.deadline:
                    raise ValidationError({
                        'new_deadline': 'الموعد الجديد يجب أن يكون بعد الموعد الأصلي'
                    })
            except WeeklyPeriod.DoesNotExist:
                pass
