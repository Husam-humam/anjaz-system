"""
نموذج المستهدفات — يدعم المستهدفات الهرمية على مستويات مختلفة:
- مؤسسي (scope_unit=None): مستهدف للمؤسسة ككل
- دائرة: مستهدف لدائرة معيّنة (يُجمّع من أقسامها)
- مديرية: مستهدف لمديرية معيّنة (يُجمّع من أقسامها)
- قسم: مستهدف لقسم واحد محدّد
"""
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models


class Target(models.Model):
    """
    المستهدفات السنوية الهرمية.

    scope_unit يُحدّد مستوى المستهدف:
    - None: المؤسسة كلها
    - daira: دائرة
    - mudiriya: مديرية
    - qism: قسم منفرد (للحالات الخاصة)

    القاعدة الذهبية: المؤشرات من نوع "آخر قيمة" (last_value) تُسمح فقط على
    مستوى القسم، لأن "آخر قيمة" ليس لها تجميع هرمي واضح.
    """

    # السماح بـ null للدلالة على مستهدف على مستوى المؤسسة كاملة
    scope_unit = models.ForeignKey(
        'organization.OrganizationUnit',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='targets',
        verbose_name='نطاق المستهدف',
        help_text=(
            'الوحدة التنظيمية التي يخصّها المستهدف (دائرة/مديرية/قسم). '
            'اترك فارغاً لإنشاء مستهدف على مستوى المؤسسة كاملة.'
        ),
    )
    indicator = models.ForeignKey(
        'indicators.Indicator', on_delete=models.CASCADE,
        related_name='targets', verbose_name='المؤشر'
    )
    year = models.PositiveIntegerField(verbose_name='السنة')
    target_value = models.FloatField(verbose_name='القيمة المستهدفة')
    set_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='set_targets',
        verbose_name='حُدد بواسطة'
    )
    notes = models.TextField(blank=True, default='', verbose_name='ملاحظات')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')

    class Meta:
        db_table = 'targets'
        verbose_name = 'مستهدف'
        verbose_name_plural = 'المستهدفات'
        # قيد فريد: لا يمكن وجود مستهدفين بنفس النطاق والمؤشر والسنة
        # PostgreSQL يعامل NULL كقيم مختلفة (null != null)،
        # لذا قد يُسمح بتكرار مستهدفات على مستوى المؤسسة — نعالج ذلك يدوياً في clean()
        unique_together = ('scope_unit', 'indicator', 'year')
        indexes = [
            models.Index(fields=['scope_unit', 'indicator', 'year'], name='idx_target_scope_ind_year'),
            models.Index(fields=['year'], name='idx_target_year'),
            models.Index(fields=['indicator', 'year'], name='idx_target_indicator_year'),
        ]

    def __str__(self):
        scope_label = self.scope_unit.name if self.scope_unit_id else 'المؤسسة كاملة'
        return f'{scope_label} - {self.indicator.name} ({self.year})'

    @property
    def scope_level(self):
        """مستوى النطاق كنصّ: institution / daira / mudiriya / qism"""
        if self.scope_unit_id is None:
            return 'institution'
        return self.scope_unit.unit_type

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()

        # 1) قيمة المستهدف يجب أن تكون موجبة
        if self.target_value is not None and self.target_value <= 0:
            raise ValidationError({
                'target_value': 'القيمة المستهدفة يجب أن تكون أكبر من صفر'
            })

        # 2) فحص المؤشر
        if self.indicator_id:
            try:
                indicator = self.indicator
            except ObjectDoesNotExist:
                indicator = None

            if indicator:
                # المؤشرات النصية لا يمكن أن يكون لها مستهدف
                if indicator.unit_type == 'text':
                    raise ValidationError({
                        'indicator': 'لا يمكن تحديد مستهدف لمؤشر نصي'
                    })

                # المؤشرات من نوع "آخر قيمة" يُسمح بها فقط على مستوى القسم
                if indicator.accumulation_type == 'last_value':
                    scope_level = self.scope_level
                    if scope_level != 'qism':
                        raise ValidationError({
                            'indicator': (
                                'المؤشرات من نوع "آخر قيمة" تُسمح لها مستهدفات '
                                'على مستوى القسم فقط (وليس الدائرة أو المديرية أو المؤسسة)، '
                                'لأن "آخر قيمة" ليس لها معنى تجميع هرمي.'
                            )
                        })

        # 3) النطاق يجب أن يكون من الأنواع المسموحة
        if self.scope_unit_id:
            try:
                scope = self.scope_unit
            except ObjectDoesNotExist:
                scope = None

            if scope:
                if scope.unit_type not in ('daira', 'mudiriya', 'qism'):
                    raise ValidationError({
                        'scope_unit': (
                            'نطاق المستهدف يجب أن يكون دائرة أو مديرية أو قسم'
                        )
                    })
                # القسم يجب أن يكون مُسنَداً للتقديم (له SupervisedUnit)
                # — أقسام التخطيط (PlanningAssignment) لا تأخذ مستهدفات
                if scope.unit_type == 'qism':
                    is_planning = hasattr(scope, 'planning_assignment')
                    has_supervisor = hasattr(scope, 'supervisor_link')
                    if is_planning or not has_supervisor:
                        raise ValidationError({
                            'scope_unit': (
                                'مستهدفات الأقسام تكون فقط للأقسام المُسنَدة للتقديم'
                            )
                        })

        # 4) منع التكرار على مستوى المؤسسة (null scope) — PostgreSQL لا يفرض ذلك
        if self.scope_unit_id is None and self.indicator_id and self.year:
            duplicate = Target.objects.filter(
                scope_unit__isnull=True,
                indicator_id=self.indicator_id,
                year=self.year,
            )
            if self.pk:
                duplicate = duplicate.exclude(pk=self.pk)
            if duplicate.exists():
                raise ValidationError(
                    'يوجد مسبقاً مستهدف على مستوى المؤسسة لهذا المؤشر في هذه السنة'
                )
