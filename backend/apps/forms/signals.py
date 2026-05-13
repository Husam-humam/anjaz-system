from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.notifications.models import Notification
from apps.notifications.services import NotificationService

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
    """إشعار منشئ القالب باعتماد الاستمارة — عبر NotificationService ليصل WebSocket"""
    if not template.created_by:
        return

    NotificationService.create_notification(
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
    """إشعار منشئ القالب برفض الاستمارة — عبر NotificationService ليصل WebSocket"""
    if not template.created_by:
        return

    NotificationService.create_notification(
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
    """
    إشعار مديري قسم الإحصاء + قسم التخطيط (ضمن نطاق القسم) بوجود
    استمارة بانتظار الاعتماد — عبر NotificationService ليصل WebSocket.
    """
    from apps.accounts.models import User, UserRole

    # كل الإحصائيين (نطاق كامل)
    recipients = list(User.objects.filter(
        role=UserRole.STATISTICS_ADMIN,
        is_active=True,
    ))

    # إضافة قسم التخطيط — لأن المنطق الحالي يسمح لهم بالاعتماد
    # ضمن نطاقهم. نعتمد على `_planning_section_scope_qism_ids` لحصرهم.
    from apps.submissions.services import _planning_section_scope_qism_ids
    planners = User.objects.filter(
        role=UserRole.PLANNING_SECTION,
        is_active=True,
    )
    for planner in planners:
        scope_ids = _planning_section_scope_qism_ids(planner)
        if scope_ids is None or template.qism_id in scope_ids:
            recipients.append(planner)

    if recipients:
        NotificationService.create_bulk_notifications(
            recipients=recipients,
            notification_type=Notification.NotificationType.FORM_PENDING_APPROVAL,
            title='استمارة بانتظار الاعتماد',
            message=(
                f'تم تقديم استمارة {template.qism.name} '
                f'(الإصدار {template.version}) للاعتماد.'
            ),
            related_model='FormTemplate',
            related_id=template.pk,
        )
