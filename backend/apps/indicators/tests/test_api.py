"""
اختبارات واجهات API للمؤشرات وتصنيفاتها.
"""
import pytest
from django.urls import reverse

from apps.indicators.tests.factories import IndicatorCategoryFactory, IndicatorFactory
from apps.accounts.tests.factories import (
    StatisticsAdminFactory,
    PlanningSectionUserFactory,
    SectionManagerFactory,
)


@pytest.mark.django_db
class TestIndicatorAPI:
    """اختبارات واجهة API للمؤشرات"""

    def test_list_indicators(self, api_client):
        """اختبار عرض قائمة المؤشرات للمستخدم المصادق عليه"""
        user = StatisticsAdminFactory()
        IndicatorFactory.create_batch(3)

        api_client.force_authenticate(user=user)
        url = reverse('indicator-list')
        response = api_client.get(url)

        assert response.status_code == 200
        assert len(response.data['results']) == 3

    def test_create_indicator_admin_only(self, api_client):
        """اختبار أن إنشاء مؤشر مسموح فقط لمدير الإحصاء"""
        admin = StatisticsAdminFactory()
        category = IndicatorCategoryFactory()

        api_client.force_authenticate(user=admin)
        url = reverse('indicator-list')
        data = {
            'name': 'مؤشر جديد',
            'unit_type': 'number',
            'unit_label': 'وحدة',
            'accumulation_type': 'sum',
            'category': category.pk,
        }
        response = api_client.post(url, data=data, format='json')

        assert response.status_code == 201
        assert response.data['name'] == 'مؤشر جديد'

    def test_non_admin_cannot_create_indicator(self, api_client):
        """اختبار أن غير مدير الإحصاء لا يمكنه إنشاء مؤشر"""
        planner = PlanningSectionUserFactory()
        category = IndicatorCategoryFactory()

        api_client.force_authenticate(user=planner)
        url = reverse('indicator-list')
        data = {
            'name': 'مؤشر غير مصرح',
            'unit_type': 'number',
            'unit_label': 'وحدة',
            'accumulation_type': 'sum',
            'category': category.pk,
        }
        response = api_client.post(url, data=data, format='json')

        assert response.status_code == 403

    def test_section_manager_cannot_create_indicator(self, api_client):
        """اختبار أن مدير القسم لا يمكنه إنشاء مؤشر"""
        manager = SectionManagerFactory()
        category = IndicatorCategoryFactory()

        api_client.force_authenticate(user=manager)
        url = reverse('indicator-list')
        data = {
            'name': 'مؤشر غير مصرح',
            'unit_type': 'number',
            'unit_label': 'وحدة',
            'accumulation_type': 'sum',
            'category': category.pk,
        }
        response = api_client.post(url, data=data, format='json')

        assert response.status_code == 403

    def test_unauthenticated_returns_401(self, api_client):
        """اختبار أن الطلبات غير المصادق عليها ترجع 401"""
        url = reverse('indicator-list')
        response = api_client.get(url)

        assert response.status_code in (401, 403)


@pytest.mark.django_db
class TestIndicatorCategoryAPI:
    """اختبارات واجهة API لتصنيفات المؤشرات"""

    def test_list_categories(self, api_client):
        """اختبار عرض قائمة التصنيفات"""
        user = StatisticsAdminFactory()
        IndicatorCategoryFactory.create_batch(3)

        api_client.force_authenticate(user=user)
        url = reverse('indicator-category-list')
        response = api_client.get(url)

        assert response.status_code == 200
        assert len(response.data['results']) == 3

    def test_create_category_admin_only(self, api_client):
        """اختبار أن إنشاء تصنيف مسموح فقط لمدير الإحصاء"""
        admin = StatisticsAdminFactory()

        api_client.force_authenticate(user=admin)
        url = reverse('indicator-category-list')
        data = {'name': 'تصنيف اختبار'}
        response = api_client.post(url, data=data, format='json')

        assert response.status_code == 201

    def test_non_admin_cannot_create_category(self, api_client):
        """اختبار أن غير مدير الإحصاء لا يمكنه إنشاء تصنيف"""
        planner = PlanningSectionUserFactory()

        api_client.force_authenticate(user=planner)
        url = reverse('indicator-category-list')
        data = {'name': 'تصنيف غير مصرح'}
        response = api_client.post(url, data=data, format='json')

        assert response.status_code == 403

    def test_unauthenticated_returns_401(self, api_client):
        """اختبار أن الطلبات غير المصادق عليها ترجع 401"""
        url = reverse('indicator-category-list')
        response = api_client.get(url)

        assert response.status_code in (401, 403)
