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
        التحقق من صحة العلاقة بين دور المستخدم والوحدة التنظيميّة.

        قواعد الوحدة بحسب الدور:
        - section_manager: إلزامية (نطاقه = وحدته فقط)
        - planning_section: إلزامية (وحدته = قسم التخطيط، نطاقه يأتي من
          PlanningAssignment.supervised_units)
        - statistics_admin: اختيارية (نطاق كامل بغضّ النظر عن الوحدة)
        - viewer: اختيارية (نطاقه = ViewScope.viewable_units)

        ملاحظة: مفهوم "نوع القسم" (qism_role) أُلغي. التمييز بين قسم
        تخطيط / عادي / إحصاء يأتي الآن من التخصيصات الصريحة:
        - PlanningAssignment يُعرّف من هو قسم تخطيط
        - SupervisedUnit يُعرّف من هو قسم عادي مُشرَف عليه
        - statistics_admin role لا يحتاج وحدة خاصّة
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
            # statistics_admin و viewer: الوحدة اختياريّة
            return

        # الوحدة موجودة. لا قيود إضافيّة — التخصيصات الصريحة تتولّى التحقّق
        # الفعلي من «من هو قسم تخطيط» عند الإجراءات الفعليّة.
