"""
اختبارات واجهة برمجة التطبيقات (API) لتطبيق الهيكل التنظيمي.
"""
import pytest
from django.urls import reverse
from rest_framework import status

from apps.organization.tests.factories import (
    DairaFactory,
    MudiriyaFactory,
    QismFactory,
)
from apps.accounts.tests.factories import (
    StatisticsAdminFactory,
    PlanningSectionUserFactory,
    SectionManagerFactory,
)


@pytest.mark.django_db
class TestOrganizationUnitListAPI:
    """اختبارات نقطة نهاية قائمة الكيانات التنظيمية"""

    def test_list_units_authenticated(self, api_client):
        """التحقق من أن المستخدم المُصادق عليه يستطيع عرض قائمة الكيانات"""
        admin = StatisticsAdminFactory()
        api_client.force_authenticate(user=admin)

        DairaFactory()
        DairaFactory()

        url = reverse('organization-unit-list')
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        # التحقق من وجود نتائج (قد تحتوي على pagination)
        data = response.data
        if isinstance(data, dict) and 'results' in data:
            results = data['results']
        else:
            results = data
        # الكيانات المُنشأة + الكيانات التي أنشأها المصنع التابع لوحدة المدير
        assert len(results) >= 2

    def test_unauthenticated_access_returns_401(self, api_client):
        """التحقق من رفض الوصول للمستخدم غير المُصادق عليه"""
        url = reverse('organization-unit-list')
        response = api_client.get(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestOrganizationUnitCreateAPI:
    """اختبارات نقطة نهاية إنشاء كيان تنظيمي"""

    def test_create_unit_admin_only(self, api_client):
        """التحقق من أن مدير الإحصاء فقط يستطيع إنشاء كيان تنظيمي"""
        admin = StatisticsAdminFactory()
        api_client.force_authenticate(user=admin)

        url = reverse('organization-unit-list')
        data = {
            'name': 'دائرة جديدة',
            'code': 'DNEW',
            'unit_type': 'daira',
        }
        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == 'دائرة جديدة'
        assert response.data['code'] == 'DNEW'

    def test_create_unit_non_admin_forbidden(self, api_client):
        """التحقق من رفض إنشاء كيان من مستخدم غير مدير الإحصاء"""
        section_manager = SectionManagerFactory()
        api_client.force_authenticate(user=section_manager)

        url = reverse('organization-unit-list')
        data = {
            'name': 'دائرة غير مصرح بها',
            'code': 'DUNAUTH',
            'unit_type': 'daira',
        }
        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_unit_planning_section_forbidden(self, api_client):
        """التحقق من رفض إنشاء كيان من مستخدم قسم التخطيط"""
        planner = PlanningSectionUserFactory()
        api_client.force_authenticate(user=planner)

        url = reverse('organization-unit-list')
        data = {
            'name': 'دائرة غير مصرح بها',
            'code': 'DPLAN',
            'unit_type': 'daira',
        }
        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestOrganizationUnitTreeAPI:
    """اختبارات نقطة نهاية شجرة الهيكل التنظيمي"""

    def test_tree_endpoint(self, api_client):
        """التحقق من أن نقطة نهاية الشجرة تُرجع الكيانات الجذرية مع الأبناء"""
        admin = StatisticsAdminFactory()
        api_client.force_authenticate(user=admin)

        daira = DairaFactory()
        mudiriya = MudiriyaFactory(parent=daira)
        QismFactory(parent=mudiriya)

        url = reverse('organization-unit-tree')
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, list)
        # التحقق من أن الشجرة تحتوي على الدائرة كجذر
        # (قد تحتوي أيضاً على وحدة المدير التي أنشأها المصنع)
        root_names = [unit['name'] for unit in response.data]
        assert daira.name in root_names


@pytest.mark.django_db
class TestOrganizationUnitDeactivateAPI:
    """اختبارات نقطة نهاية تعطيل كيان تنظيمي"""

    def test_deactivate_unit_admin_only(self, api_client):
        """التحقق من أن مدير الإحصاء يستطيع تعطيل كيان (حذف ناعم)"""
        admin = StatisticsAdminFactory()
        api_client.force_authenticate(user=admin)

        qism = QismFactory()

        url = reverse('organization-unit-detail', kwargs={'pk': qism.pk})
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        qism.refresh_from_db()
        # perform_destroy يستدعي deactivate_unit الذي يضع is_active=False
        assert qism.is_active is False

    def test_deactivate_unit_non_admin_forbidden(self, api_client):
        """التحقق من رفض تعطيل كيان من مستخدم غير مدير الإحصاء"""
        manager = SectionManagerFactory()
        api_client.force_authenticate(user=manager)

        qism = QismFactory()

        url = reverse('organization-unit-detail', kwargs={'pk': qism.pk})
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_deactivate_unit_with_active_children_fails(self, api_client):
        """التحقق من رفض تعطيل كيان له كيانات فرعية نشطة عبر الـ API"""
        admin = StatisticsAdminFactory()
        api_client.force_authenticate(user=admin)

        daira = DairaFactory()
        MudiriyaFactory(parent=daira, is_active=True)

        url = reverse('organization-unit-detail', kwargs={'pk': daira.pk})
        response = api_client.delete(url)

        # ValidationError من الخدمة يجب أن يتحول إلى خطأ HTTP
        assert response.status_code in (
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
        daira.refresh_from_db()
        assert daira.is_active is True
