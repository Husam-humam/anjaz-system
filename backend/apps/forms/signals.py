from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.notifications.models import Notification

from .models import FormTemplate


@receiver(post_save, sender=FormTemplate)
def form_template_status_changed(sender, instance, **kwargs):
    """
    إرسال إشعارات عند تغيير حالة قالب الاستمارة.
    - عند الاعتماد: إشعار لمنشئ القالب
    - عند الرفض: إشعار لمنشئ القالب
    - عند تقديم للاعتماد: إشعار لمديري قسم الإحصاء
    """
    # تجنب الإشعارات عند الإنشاء الأولي
    if kwargs.get('created', False):
        return

    update_fields = kwargs.get('update_fields')

    # التحقق من أن الحالة تغيرت (عبر update_fields أو عبر save عام)
    if update_fields and 'status' not in update_fields:
        return

    if instance.status == FormTemplate.Status.APPROVED:
        _notify_form_approved(instance)
    elif instance.status == FormTemplate.Status.REJECTED:
        _notify_form_rejected(instance)
    elif instance.status == FormTemplate.Status.PENDING_APPROVAL:
        _notify_form_pending_approval(instance)


def _notify_form_approved(template):
    """إشعار منشئ القالب باعتماد الاستمارة"""
    if not template.created_by:
        return

    Notification.objects.create(
        recipient=template.created_by,
        notification_type=Notification.NotificationType.FORM_APPROVED,
        title='تم اعتماد الاستمارة',
        message=(
            f'تم اعتماد استمارة {template.qism.name} '
            f'(الإصدار {template.version}) '
            f'وستكون سارية من الأسبوع {template.effective_from_week} '
            f'لسنة {template.effective_from_year}.'
        ),
        related_model='FormTemplate',
        related_id=template.pk,
    )


def _notify_form_rejected(template):
    """إشعار منشئ القالب برفض الاستمارة"""
    if not template.created_by:
        return

    Notification.objects.create(
        recipient=template.created_by,
        notification_type=Notification.NotificationType.FORM_REJECTED,
        title='تم رفض الاستمارة',
        message=(
            f'تم رفض استمارة {template.qism.name} '
            f'(الإصدار {template.version}). '
            f'السبب: {template.rejection_reason}'
        ),
        related_model='FormTemplate',
        related_id=template.pk,
    )


def _notify_form_pending_approval(template):
    """إشعار مديري قسم الإحصاء بوجود استمارة بانتظار الاعتماد"""
    from apps.accounts.models import User, UserRole

    # الحصول على جميع مديري قسم الإحصاء النشطين
    statistics_admins = User.objects.filter(
        role=UserRole.STATISTICS_ADMIN,
        is_active=True,
    )

    notifications = [
        Notification(
            recipient=admin_user,
            notification_type=Notification.NotificationType.FORM_PENDING_APPROVAL,
            title='استمارة بانتظار الاعتماد',
            message=(
                f'تم تقديم استمارة {template.qism.name} '
                f'(الإصدار {template.version}) للاعتماد.'
            ),
            related_model='FormTemplate',
            related_id=template.pk,
        )
        for admin_user in statistics_admins
    ]

    if notifications:
        Notification.objects.bulk_create(notifications)
