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
        """
        super().clean()

        if not self.unit_id:
            return

        unit = self.unit

        # خريطة الدور → دور القسم المطلوب
        role_to_qism_role = {
            UserRole.STATISTICS_ADMIN: 'statistics',
            UserRole.PLANNING_SECTION: 'planning',
            UserRole.SECTION_MANAGER: 'regular',
        }

        # خريطة الدور → رسالة الخطأ
        role_error_messages = {
            UserRole.STATISTICS_ADMIN: 'مدير قسم الإحصاء يجب أن يرتبط بقسم من نوع "إحصاء".',
            UserRole.PLANNING_SECTION: 'قسم التخطيط يجب أن يرتبط بقسم من نوع "تخطيط".',
            UserRole.SECTION_MANAGER: 'مدير القسم يجب أن يرتبط بقسم من نوع "عادي".',
        }

        expected_qism_role = role_to_qism_role.get(self.role)

        if expected_qism_role is None:
            return

        # التحقق من أن الوحدة هي قسم (qism)
        if unit.unit_type != 'qism':
            raise ValidationError({
                'unit': 'يجب أن تكون الوحدة التنظيمية من نوع "قسم".',
            })

        # التحقق من أن دور القسم يطابق دور المستخدم
        if unit.qism_role != expected_qism_role:
            raise ValidationError({
                'unit': role_error_messages[self.role],
            })
