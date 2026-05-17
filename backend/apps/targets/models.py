"""
نموذج المستهدفات — يدعم المستهدفات المركّبة الهرميّة على مستويات مختلفة:

نموذج المستهدف:
- اسم وصفي (مثل «إعداد التقارير»)
- مجموعة مؤشّرات تُكوّن المستهدف (M2M، مكوّن واحد أو أكثر)
- قيمة مستهدفة (الإجمالي عبر كل المكوّنات بالجمع البسيط)
- نطاق هرمي: مؤسسي / دائرة / مديرية / قسم

قواعد جوهريّة:
- كل المكوّنات يجب أن تكون بنفس `unit_type` (منع صارم للخلط).
- المؤشرات النصّيّة لا تُقبَل (لا معنى لـ «مستهدف نصّ»).
- مؤشّر «آخر قيمة» يُقبَل فقط على مستوى القسم.
"""
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models


class Target(models.Model):
    """
    المستهدفات السنوية المركّبة الهرميّة.

    scope_unit يُحدّد مستوى المستهدف:
    - None: المؤسسة كلها
    - daira: دائرة
    - mudiriya: مديرية
    - qism: قسم منفرد

    `indicators` (M2M) يحوي مكوّن واحد على الأقلّ. عند حسّاب القيمة الفعليّة،
    نجمع قيم كل المكوّنات (جمع بسيط، بدون أوزان).
    """

    name = models.CharField(
        max_length=200,
        verbose_name='اسم المستهدف',
        help_text=(
            'وصف مختصر للمستهدف (مثل «إعداد التقارير»). يُعرض في التقارير '
            'كعنوان رئيسي مع تفصيل المكوّنات تحته.'
        ),
    )
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
    # M2M بدل FK واحد — مستهدف واحد يمكن أن يتركّب من عدّة مؤشّرات.
    # كلها يجب أن تكون بنفس unit_type (يُفحَص في الـ service لأن M2M لا يصحّ
    # التحقّق منه في model.clean قبل الحفظ).
    indicators = models.ManyToManyField(
        'indicators.Indicator',
        related_name='targets',
        verbose_name='المؤشّرات المُكوِّنة',
        help_text=(
            'المؤشّر/المؤشّرات التي يتركّب منها المستهدف. كل المكوّنات '
            'يجب أن تكون بنفس نوع الوحدة (عدد، نسبة، إلخ).'
        ),
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
        # ملاحظة: لم نُعد قيد unique_together على (scope_unit, indicator, year)
        # لأن indicator أصبح M2M. التفرّد الآن على مستوى الاسم داخل نفس النطاق
        # والسنة (نُفحَص في الـ service).
        indexes = [
            models.Index(fields=['scope_unit', 'year'], name='idx_target_scope_year'),
            models.Index(fields=['year'], name='idx_target_year'),
        ]

    def __str__(self):
        scope_label = self.scope_unit.name if self.scope_unit_id else 'المؤسسة كاملة'
        return f'{scope_label} - {self.name} ({self.year})'

    @property
    def scope_level(self):
        """مستوى النطاق كنصّ: institution / daira / mudiriya / qism"""
        if self.scope_unit_id is None:
            return 'institution'
        return self.scope_unit.unit_type

    def clean(self):
        super().clean()

        # 1) الاسم مطلوب وغير فارغ
        if not (self.name or '').strip():
            raise ValidationError({'name': 'اسم المستهدف مطلوب'})

        # 2) قيمة المستهدف يجب أن تكون موجبة
        if self.target_value is not None and self.target_value <= 0:
            raise ValidationError({
                'target_value': 'القيمة المستهدفة يجب أن تكون أكبر من صفر'
            })

        # 3) فحص النطاق
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
                if scope.unit_type == 'qism':
                    is_planning = hasattr(scope, 'planning_assignment')
                    has_supervisor = hasattr(scope, 'supervisor_link')
                    if is_planning or not has_supervisor:
                        raise ValidationError({
                            'scope_unit': (
                                'مستهدفات الأقسام تكون فقط للأقسام المُسنَدة للتقديم'
                            )
                        })

    def validate_components(self, indicators):
        """
        يُفحَص بعد ربط المؤشّرات (M2M لا يَصحّ في clean قبل الحفظ).

        - مكوّن واحد على الأقلّ
        - كل المكوّنات بنفس unit_type
        - لا مكوّن نصّي (text)
        - مكوّن «آخر قيمة» مسموح فقط على مستوى القسم
        - منع تكرار الاسم في نفس النطاق والسنة
        """
        if not indicators:
            raise ValidationError({
                'indicators': 'يجب اختيار مؤشّر واحد على الأقلّ كمكوّن للمستهدف'
            })

        unit_types = {ind.unit_type for ind in indicators}
        if len(unit_types) > 1:
            raise ValidationError({
                'indicators': (
                    'كل المكوّنات يجب أن تكون بنفس نوع الوحدة. '
                    f'الأنواع المُختارة: {", ".join(sorted(unit_types))}'
                )
            })

        unit_type = unit_types.pop()
        if unit_type == 'text':
            raise ValidationError({
                'indicators': 'لا يمكن إنشاء مستهدف لمؤشّرات نصّيّة'
            })

        # «آخر قيمة» مسموح فقط على مستوى القسم
        has_last_value = any(
            ind.accumulation_type == 'last_value' for ind in indicators
        )
        if has_last_value and self.scope_level != 'qism':
            raise ValidationError({
                'indicators': (
                    'المؤشرات من نوع "آخر قيمة" تُسمح لها مستهدفات على مستوى '
                    'القسم فقط (وليس الدائرة أو المديرية أو المؤسسة).'
                )
            })

        # منع تكرار الاسم في نفس النطاق والسنة
        duplicate_qs = Target.objects.filter(
            scope_unit_id=self.scope_unit_id,
            year=self.year,
            name=self.name,
        )
        if self.pk:
            duplicate_qs = duplicate_qs.exclude(pk=self.pk)
        if duplicate_qs.exists():
            scope_label = (
                self.scope_unit.name if self.scope_unit_id else 'المؤسسة'
            )
            raise ValidationError({
                'name': (
                    f'يوجد مستهدف بنفس الاسم «{self.name}» في {scope_label} '
                    f'للسنة {self.year}'
                )
            })
