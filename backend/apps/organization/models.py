from django.core.exceptions import ValidationError
from django.db import models
from mptt.models import MPTTModel, TreeForeignKey


class UnitType(models.TextChoices):
    """أنواع الكيانات التنظيمية"""
    DAIRA = 'daira', 'دائرة'
    MUDIRIYA = 'mudiriya', 'مديرية'
    QISM = 'qism', 'قسم'


class QismRole(models.TextChoices):
    """أدوار الأقسام"""
    REGULAR = 'regular', 'عادي'
    PLANNING = 'planning', 'تخطيط'
    STATISTICS = 'statistics', 'إحصاء'


class OrganizationUnit(MPTTModel):
    """نموذج الكيان التنظيمي - يمثل الهيكل التنظيمي للمؤسسة"""

    name = models.CharField(
        max_length=200,
        verbose_name='اسم الكيان',
    )
    code = models.CharField(
        max_length=20,
        unique=True,
        verbose_name='الرمز',
    )
    unit_type = models.CharField(
        max_length=20,
        choices=UnitType.choices,
        verbose_name='نوع الكيان',
    )
    qism_role = models.CharField(
        max_length=20,
        choices=QismRole.choices,
        default=QismRole.REGULAR,
        verbose_name='دور القسم',
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

        # دور القسم له معنى فقط عندما يكون نوع الكيان "قسم"
        if self.unit_type != UnitType.QISM:
            self.qism_role = QismRole.REGULAR

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def get_full_path(self):
        """إرجاع المسار الكامل للكيان من الجذر حتى الكيان الحالي"""
        ancestors = self.get_ancestors(include_self=True)
        return ' / '.join(ancestor.name for ancestor in ancestors)
