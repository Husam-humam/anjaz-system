"""
نماذج تطبيق الحسابات — نموذج المستخدم المخصص لنظام إنجاز.
"""
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models


class UserRole(models.TextChoices):
    """أدوار المستخدمين في النظام."""
    STATISTICS_ADMIN = 'statistics_admin', 'مدير قسم الإحصاء'
    PLANNING_SECTION = 'planning_section', 'قسم التخطيط'
    SECTION_MANAGER = 'section_manager', 'مدير قسم'
    # دور قراءة فقط — يُمنح صلاحية الاطّلاع على وحدات محدّدة عبر ViewScope.
    # لا يستطيع الاعتماد / الرفض / التعديل / الإرسال.
    VIEWER = 'viewer', 'مُطّلِع'


class User(AbstractUser):
    """
    نموذج المستخدم المخصص لنظام إنجاز.
    يمتد من AbstractUser مع إزالة الحقول غير المطلوبة
    وإضافة حقول خاصة بالنظام.
    """

    # إزالة الحقول غير المطلوبة
    first_name = None
    last_name = None
    email = None

    # الحقول المخصصة
    full_name = models.CharField(
        max_length=200,
        verbose_name='الاسم الكامل',
    )

    role = models.CharField(
        max_length=30,
        choices=UserRole.choices,
        verbose_name='الدور',
    )

    unit = models.ForeignKey(
        'organization.OrganizationUnit',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
        verbose_name='الوحدة التنظيمية',
    )

    created_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_users',
        verbose_name='أنشئ بواسطة',
    )

    # حقول التتبع الزمني
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='تاريخ الإنشاء',
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='تاريخ التحديث',
    )

    REQUIRED_FIELDS = ['full_name', 'role']

    class Meta:
        db_table = 'users'
        verbose_name = 'مستخدم'
        verbose_name_plural = 'المستخدمون'

    def __str__(self):
        return self.full_name

    def clean(self):
        """
        التحقق من صحة العلاقة بين دور المستخدم ونوع الوحدة التنظيمية.

        قواعد الوحدة بحسب الدور:
        - section_manager: إلزامية (نطاقه = وحدته)
        - planning_section: إلزامية (وحدته هي قسم التخطيط، نطاقه يأتي من
          PlanningAssignment للوحدة)
        - statistics_admin: اختيارية (نطاق كامل بغضّ النظر عن الوحدة)
        - viewer: اختيارية (نطاقه يأتي من ViewScope.viewable_units فقط)

        ملاحظة: بعد Phase F (إزالة `qism_role`)، لم يَعُد هناك تطابق إلزامي
        بين الدور و«نوع القسم». التخصيصات الصريحة (PlanningAssignment)
        تحلّ مكان هذه القواعد.
        """
        super().clean()

        if not self.unit_id:
            if self.role == UserRole.SECTION_MANAGER:
                raise ValidationError({
                    'unit': 'مدير القسم يجب أن يكون مرتبطاً بقسم.',
                })
            if self.role == UserRole.PLANNING_SECTION:
                raise ValidationError({
                    'unit': 'قسم التخطيط يجب أن يرتبط بوحدة تنظيميّة.',
                })
            return

        # الوحدة موجودة. التحقّقات السابقة على `qism_role` تُحفَظ مؤقّتاً
        # للحفاظ على التوافق حتى Phase F. سيتم استبدالها بـ
        # PlanningAssignment validation في Phase D.
        unit = self.unit
        role_to_qism_role = {
            UserRole.STATISTICS_ADMIN: 'statistics',
            UserRole.PLANNING_SECTION: 'planning',
            UserRole.SECTION_MANAGER: 'regular',
        }
        role_error_messages = {
            UserRole.STATISTICS_ADMIN: 'مدير قسم الإحصاء يجب أن يرتبط بقسم من نوع "إحصاء".',
            UserRole.PLANNING_SECTION: 'قسم التخطيط يجب أن يرتبط بقسم من نوع "تخطيط".',
            UserRole.SECTION_MANAGER: 'مدير القسم يجب أن يرتبط بقسم من نوع "عادي".',
        }
        expected_qism_role = role_to_qism_role.get(self.role)
        if expected_qism_role is None:
            # viewer أو أي دور لا يفرض نوع قسم
            return

        if unit.unit_type != 'qism':
            raise ValidationError({
                'unit': 'يجب أن تكون الوحدة التنظيمية من نوع "قسم".',
            })
        if unit.qism_role != expected_qism_role:
            raise ValidationError({
                'unit': role_error_messages[self.role],
            })
