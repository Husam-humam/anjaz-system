import logging

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model

from .models import Notification

logger = logging.getLogger(__name__)
User = get_user_model()


class NotificationService:

    @staticmethod
    def create_notification(recipient, notification_type, title, message,
                            related_model='', related_id=None):
        """إنشاء إشعار وإرساله عبر WebSocket"""
        notification = Notification.objects.create(
            recipient=recipient,
            notification_type=notification_type,
            title=title,
            message=message,
            related_model=related_model,
            related_id=related_id,
        )
        # إرسال عبر WebSocket
        NotificationService._send_ws_notification(notification)
        return notification

    @staticmethod
    def create_bulk_notifications(recipients, notification_type, title, message,
                                  related_model='', related_id=None):
        """إنشاء إشعارات متعددة"""
        notifications = []
        for recipient in recipients:
            notification = Notification(
                recipient=recipient,
                notification_type=notification_type,
                title=title,
                message=message,
                related_model=related_model,
                related_id=related_id,
            )
            notifications.append(notification)
        created = Notification.objects.bulk_create(notifications)
        for notification in created:
            NotificationService._send_ws_notification(notification)
        return created

    @staticmethod
    def mark_as_read(notification):
        """تعليم إشعار كمقروء"""
        notification.is_read = True
        notification.save(update_fields=['is_read'])

    @staticmethod
    def mark_all_as_read(user):
        """تعليم جميع الإشعارات كمقروءة"""
        Notification.objects.filter(
            recipient=user, is_read=False
        ).update(is_read=True)

    @staticmethod
    def get_unread_count(user):
        """عدد الإشعارات غير المقروءة"""
        return Notification.objects.filter(
            recipient=user, is_read=False
        ).count()

    @staticmethod
    def notify_period_opened(period):
        """إشعار بفتح أسبوع جديد"""
        # إشعار لجميع مديري الأقسام العادية النشطة
        # ملاحظة: سلسلة الدور تعتمد على القيم المعرّفة في نموذج المستخدم (UserRole)
        recipients = User.objects.filter(
            role='section_manager',
            is_active=True,
            unit__is_active=True,
            unit__qism_role='regular',
        )
        NotificationService.create_bulk_notifications(
            recipients=recipients,
            notification_type='period_opened',
            title='تم فتح أسبوع جديد',
            message=f'تم فتح {period} - الموعد النهائي: {period.deadline.strftime("%Y-%m-%d %H:%M")}',
            related_model='WeeklyPeriod',
            related_id=period.id,
        )

    @staticmethod
    def notify_submission_received(submission):
        """إشعار قسم التخطيط باستلام منجز"""
        parent = submission.qism.parent
        if not parent:
            return
        # ملاحظة: سلسلة الدور تعتمد على القيم المعرّفة في نموذج المستخدم (UserRole)
        planners = User.objects.filter(
            role='planning_section',
            is_active=True,
            unit__parent=parent,
            unit__qism_role='planning',
        )
        NotificationService.create_bulk_notifications(
            recipients=planners,
            notification_type='submission_received',
            title='تم استلام منجز أسبوعي',
            message=f'قدم {submission.qism.name} المنجز الأسبوعي لـ{submission.weekly_period}',
            related_model='WeeklySubmission',
            related_id=submission.id,
        )

    @staticmethod
    def notify_submission_approved(submission):
        """إشعار مدير القسم باعتماد المنجز"""
        # ملاحظة: سلسلة الدور تعتمد على القيم المعرّفة في نموذج المستخدم (UserRole)
        managers = User.objects.filter(
            unit=submission.qism,
            role='section_manager',
            is_active=True,
        )
        NotificationService.create_bulk_notifications(
            recipients=managers,
            notification_type='submission_approved',
            title='تم اعتماد المنجز الأسبوعي',
            message=f'تم اعتماد منجز {submission.weekly_period} بواسطة قسم التخطيط',
            related_model='WeeklySubmission',
            related_id=submission.id,
        )

    @staticmethod
    def notify_extension_granted(extension):
        """إشعار بمنح تمديد"""
        # ملاحظة: سلسلة الدور تعتمد على القيم المعرّفة في نموذج المستخدم (UserRole)
        managers = User.objects.filter(
            unit=extension.qism,
            role='section_manager',
            is_active=True,
        )
        NotificationService.create_bulk_notifications(
            recipients=managers,
            notification_type='extension_granted',
            title='تم منح تمديد للموعد النهائي',
            message=f'تم تمديد الموعد النهائي لـ{extension.weekly_period} إلى {extension.new_deadline.strftime("%Y-%m-%d %H:%M")}',
            related_model='QismExtension',
            related_id=extension.id,
        )

    @staticmethod
    def notify_qualitative_approved(answer):
        """إشعار باعتماد المنجز النوعي"""
        # ملاحظة: سلسلة الدور تعتمد على القيم المعرّفة في نموذج المستخدم (UserRole)
        managers = User.objects.filter(
            unit=answer.submission.qism,
            role='section_manager',
            is_active=True,
        )
        NotificationService.create_bulk_notifications(
            recipients=managers,
            notification_type='qualitative_approved',
            title='تم اعتماد المنجز النوعي',
            message=f'تم اعتماد المنجز النوعي: {answer.form_item.indicator.name}',
            related_model='SubmissionAnswer',
            related_id=answer.id,
        )

    @staticmethod
    def notify_qualitative_rejected(answer):
        """إشعار برفض المنجز النوعي"""
        # ملاحظة: سلسلة الدور تعتمد على القيم المعرّفة في نموذج المستخدم (UserRole)
        managers = User.objects.filter(
            unit=answer.submission.qism,
            role='section_manager',
            is_active=True,
        )
        NotificationService.create_bulk_notifications(
            recipients=managers,
            notification_type='qualitative_rejected',
            title='تم رفض المنجز النوعي',
            message=f'تم رفض المنجز النوعي: {answer.form_item.indicator.name} - السبب: {answer.rejection_reason}',
            related_model='SubmissionAnswer',
            related_id=answer.id,
        )

    @staticmethod
    def notify_qualitative_pending(answer):
        """إشعار بوجود منجز نوعي بانتظار اعتماد الإحصاء"""
        # ملاحظة: سلسلة الدور تعتمد على القيم المعرّفة في نموذج المستخدم (UserRole)
        admins = User.objects.filter(
            role='statistics_admin',
            is_active=True,
        )
        NotificationService.create_bulk_notifications(
            recipients=admins,
            notification_type='qualitative_pending',
            title='منجز نوعي بانتظار الاعتماد',
            message=f'منجز نوعي من {answer.submission.qism.name}: {answer.form_item.indicator.name}',
            related_model='SubmissionAnswer',
            related_id=answer.id,
        )

    @staticmethod
    def _send_ws_notification(notification):
        """إرسال إشعار عبر WebSocket"""
        try:
            channel_layer = get_channel_layer()
            group_name = f'notifications_user_{notification.recipient_id}'
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    'type': 'notification_message',
                    'data': {
                        'id': notification.id,
                        'notification_type': notification.notification_type,
                        'title': notification.title,
                        'message': notification.message,
                        'is_read': notification.is_read,
                        'created_at': notification.created_at.isoformat(),
                        'related_model': notification.related_model,
                        'related_id': notification.related_id,
                    }
                }
            )
        except Exception as e:
            # عدم تعطيل العملية إذا فشل WebSocket مع تسجيل التحذير
            logger.warning(f"فشل إرسال إشعار WebSocket: {e}")
