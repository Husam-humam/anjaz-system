"""
اختبارات واجهة API لتطبيق الإشعارات.
"""
import pytest
from rest_framework.test import APIClient

from apps.accounts.tests.factories import SectionManagerFactory

from .factories import NotificationFactory


@pytest.mark.django_db
class TestNotificationListAPI:
    """اختبارات عرض قائمة الإشعارات"""

    def test_list_notifications(self, api_client):
        """عرض قائمة إشعارات المستخدم المصادَق"""
        user = SectionManagerFactory()
        NotificationFactory(recipient=user, title="إشعار أول")
        NotificationFactory(recipient=user, title="إشعار ثاني")

        api_client.force_authenticate(user)
        response = api_client.get("/api/notifications/")

        assert response.status_code == 200
        # التحقق من أن البيانات موجودة (مع أو بدون pagination)
        data = response.data.get("results", response.data)
        assert len(data) == 2

    def test_only_own_notifications(self, api_client):
        """المستخدم يرى إشعاراته فقط"""
        user1 = SectionManagerFactory()
        user2 = SectionManagerFactory()

        NotificationFactory(recipient=user1, title="إشعار المستخدم الأول")
        NotificationFactory(recipient=user2, title="إشعار المستخدم الثاني")

        api_client.force_authenticate(user1)
        response = api_client.get("/api/notifications/")

        assert response.status_code == 200
        data = response.data.get("results", response.data)
        assert len(data) == 1
        assert data[0]["title"] == "إشعار المستخدم الأول"

    def test_unauthenticated_returns_401(self):
        """الطلب بدون مصادقة يرجع 401"""
        client = APIClient()
        response = client.get("/api/notifications/")
        assert response.status_code == 401


@pytest.mark.django_db
class TestNotificationMarkReadAPI:
    """اختبارات تعليم الإشعارات كمقروءة عبر API"""

    def test_mark_read_endpoint(self, api_client):
        """تعليم إشعار واحد كمقروء"""
        user = SectionManagerFactory()
        notification = NotificationFactory(recipient=user, is_read=False)

        api_client.force_authenticate(user)
        response = api_client.post(
            f"/api/notifications/{notification.id}/read/"
        )

        assert response.status_code == 200
        notification.refresh_from_db()
        assert notification.is_read is True

    def test_mark_all_read_endpoint(self, api_client):
        """تعليم جميع الإشعارات كمقروءة"""
        user = SectionManagerFactory()
        NotificationFactory(recipient=user, is_read=False)
        NotificationFactory(recipient=user, is_read=False)
        NotificationFactory(recipient=user, is_read=False)

        api_client.force_authenticate(user)
        response = api_client.post("/api/notifications/read_all/")

        assert response.status_code == 200
        from apps.notifications.models import Notification
        unread = Notification.objects.filter(
            recipient=user, is_read=False
        ).count()
        assert unread == 0

    def test_unread_count_endpoint(self, api_client):
        """الحصول على عدد الإشعارات غير المقروءة"""
        user = SectionManagerFactory()
        NotificationFactory(recipient=user, is_read=False)
        NotificationFactory(recipient=user, is_read=False)
        NotificationFactory(recipient=user, is_read=True)

        api_client.force_authenticate(user)
        response = api_client.get("/api/notifications/unread_count/")

        assert response.status_code == 200
        assert response.data["count"] == 2

    def test_cannot_read_other_users_notification(self, api_client):
        """لا يمكن تعليم إشعار مستخدم آخر كمقروء"""
        user1 = SectionManagerFactory()
        user2 = SectionManagerFactory()
        notification = NotificationFactory(recipient=user2, is_read=False)

        api_client.force_authenticate(user1)
        response = api_client.post(
            f"/api/notifications/{notification.id}/read/"
        )
        # الإشعار لا يظهر ضمن queryset المستخدم فيرجع 404
        assert response.status_code == 404
