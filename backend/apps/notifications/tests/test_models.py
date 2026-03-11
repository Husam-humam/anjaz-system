"""
اختبارات نماذج تطبيق الإشعارات.
"""
import pytest

from apps.accounts.tests.factories import SectionManagerFactory

from .factories import NotificationFactory


@pytest.mark.django_db
class TestNotificationModel:
    """اختبارات نموذج الإشعار"""

    def test_notification_str(self):
        """__str__ يرجع العنوان واسم المستلم"""
        notification = NotificationFactory(title="فتح أسبوع جديد")
        result = str(notification)
        assert "فتح أسبوع جديد" in result
        assert str(notification.recipient) in result

    def test_notification_default_unread(self):
        """الإشعار يُنشأ كغير مقروء افتراضياً"""
        notification = NotificationFactory()
        assert notification.is_read is False

    def test_notification_ordering(self):
        """الإشعارات مرتبة تنازلياً حسب تاريخ الإنشاء"""
        user = SectionManagerFactory()
        n1 = NotificationFactory(recipient=user, title="الأول")
        n2 = NotificationFactory(recipient=user, title="الثاني")
        n3 = NotificationFactory(recipient=user, title="الثالث")

        from apps.notifications.models import Notification
        notifications = list(
            Notification.objects.filter(recipient=user)
        )
        # الترتيب التنازلي: الأحدث أولاً
        assert notifications[0].id == n3.id
        assert notifications[-1].id == n1.id

    def test_notification_type_choices(self):
        """التحقق من إنشاء إشعارات بأنواع مختلفة"""
        notification = NotificationFactory(
            notification_type="submission_received"
        )
        assert notification.notification_type == "submission_received"

    def test_notification_created_at_auto(self):
        """تاريخ الإنشاء يُملأ تلقائياً"""
        notification = NotificationFactory()
        assert notification.created_at is not None
