from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class SystemConfiguration(models.Model):
    """
    إعدادات النظام العامة — نموذج أحاد (Singleton).
    يحتوي على تفضيلات الإدارة التلقائية للأسابيع وقواعد الموعد النهائي.
    """

    class WeekDay(models.IntegerChoices):
        MONDAY = 0, 'الاثنين'
        TUESDAY = 1, 'الثلاثاء'
        WEDNESDAY = 2, 'الأربعاء'
        THURSDAY = 3, 'الخميس'
        FRIDAY = 4, 'الجمعة'
        SATURDAY = 5, 'السبت'
        SUNDAY = 6, 'الأحد'

    week_start_day = models.IntegerField(
        choices=WeekDay.choices,
        default=WeekDay.SATURDAY,
        verbose_name='يوم بداية الأسبوع',
        help_text='اليوم الذي يبدأ به الأسبوع رسمياً (يوم السبت هو الافتراضي)',
    )
    deadline_days_after_week_end = models.PositiveIntegerField(
        default=3,
        verbose_name='أيام الموعد النهائي بعد نهاية الأسبوع',
        help_text='عدد الأيام بعد نهاية الأسبوع حتى الموعد النهائي للتسليم',
    )
    deadline_hour = models.PositiveIntegerField(
        default=12,
        verbose_name='ساعة الموعد النهائي',
        help_text='الساعة من اليوم (0-23) للموعد النهائي. الافتراضي 12 ظهراً',
    )
    auto_create_enabled = models.BooleanField(
        default=True,
        verbose_name='تفعيل الإنشاء التلقائي للأسابيع',
        help_text='عند التفعيل، يُنشئ النظام الأسبوع الحالي تلقائياً في بدايته',
    )
    auto_close_previous = models.BooleanField(
        default=True,
        verbose_name='إغلاق الأسبوع السابق تلقائياً بعد انتهاء موعده',
        help_text='يُغلق الأسبوع السابق تلقائياً بعد مرور الموعد النهائي',
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name='آخر تحديث')

    class Meta:
        db_table = 'system_configuration'
        verbose_name = 'إعدادات النظام'
        verbose_name_plural = 'إعدادات النظام'

    def __str__(self):
        return 'إعدادات النظام'

    def clean(self):
        super().clean()
        if not 0 <= self.deadline_hour <= 23:
            raise ValidationError({
                'deadline_hour': 'الساعة يجب أن تكون بين 0 و 23'
            })

    def save(self, *args, **kwargs):
        """ضمان وجود سجل واحد فقط (Singleton pattern)"""
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """منع حذف السجل الأحادي"""
        pass

    @classmethod
    def load(cls):
        """
        إرجاع سجل الإعدادات (ينشئه بالقيم الافتراضية إن لم يكن موجوداً).
        هذا هو المدخل الموصى به للوصول إلى الإعدادات.
        """
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj


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
        RETURNED = 'returned', 'مُرجَع للتصحيح'
        LATE = 'late', 'متأخر'
        EXTENDED = 'extended', 'مُمدَّد'
        # مُرجَع من الإحصاء إلى قسم التخطيط لتصحيحه.
        # هذه الحالة قابلة للتعديل وإعادة الإرسال حتى بعد انتهاء موعد
        # الأسبوع — لأن التأخير سببه إجراء الإحصاء وليس تقصير القسم.
        RETURNED_BY_ADMIN = 'returned_by_admin', 'مُرجَع من الإحصاء'

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
        max_length=20, choices=Status.choices,
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
    # ─── مراجعة الإحصاء (admin review) ───
    # `admin_reviewed_at IS NULL` يعني «بانتظار مراجعة الإحصاء».
    # بمجرّد أن يُراجع أحد موظّفي الإحصاء (approve/edit/return)، يُقفَل
    # المنجز من أي مراجعة أخرى من قبل موظّفي الإحصاء الآخرين.
    admin_reviewed_at = models.DateTimeField(
        null=True, blank=True, verbose_name='تاريخ مراجعة الإحصاء',
    )
    admin_reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='admin_reviewed_submissions',
        verbose_name='مراجَع بواسطة (الإحصاء)',
    )
    admin_review_action = models.CharField(
        max_length=20, blank=True, default='',
        verbose_name='إجراء مراجعة الإحصاء',
        help_text='approved / edited / returned',
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
        """
        التحقق من قابلية التعديل.

        ملاحظة خاصة بحالة `RETURNED_BY_ADMIN`:
        - المنجز المُرجَع من قِبَل الإحصاء **قابل للتعديل دائماً**
          بغضّ النظر عن حالة الأسبوع أو الموعد النهائي.
        - السبب: التأخير سببه قرار الإحصاء بإرجاعه، وليس تقصير القسم،
          ومن غير العادل إقفاله أمام القسم فقط لأن الأسبوع انتهى.
        - هذا استثناء مقصود من قاعدة «المنجز قابل للتعديل فقط داخل الأسبوع».
        """
        # استثناء: المُرجَع من الإحصاء قابل للتعديل دائماً
        if self.status == self.Status.RETURNED_BY_ADMIN:
            return True

        editable_statuses = (
            self.Status.DRAFT,
            self.Status.RETURNED,
            self.Status.EXTENDED,
        )
        if self.status not in editable_statuses:
            return False
        period = self.weekly_period
        if period.status != WeeklyPeriod.Status.OPEN:
            return False
        now = timezone.now()
        if now < period.deadline:
            return True
        # تجاوز الموعد النهائي → التحقق من وجود تمديد ساري
        if extensions is not None:
            return any(ext.new_deadline > now for ext in extensions)
        return QismExtension.objects.filter(
            qism=self.qism,
            weekly_period=period,
            new_deadline__gt=now,
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
