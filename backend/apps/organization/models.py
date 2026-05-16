from django.core.exceptions import ValidationError
from django.db import models
from mptt.models import MPTTModel, TreeForeignKey

from .querysets import OrganizationUnitManager, OrganizationUnitQuerySet


class UnitType(models.TextChoices):
    """أنواع الكيانات التنظيمية"""
    DAIRA = 'daira', 'دائرة'
    MUDIRIYA = 'mudiriya', 'مديرية'
    QISM = 'qism', 'قسم'


class OrganizationUnit(MPTTModel):
    """نموذج الكيان التنظيمي - يمثل الهيكل التنظيمي للمؤسسة"""

    objects = OrganizationUnitManager()

    name = models.CharField(
        max_length=200,
        verbose_name='اسم الكيان',
    )
    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='الرمز',
    )
    unit_type = models.CharField(
        max_length=20,
        choices=UnitType.choices,
        verbose_name='نوع الكيان',
    )
    parent = TreeForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name='الكيان الأب',
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='نشط',
    )
    # ─── ربط بالنظام الخارجي ───
    # المعرّف في النظام الخارجي (مصدر الحقيقة لبنية الهيكل التنظيمي).
    # الوحدات اليدويّة القديمة (قبل المزامنة) تبقى بـ NULL ولا تُمسّ بالمزامنة.
    external_id = models.PositiveIntegerField(
        null=True, blank=True, unique=True, db_index=True,
        verbose_name='المعرّف الخارجي',
        help_text='معرّف الوحدة في نظام الهيكل التنظيمي المركزي',
    )
    external_synced_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name='آخر مزامنة مع النظام الخارجي',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='تاريخ الإنشاء',
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='تاريخ التحديث',
    )

    class MPTTMeta:
        order_insertion_by = ['name']

    class Meta:
        db_table = 'organization_units'
        verbose_name = 'كيان تنظيمي'
        verbose_name_plural = 'الكيانات التنظيمية'
        indexes = [
            models.Index(fields=['unit_type'], name='idx_org_units_type'),
            models.Index(fields=['parent'], name='idx_org_units_parent'),
            models.Index(fields=['tree_id', 'lft', 'rght'], name='idx_org_units_mptt'),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        """التحقق من صحة العلاقات الهرمية بين الكيانات التنظيمية"""
        super().clean()

        # التحقق من قواعد التسلسل الهرمي حسب نوع الكيان
        if self.unit_type == UnitType.DAIRA:
            if self.parent is not None:
                raise ValidationError({
                    'parent': 'الدائرة يجب أن تكون في المستوى الأعلى (بدون كيان أب).'
                })

        elif self.unit_type == UnitType.MUDIRIYA:
            if self.parent is not None and self.parent.unit_type != UnitType.DAIRA:
                raise ValidationError({
                    'parent': 'المديرية يجب أن تتبع دائرة أو تكون مستقلة (بدون كيان أب).'
                })

        elif self.unit_type == UnitType.QISM:
            if self.parent is None:
                raise ValidationError({
                    'parent': 'القسم يجب أن يتبع مديرية أو دائرة.'
                })
            if self.parent.unit_type not in (UnitType.MUDIRIYA, UnitType.DAIRA):
                raise ValidationError({
                    'parent': 'القسم يجب أن يتبع مديرية أو دائرة فقط.'
                })

        # القسم لا يمكن أن يكون أباً لأي كيان آخر
        if self.parent is not None and self.parent.unit_type == UnitType.QISM:
            raise ValidationError({
                'parent': 'القسم لا يمكن أن يكون كياناً أباً لأي كيان آخر.'
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def get_full_path(self):
        """إرجاع المسار الكامل للكيان من الجذر حتى الكيان الحالي"""
        ancestors = self.get_ancestors(include_self=True)
        return ' / '.join(ancestor.name for ancestor in ancestors)


# ═══════════════════════════════════════════════════════════════
# نماذج التخصيصات (assignments) — تَحلّ محلّ qism_role في Phase F
# ═══════════════════════════════════════════════════════════════

class PlanningAssignment(models.Model):
    """
    تخصيص قسم تخطيط: يربط وحدة معيّنة بدور «قسم التخطيط» ويحدّد المديرية/
    الدائرة الأم سياقياً (للعرض في التقارير). الأقسام المُشرَف عليها تُحدَّد
    عبر `SupervisedUnit` (relationship منفصل لضمان أن قسماً واحداً = مُشرف
    واحد).

    قواعد الأعمال:
    - وحدة واحدة لا يمكن أن تكون قسم تخطيط مرّتَين (OneToOne).
    - الوحدة الأم (context_parent) للعرض فقط — لا تُقيّد نطاق الإشراف.
    - عند حذف وحدة، يُمنع الحذف (PROTECT) لحماية البيانات المرتبطة.
    """
    planning_unit = models.OneToOneField(
        OrganizationUnit,
        on_delete=models.PROTECT,
        related_name='planning_assignment',
        verbose_name='الوحدة العاملة كقسم تخطيط',
    )
    context_parent = models.ForeignKey(
        OrganizationUnit,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',  # لا حاجة لـ reverse accessor
        verbose_name='المديرية/الدائرة الأم',
        help_text='للعرض في التقارير فقط — لا يقيّد نطاق الإشراف',
    )
    notes = models.TextField(blank=True, default='', verbose_name='ملاحظات')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_planning_assignments',
        verbose_name='أُنشئ بواسطة',
    )

    class Meta:
        db_table = 'planning_assignments'
        verbose_name = 'تخصيص قسم تخطيط'
        verbose_name_plural = 'تخصيصات أقسام التخطيط'

    def __str__(self):
        return f'{self.planning_unit.name} (تخطيط)'


class SupervisedUnit(models.Model):
    """
    قسم تحت إشراف قسم تخطيط معيّن.

    قاعدة جوهريّة: `unit` هو OneToOne — كل وحدة يمكن أن تكون مُشرَفاً عليها
    من قِبَل قسم تخطيط واحد فقط. لو احتاج النموذج لتعدّد المُشرفين لاحقاً،
    نحوّل إلى FK مع unique_together(unit) ثم نُرخيه.
    """
    assignment = models.ForeignKey(
        PlanningAssignment,
        on_delete=models.CASCADE,
        related_name='supervised_units',
        verbose_name='تخصيص قسم التخطيط',
    )
    unit = models.OneToOneField(
        OrganizationUnit,
        on_delete=models.PROTECT,
        related_name='supervisor_link',
        verbose_name='الوحدة المُشرَف عليها',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإضافة')

    class Meta:
        db_table = 'supervised_units'
        verbose_name = 'وحدة مُشرَف عليها'
        verbose_name_plural = 'الوحدات المُشرَف عليها'
        indexes = [
            models.Index(fields=['assignment'], name='idx_supervised_assignment'),
        ]

    def __str__(self):
        return f'{self.unit.name} ← {self.assignment.planning_unit.name}'

    def clean(self):
        super().clean()
        # وحدة قسم التخطيط نفسها لا تُشرَف عليها بنفسها (يمكن تخفيف هذه القاعدة
        # لاحقاً لو احتاج قسم تخطيط أن يُرسل منجزاته بنفسه — لكن يبقى منطقياً
        # أن نمنع self-reference هنا).
        if (
            self.unit_id is not None
            and self.assignment_id is not None
            and self.unit_id == self.assignment.planning_unit_id
        ):
            raise ValidationError({
                'unit': 'لا يمكن لقسم التخطيط أن يكون تحت إشراف نفسه.',
            })


class ViewScope(models.Model):
    """
    نطاق اطّلاع موسَّع لمستخدم — يمنحه رؤية وحدات إضافيّة لا يديرها.

    حالات الاستخدام:
    - دور `viewer`: ViewScope = نطاق الاطّلاع الكامل (لا يدير شيئاً).
    - دور `planning_section`: ViewScope = نطاق إضافي فوق المُدار (مثل قسم
      تخطيط دائرة يطّلع على أقسام مديريّاتها التي يديرها مخطّطو المديريّات).
    - باقي الأدوار: ViewScope غير ضروري (admin له نطاق كامل ضمنياً،
      section_manager محصور بقسمه).

    المُنشئ المتوقّع لـ ViewScope هو `statistics_admin` فقط.
    """
    user = models.OneToOneField(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='view_scope',
        verbose_name='المستخدم',
    )
    viewable_units = models.ManyToManyField(
        OrganizationUnit,
        related_name='view_scope_users',
        blank=True,
        verbose_name='الوحدات القابلة للاطّلاع',
    )
    notes = models.TextField(blank=True, default='', verbose_name='ملاحظات')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_view_scopes',
        verbose_name='أُنشئ بواسطة',
    )

    class Meta:
        db_table = 'view_scopes'
        verbose_name = 'نطاق اطّلاع'
        verbose_name_plural = 'نطاقات الاطّلاع'

    def __str__(self):
        return f'ViewScope({self.user.full_name})'


# ═══════════════════════════════════════════════════════════════
# تطابق أنواع الوحدات بين النظام الخارجي و نظام أنجز
# ═══════════════════════════════════════════════════════════════

class ExternalUnitTypeMapping(models.Model):
    """
    يربط أسماء أنواع الوحدات الواردة من النظام الخارجي بأحد الأنواع الثلاثة
    في «أنجز» (دائرة / مديرية / قسم)، أو يُعلِّمها كـ «تجاهل».

    التدفّق المتوقّع:
    1. عند مزامنة الهيكل التنظيمي، نجلب قائمة `unit_types` من النظام الخارجي.
    2. نُنشئ سطراً لكل نوع جديد بـ `treat_as=NULL` (يعني: «لم يُقرَّر بعد»).
    3. يفتح الأدمن صفحة الإعدادات ويُحدّد القرار.
    4. أثناء المزامنة الفعلية للوحدات، نستخدم هذا الجدول بدل خريطة مُجمَّدة.
       - `treat_as` يساوي أحد الـ 3 أنواع → الوحدة تُستورَد بذلك النوع
       - `treat_as='ignore'` → الوحدة تُتجاهَل تماماً
       - `treat_as=NULL` → الوحدة تُتجاهَل مع عدّ skipped_unknown_type
    """

    class TreatAs(models.TextChoices):
        DAIRA = 'daira', 'دائرة'
        MUDIRIYA = 'mudiriya', 'مديرية'
        QISM = 'qism', 'قسم'
        IGNORE = 'ignore', 'تجاهل'

    external_type_name = models.CharField(
        max_length=100, unique=True, db_index=True,
        verbose_name='اسم نوع الوحدة في النظام الخارجي',
        help_text='كما يُرجعه `unit_type_name` من /reference/unit-types/',
    )
    external_type_id = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='المعرّف في النظام الخارجي',
        help_text='اختياري — للتتبّع فقط، لا يُستخدم في الربط',
    )
    treat_as = models.CharField(
        max_length=20,
        choices=TreatAs.choices,
        null=True, blank=True,
        verbose_name='يُعامَل كـ',
        help_text='اتركه فارغاً مؤقتاً حتى يُقرّر الأدمن. القيم: daira / mudiriya / qism / ignore',
    )
    notes = models.TextField(blank=True, default='', verbose_name='ملاحظات')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاريخ التحديث')

    class Meta:
        db_table = 'external_unit_type_mappings'
        verbose_name = 'تطابق نوع وحدة خارجي'
        verbose_name_plural = 'تطابقات أنواع الوحدات الخارجيّة'
        ordering = ['external_type_name']

    def __str__(self):
        decision = self.get_treat_as_display() if self.treat_as else 'لم يُحدَّد'
        return f'{self.external_type_name} → {decision}'
