"""
اختبارات واجهة برمجة التطبيقات (API) لتطبيق الحسابات — المصادقة وإدارة المستخدمين.
"""
import pytest
from django.urls import reverse
from rest_framework import status

from apps.accounts.tests.factories import (
    StatisticsAdminFactory,
    PlanningSectionUserFactory,
    SectionManagerFactory,
)
from apps.organization.tests.factories import QismFactory


@pytest.mark.django_db
class TestLoginAPI:
    """اختبارات نقطة نهاية تسجيل الدخول"""

    def test_login_valid_credentials(self, api_client):
        """التحقق من تسجيل الدخول بنجاح مع بيانات اعتماد صحيحة"""
        user = StatisticsAdminFactory()

        url = reverse('auth:login')
        data = {
            'username': user.username,
            'password': 'password123',
        }
        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data
        assert 'refresh' in response.data
        assert 'user' in response.data
        assert response.data['user']['username'] == user.username

    def test_login_invalid_credentials(self, api_client):
        """التحقق من رفض تسجيل الدخول مع بيانات اعتماد خاطئة"""
        StatisticsAdminFactory(username='testuser')

        url = reverse('auth:login')
        data = {
            'username': 'testuser',
            'password': 'wrongpassword',
        }
        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'access' not in response.data

    def test_login_nonexistent_user(self, api_client):
        """التحقق من رفض تسجيل الدخول لمستخدم غير موجود"""
        url = reverse('auth:login')
        data = {
            'username': 'does_not_exist',
            'password': 'password123',
        }
        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_inactive_user(self, api_client):
        """التحقق من رفض تسجيل الدخول لمستخدم معطّل"""
        user = StatisticsAdminFactory(is_active=False)

        url = reverse('auth:login')
        data = {
            'username': user.username,
            'password': 'password123',
        }
        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestMeAPI:
    """اختبارات نقطة نهاية الملف الشخصي"""

    def test_me_endpoint_returns_user_profile(self, api_client):
        """التحقق من أن نقطة نهاية /me/ تُرجع معلومات المستخدم الحالي"""
        user = StatisticsAdminFactory()
        api_client.force_authenticate(user=user)

        url = reverse('auth:me')
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['username'] == user.username
        assert response.data['full_name'] == user.full_name
        assert response.data['role'] == user.role

    def test_me_endpoint_unauthenticated(self, api_client):
        """التحقق من رفض الوصول لنقطة نهاية /me/ بدون مصادقة"""
        url = reverse('auth:me')
        response = api_client.get(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestUserCRUDAPI:
    """اختبارات نقاط نهاية إدارة المستخدمين (CRUD)"""

    def test_create_user_admin_only(self, api_client):
        """التحقق من أن مدير الإحصاء فقط يستطيع إنشاء مستخدم جديد"""
        admin = StatisticsAdminFactory()
        api_client.force_authenticate(user=admin)

        qism = QismFactory()

        url = reverse('users:user-list')
        data = {
            'username': 'new_manager',
            'password': 'securepass123',
            'full_name': 'مدير قسم جديد',
            'role': 'section_manager',
            'unit': qism.pk,
        }
        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['username'] == 'new_manager'
        assert response.data['full_name'] == 'مدير قسم جديد'

    def test_create_user_non_admin_forbidden(self, api_client):
        """التحقق من رفض إنشاء مستخدم من مستخدم ليس مدير إحصاء"""
        manager = SectionManagerFactory()
        api_client.force_authenticate(user=manager)

        qism = QismFactory()

        url = reverse('users:user-list')
        data = {
            'username': 'unauthorized_user',
            'password': 'securepass123',
            'full_name': 'مستخدم غير مصرح',
            'role': 'section_manager',
            'unit': qism.pk,
        }
        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_user_planning_section_forbidden(self, api_client):
        """التحقق من رفض إنشاء مستخدم من مستخدم قسم التخطيط"""
        planner = PlanningSectionUserFactory()
        api_client.force_authenticate(user=planner)

        qism = QismFactory()

        url = reverse('users:user-list')
        data = {
            'username': 'unauthorized_planner',
            'password': 'securepass123',
            'full_name': 'مستخدم غير مصرح',
            'role': 'section_manager',
            'unit': qism.pk,
        }
        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_access_returns_401(self, api_client):
        """التحقق من رفض الوصول لنقاط نهاية المستخدمين بدون مصادقة"""
        url = reverse('users:user-list')
        response = api_client.get(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_users_admin_only(self, api_client):
        """التحقق من أن مدير الإحصاء يستطيع عرض قائمة المستخدمين"""
        admin = StatisticsAdminFactory()
        api_client.force_authenticate(user=admin)

        # إنشاء مستخدمين إضافيين
        SectionManagerFactory()
        PlanningSectionUserFactory()

        url = reverse('users:user-list')
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.data
        if isinstance(data, dict) and 'results' in data:
            results = data['results']
        else:
            results = data
        # على الأقل 3 مستخدمين: المدير + مدير قسم + مخطط
        assert len(results) >= 3


@pytest.mark.django_db
class TestResetPasswordAPI:
    """اختبارات نقطة نهاية إعادة تعيين كلمة المرور"""

    def test_reset_password_endpoint(self, api_client):
        """التحقق من نجاح إعادة تعيين كلمة المرور عبر الـ API"""
        admin = StatisticsAdminFactory()
        api_client.force_authenticate(user=admin)

        target_user = SectionManagerFactory()

        url = reverse(
            'users:user-reset-password',
            kwargs={'pk': target_user.pk},
        )
        data = {'new_password': 'newsecurepass456'}
        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_200_OK
        target_user.refresh_from_db()
        assert target_user.check_password('newsecurepass456')

    def test_reset_password_non_admin_forbidden(self, api_client):
        """التحقق من رفض إعادة تعيين كلمة المرور من مستخدم غير مدير الإحصاء"""
        manager = SectionManagerFactory()
        api_client.force_authenticate(user=manager)

        target_user = SectionManagerFactory()

        url = reverse(
            'users:user-reset-password',
            kwargs={'pk': target_user.pk},
        )
        data = {'new_password': 'newsecurepass456'}
        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_reset_password_unauthenticated(self, api_client):
        """التحقق من رفض إعادة تعيين كلمة المرور بدون مصادقة"""
        target_user = SectionManagerFactory()

        url = reverse(
            'users:user-reset-password',
            kwargs={'pk': target_user.pk},
        )
        data = {'new_password': 'newsecurepass456'}
        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
