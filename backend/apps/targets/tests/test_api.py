"""
اختبارات واجهات API للمستهدفات.
"""
import pytest
from django.urls import reverse

from apps.targets.tests.factories import TargetFactory
from apps.indicators.tests.factories import IndicatorFactory
from apps.organization.tests.factories import QismFactory
from apps.accounts.tests.factories import (
    StatisticsAdminFactory,
    PlanningSectionUserFactory,
    SectionManagerFactory,
)


@pytest.mark.django_db
class TestTargetAPI:
    """اختبارات واجهة API للمستهدفات"""

    def test_list_targets(self, api_client):
        """اختبار عرض قائمة المستهدفات للمستخدم المصادق عليه"""
        admin = StatisticsAdminFactory()
        TargetFactory.create_batch(3)

        api_client.force_authenticate(user=admin)
        url = reverse('target-list')
        response = api_client.get(url)

        assert response.status_code == 200
        assert len(response.data['results']) == 3

    def test_create_target_admin_only(self, api_client):
        """اختبار أن إنشاء مستهدف مسموح فقط لمدير الإحصاء"""
        admin = StatisticsAdminFactory()
        qism = QismFactory()
        indicator = IndicatorFactory()

        api_client.force_authenticate(user=admin)
        url = reverse('target-list')
        data = {
            'qism': qism.pk,
            'indicator': indicator.pk,
            'year': 2025,
            'target_value': 100.0,
            'notes': '',
        }
        response = api_client.post(url, data=data, format='json')

        assert response.status_code == 201
        assert response.data['target_value'] == 100.0

    def test_non_admin_cannot_create_target(self, api_client):
        """اختبار أن غير مدير الإحصاء لا يمكنه إنشاء مستهدف"""
        planner = PlanningSectionUserFactory()
        qism = QismFactory()
        indicator = IndicatorFactory()

        api_client.force_authenticate(user=planner)
        url = reverse('target-list')
        data = {
            'qism': qism.pk,
            'indicator': indicator.pk,
            'year': 2025,
            'target_value': 100.0,
        }
        response = api_client.post(url, data=data, format='json')

        assert response.status_code == 403

    def test_section_manager_cannot_create_target(self, api_client):
        """اختبار أن مدير القسم لا يمكنه إنشاء مستهدف"""
        manager = SectionManagerFactory()
        qism = QismFactory()
        indicator = IndicatorFactory()

        api_client.force_authenticate(user=manager)
        url = reverse('target-list')
        data = {
            'qism': qism.pk,
            'indicator': indicator.pk,
            'year': 2025,
            'target_value': 50.0,
        }
        response = api_client.post(url, data=data, format='json')

        assert response.status_code == 403

    def test_unauthenticated_returns_401(self, api_client):
        """اختبار أن الطلبات غير المصادق عليها ترجع 401"""
        url = reverse('target-list')
        response = api_client.get(url)

        assert response.status_code in (401, 403)

    def test_planner_can_read_targets(self, api_client):
        """اختبار أن قسم التخطيط يمكنه قراءة المستهدفات"""
        mudiriya = QismFactory().parent  # الحصول على المديرية
        planner = PlanningSectionUserFactory(unit__parent=mudiriya)
        qism = QismFactory(parent=mudiriya)
        TargetFactory(qism=qism, year=2025)

        api_client.force_authenticate(user=planner)
        url = reverse('target-list')
        response = api_client.get(url)

        assert response.status_code == 200
