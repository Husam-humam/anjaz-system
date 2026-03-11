"""
اختبارات طبقة الخدمات لتطبيق الإشعارات.
"""
import pytest
from unittest.mock import patch

from apps.accounts.tests.factories import SectionManagerFactory
from apps.notifications.models import Notification
from apps.notifications.services import NotificationService

from .factories import NotificationFactory


@pytest.mark.django_db
class TestNotificationServiceCreate:
    """اختبارات إنشاء الإشعارات"""

    @patch("apps.notifications.services.NotificationService._send_ws_notification")
    def test_create_notification(self, mock_ws):
        """إنشاء إشعار جديد بنجاح"""
        user = SectionManagerFactory()

        notification = NotificationService.create_notification(
            recipient=user,
            notification_type="period_opened",
            title="فتح أسبوع جديد",
            message="تم فتح الأسبوع 10 / 2025",
            related_model="WeeklyPeriod",
            related_id=1,
        )

        assert notification.id is not None
        assert notification.recipient == user
        assert notification.notification_type == "period_opened"
        assert notification.title == "فتح أسبوع جديد"
        assert notification.is_read is False
        assert notification.related_model == "WeeklyPeriod"
        assert notification.related_id == 1
        mock_ws.assert_called_once_with(notification)

    @patch("apps.notifications.services.NotificationService._send_ws_notification")
    def test_create_bulk_notifications(self, mock_ws):
        """إنشاء إشعارات متعددة لعدة مستلمين"""
        user1 = SectionManagerFactory()
        user2 = SectionManagerFactory()
        user3 = SectionManagerFactory()

        notifications = NotificationService.create_bulk_notifications(
            recipients=[user1, user2, user3],
            notification_type="submission_due",
            title="اقتراب الموعد النهائي",
            message="الموعد النهائي للإرسال يقترب",
            related_model="WeeklyPeriod",
            related_id=5,
        )

        assert len(notifications) == 3
        assert Notification.objects.filter(
            notification_type="submission_due"
        ).count() == 3
        assert mock_ws.call_count == 3


@pytest.mark.django_db
class TestNotificationServiceRead:
    """اختبارات تعليم الإشعارات كمقروءة"""

    def test_mark_as_read(self):
        """تعليم إشعار واحد كمقروء"""
        notification = NotificationFactory(is_read=False)
        assert notification.is_read is False

        NotificationService.mark_as_read(notification)

        notification.refresh_from_db()
        assert notification.is_read is True

    def test_mark_all_as_read(self):
        """تعليم جميع إشعارات المستخدم كمقروءة"""
        user = SectionManagerFactory()
        NotificationFactory(recipient=user, is_read=False)
        NotificationFactory(recipient=user, is_read=False)
        NotificationFactory(recipient=user, is_read=False)

        # إشعار لمستخدم آخر (يجب أن يبقى غير مقروء)
        other_user = SectionManagerFactory()
        other_notification = NotificationFactory(
            recipient=other_user, is_read=False
        )

        NotificationService.mark_all_as_read(user)

        assert Notification.objects.filter(
            recipient=user, is_read=False
        ).count() == 0
        assert Notification.objects.filter(
            recipient=user, is_read=True
        ).count() == 3

        # إشعار المستخدم الآخر لم يتأثر
        other_notification.refresh_from_db()
        assert other_notification.is_read is False

    def test_get_unread_count(self):
        """حساب عدد الإشعارات غير المقروءة"""
        user = SectionManagerFactory()
        NotificationFactory(recipient=user, is_read=False)
        NotificationFactory(recipient=user, is_read=False)
        NotificationFactory(recipient=user, is_read=True)

        count = NotificationService.get_unread_count(user)
        assert count == 2

    def test_get_unread_count_zero(self):
        """عدد الإشعارات غير المقروءة يساوي صفر عندما لا توجد إشعارات"""
        user = SectionManagerFactory()
        count = NotificationService.get_unread_count(user)
        assert count == 0
