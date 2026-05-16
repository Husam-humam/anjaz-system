from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    """
    سجل تدقيق عام (append-only) لكل الإجراءات الحسّاسة في النظام.

    التصميم:
    - يُسجَّل سطر واحد لكل إجراء (ليس لكل حقل في التعديل — التفاصيل في `field_changes`).
    - `target_model` + `target_id` يُعرِّفان الكائن المستهدَف دون استخدام
      `GenericForeignKey` (الذي يُعقِّد الاستعلامات) — نكتفي بسلسلة اسم النموذج.
    - `field_changes` هو JSON يحتوي قائمة التعديلات بالشكل:
        [{"field": "notes", "old": "...", "new": "...", "item_id": 3}, ...]
      الحقل `item_id` اختياري (لتمييز بند معيّن في المنجز عند تعديل إجابة).
    - `metadata` JSON مرن لأي سياق إضافي (سبب الإرسال، مصدر الطلب، ...).
    - الجدول append-only: لا UPDATE ولا DELETE من طبقة التطبيق.
    """

    class ActionType(models.TextChoices):
        # ─── إجراءات المنجزات الأسبوعية ───
        SUBMISSION_CREATED = 'submission_created', 'إنشاء منجز'
        SUBMISSION_SAVED = 'submission_saved', 'حفظ إجابات منجز'
        SUBMISSION_SUBMITTED = 'submission_submitted', 'إرسال منجز للاعتماد'
        SUBMISSION_PLANNING_APPROVED = (
            'submission_planning_approved', 'اعتماد منجز من التخطيط'
        )
        SUBMISSION_PLANNING_RETURNED = (
            'submission_planning_returned', 'إرجاع منجز من التخطيط'
        )
        SUBMISSION_ADMIN_APPROVED = (
            'submission_admin_approved', 'اعتماد منجز من الإحصاء'
        )
        SUBMISSION_ADMIN_EDITED = (
            'submission_admin_edited', 'تعديل منجز من الإحصاء'
        )
        SUBMISSION_ADMIN_RETURNED = (
            'submission_admin_returned', 'إرجاع منجز من الإحصاء للتخطيط'
        )

        # ─── الإجابات النوعية ───
        QUALITATIVE_PLANNING_APPROVED = (
            'qualitative_planning_approved', 'اعتماد نوعي من التخطيط'
        )
        QUALITATIVE_PLANNING_REJECTED = (
            'qualitative_planning_rejected', 'رفض نوعي من التخطيط'
        )
        QUALITATIVE_ADMIN_APPROVED = (
            'qualitative_admin_approved', 'اعتماد نوعي من الإحصاء'
        )
        QUALITATIVE_ADMIN_REJECTED = (
            'qualitative_admin_rejected', 'رفض نوعي من الإحصاء'
        )

        # ─── إجراءات قوالب الاستمارات ───
        TEMPLATE_CREATED = 'template_created', 'إنشاء قالب استمارة'
        TEMPLATE_UPDATED = 'template_updated', 'تعديل قالب استمارة'
        TEMPLATE_SUBMITTED = 'template_submitted', 'تقديم قالب للاعتماد'
        TEMPLATE_APPROVED = 'template_approved', 'اعتماد قالب'
        TEMPLATE_REJECTED = 'template_rejected', 'رفض قالب'
        TEMPLATE_NEW_VERSION = 'template_new_version', 'إنشاء إصدار جديد'

        # ─── المستهدفات ───
        TARGET_CREATED = 'target_created', 'إنشاء مستهدف'
        TARGET_UPDATED = 'target_updated', 'تعديل مستهدف'
        TARGET_DELETED = 'target_deleted', 'حذف مستهدف'

        # ─── التمديدات ───
        EXTENSION_GRANTED = 'extension_granted', 'منح تمديد موعد'

        # ─── الفترات الأسبوعية ───
        PERIOD_OPENED = 'period_opened', 'فتح أسبوع'
        PERIOD_CLOSED = 'period_closed', 'إغلاق أسبوع'

        # ─── إدارة المستخدمين ───
        USER_CREATED = 'user_created', 'إنشاء مستخدم'
        USER_UPDATED = 'user_updated', 'تعديل بيانات مستخدم'
        USER_PASSWORD_RESET = 'user_password_reset', 'إعادة تعيين كلمة المرور'
        USER_DEACTIVATED = 'user_deactivated', 'تعطيل مستخدم'
        USER_REACTIVATED = 'user_reactivated', 'تفعيل مستخدم'

        # ─── إدارة المؤشّرات ───
        INDICATOR_CREATED = 'indicator_created', 'إنشاء مؤشّر'
        INDICATOR_UPDATED = 'indicator_updated', 'تعديل مؤشّر'
        INDICATOR_DEACTIVATED = 'indicator_deactivated', 'تعطيل مؤشّر'

    action_type = models.CharField(
        max_length=50, choices=ActionType.choices, verbose_name='نوع الإجراء'
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='audit_actions',
        verbose_name='المنفِّذ',
    )
    actor_role = models.CharField(
        max_length=30, blank=True, default='',
        verbose_name='دور المنفِّذ',
        help_text='يُحفَظ للاحتفاظ بالسياق حتى عند تغيير دور المستخدم لاحقاً',
    )

    # الكائن المستهدَف — نستخدم string بدل GenericForeignKey لتبسيط الاستعلامات.
    target_model = models.CharField(
        max_length=50, verbose_name='نموذج الكائن',
        help_text='اسم النموذج المستهدَف مثل WeeklySubmission, FormTemplate',
    )
    target_id = models.PositiveBigIntegerField(
        null=True, blank=True, verbose_name='معرّف الكائن',
    )
    target_repr = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='وصف الكائن',
        help_text='وصف نصّي للكائن وقت الإجراء (لا يتأثّر بتغييرات لاحقة)',
    )

    # سياق هرمي للتصفية السريعة (مفيد للأدمن عند فلترة السجلّ حسب قسم/دائرة).
    qism = models.ForeignKey(
        'organization.OrganizationUnit', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
        verbose_name='القسم المرتبط',
    )

    # تفاصيل التعديل — قائمة JSON من تعديلات الحقول.
    field_changes = models.JSONField(
        null=True, blank=True, default=None,
        verbose_name='تفاصيل التعديلات',
    )

    # السبب (إلزامي لإجراءات الإرجاع والتعديل — غير مطلوب للاعتماد).
    reason = models.TextField(
        blank=True, default='', verbose_name='السبب',
    )

    # بيانات إضافية مرنة (source, ip, old/new status, ...).
    metadata = models.JSONField(
        null=True, blank=True, default=None,
        verbose_name='بيانات إضافية',
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='وقت الإجراء')

    class Meta:
        db_table = 'audit_log'
        verbose_name = 'سجل تدقيق'
        verbose_name_plural = 'سجل التدقيق'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['target_model', 'target_id'], name='idx_audit_target'),
            models.Index(fields=['action_type'], name='idx_audit_action'),
            models.Index(fields=['actor'], name='idx_audit_actor'),
            models.Index(fields=['qism', '-created_at'], name='idx_audit_qism_time'),
            models.Index(fields=['-created_at'], name='idx_audit_time'),
        ]

    def __str__(self):
        actor_name = self.actor.full_name if self.actor else 'النظام'
        return f'{self.get_action_type_display()} بواسطة {actor_name} في {self.created_at}'
