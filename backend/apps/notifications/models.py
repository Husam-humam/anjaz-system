from django.conf import settings
from django.db import models


class Notification(models.Model):
    """الإشعارات"""

    class NotificationType(models.TextChoices):
        PERIOD_OPENED = 'period_opened', 'فتح أسبوع جديد'
        SUBMISSION_DUE = 'submission_due', 'اقتراب الموعد النهائي'
        SUBMISSION_LATE = 'submission_late', 'تأخر في التسليم'
        EXTENSION_GRANTED = 'extension_granted', 'منح تمديد'
        FORM_PENDING_APPROVAL = 'form_pending_approval', 'استمارة بانتظار الاعتماد'
        FORM_APPROVED = 'form_approved', 'اعتماد الاستمارة'
        FORM_REJECTED = 'form_rejected', 'رفض الاستمارة'
        SUBMISSION_RECEIVED = 'submission_received', 'استلام منجز'
        SUBMISSION_APPROVED = 'submission_approved', 'اعتماد المنجز'
        QUALITATIVE_PENDING = 'qualitative_pending', 'منجز نوعي بانتظار الاعتماد'
        QUALITATIVE_APPROVED = 'qualitative_approved', 'اعتماد المنجز النوعي'
        QUALITATIVE_REJECTED = 'qualitative_rejected', 'رفض المنجز النوعي'

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='notifications', verbose_name='المستلم'
    )
    notification_type = models.CharField(
        max_length=30, choices=NotificationType.choices,
        verbose_name='نوع الإشعار'
    )
    title = models.CharField(max_length=200, verbose_name='العنوان')
    message = models.TextField(verbose_name='الرسالة')
    is_read = models.BooleanField(default=False, verbose_name='مقروء')
    related_model = models.CharField(
        max_length=50, blank=True, default='',
        verbose_name='النموذج المرتبط'
    )
    related_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='معرف المرتبط'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاريخ الإنشاء')

    class Meta:
        db_table = 'notifications'
        verbose_name = 'إشعار'
        verbose_name_plural = 'الإشعارات'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['created_at'], name='idx_notification_created'),
            models.Index(fields=['notification_type'], name='idx_notification_type'),
        ]

    def __str__(self):
        return f'{self.title} - {self.recipient}'
