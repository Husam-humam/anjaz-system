"""
اختبارات واجهات API للمستهدفات.
"""
import pytest
from django.urls import reverse

from apps.accounts.tests.factories import (
    PlanningSectionUserFactory,
    SectionManagerFactory,
    StatisticsAdminFactory,
)
from apps.indicators.tests.factories import IndicatorFactory
from apps.organization.tests.factories import (
    DairaFactory,
    MudiriyaFactory,
    QismFactory,
    SupervisedQismFactory,
)
from apps.targets.tests.factories import TargetFactory


@pytest.mark.django_db
class TestTargetAPI:
    """اختبارات واجهة API للمستهدفات الهرمية"""

    def test_list_targets(self, api_client):
        admin = StatisticsAdminFactory()
        for _ in range(3):
            TargetFactory(scope_unit=SupervisedQismFactory())

        api_client.force_authenticate(user=admin)
        url = reverse('target-list')
        response = api_client.get(url)

        assert response.status_code == 200
        assert len(response.data['results']) == 3

    def test_create_qism_target_admin(self, api_client):
        """إنشاء مستهدف على مستوى قسم"""
        admin = StatisticsAdminFactory()
        qism = SupervisedQismFactory()
        indicator = IndicatorFactory(
            unit_type="number", accumulation_type="sum"
        )

        api_client.force_authenticate(user=admin)
        url = reverse('target-list')
        data = {
            'scope_unit': qism.pk,
            'indicator': indicator.pk,
            'year': 2026,
            'target_value': 100.0,
            'notes': '',
        }
        response = api_client.post(url, data=data, format='json')

        assert response.status_code == 201
        assert response.data['target_value'] == 100.0
        assert response.data['scope_level'] == 'qism'

    def test_create_institution_target(self, api_client):
        """إنشاء مستهدف على مستوى المؤسسة (scope_unit=None)"""
        admin = StatisticsAdminFactory()
        indicator = IndicatorFactory(
            unit_type="number", accumulation_type="sum"
        )

        api_client.force_authenticate(user=admin)
        url = reverse('target-list')
        data = {
            'scope_unit': None,
            'indicator': indicator.pk,
            'year': 2026,
            'target_value': 1000.0,
        }
        response = api_client.post(url, data=data, format='json')

        assert response.status_code == 201
        assert response.data['scope_level'] == 'institution'
        assert response.data['scope_unit'] is None

    def test_create_daira_target(self, api_client):
        """إنشاء مستهدف على مستوى دائرة"""
        admin = StatisticsAdminFactory()
        daira = DairaFactory()
        indicator = IndicatorFactory(
            unit_type="number", accumulation_type="sum"
        )

        api_client.force_authenticate(user=admin)
        url = reverse('target-list')
        data = {
            'scope_unit': daira.pk,
            'indicator': indicator.pk,
            'year': 2026,
            'target_value': 400.0,
        }
        response = api_client.post(url, data=data, format='json')

        assert response.status_code == 201
        assert response.data['scope_level'] == 'daira'

    def test_non_admin_cannot_create_target(self, api_client):
        """غير مدير الإحصاء لا يمكنه إنشاء مستهدف"""
        planner = PlanningSectionUserFactory()
        qism = QismFactory()
        indicator = IndicatorFactory()

        api_client.force_authenticate(user=planner)
        url = reverse('target-list')
        data = {
            'scope_unit': qism.pk,
            'indicator': indicator.pk,
            'year': 2026,
            'target_value': 100.0,
        }
        response = api_client.post(url, data=data, format='json')
        assert response.status_code == 403

    def test_section_manager_cannot_create_target(self, api_client):
        manager = SectionManagerFactory()
        qism = QismFactory()
        indicator = IndicatorFactory()

        api_client.force_authenticate(user=manager)
        url = reverse('target-list')
        data = {
            'scope_unit': qism.pk,
            'indicator': indicator.pk,
            'year': 2026,
            'target_value': 50.0,
        }
        response = api_client.post(url, data=data, format='json')
        assert response.status_code == 403

    def test_unauthenticated_returns_401(self, api_client):
        url = reverse('target-list')
        response = api_client.get(url)
        assert response.status_code in (401, 403)

    def test_filter_by_scope_level(self, api_client):
        """فلترة حسب scope_level (daira/mudiriya/qism/institution)"""
        admin = StatisticsAdminFactory()
        daira = DairaFactory()
        mudiriya = MudiriyaFactory()
        indicator = IndicatorFactory(
            unit_type="number", accumulation_type="sum"
        )

        TargetFactory(scope_unit=None, indicator=indicator, year=2026)
        TargetFactory(scope_unit=daira, indicator=indicator, year=2026)
        TargetFactory(scope_unit=mudiriya, indicator=indicator, year=2026)
        TargetFactory(scope_unit=SupervisedQismFactory(), indicator=indicator, year=2026)

        api_client.force_authenticate(user=admin)
        url = reverse('target-list')

        # institution
        response = api_client.get(url, {'scope_level': 'institution'})
        assert response.status_code == 200
        assert len(response.data['results']) == 1

        # daira
        response = api_client.get(url, {'scope_level': 'daira'})
        assert len(response.data['results']) == 1

    def test_progress_action(self, api_client):
        """نقطة /targets/{id}/progress/ تُرجع حساب التقدم"""
        admin = StatisticsAdminFactory()
        target = TargetFactory(scope_unit=SupervisedQismFactory(), target_value=200)

        api_client.force_authenticate(user=admin)
        url = reverse('target-progress', kwargs={'pk': target.pk})
        response = api_client.get(url)

        assert response.status_code == 200
        assert 'cumulative_value' in response.data
        assert 'progress_percentage' in response.data
        assert response.data['target_value'] == 200

    def test_breakdown_action_for_mudiriya(self, api_client):
        """
        نقطة /targets/{id}/breakdown/ تُرجع شجرة تفصيل.
        لمستهدف مديرية: الجذور = أقسام المديرية المباشرة.
        """
        admin = StatisticsAdminFactory()
        mudiriya = MudiriyaFactory()
        q1 = SupervisedQismFactory(parent=mudiriya)
        q2 = SupervisedQismFactory(parent=mudiriya)
        indicator = IndicatorFactory(
            unit_type="number", accumulation_type="sum"
        )
        target = TargetFactory(
            scope_unit=mudiriya, indicator=indicator,
            year=2026, target_value=100,
        )

        api_client.force_authenticate(user=admin)
        url = reverse('target-breakdown', kwargs={'pk': target.pk})
        response = api_client.get(url)

        assert response.status_code == 200
        assert 'breakdown' in response.data
        assert response.data['breakdown_type'] == 'tree'
        # في شجرة مستهدف مديرية، الجذور = أقسام المديرية
        ids = {row['unit_id'] for row in response.data['breakdown']}
        assert q1.id in ids
        assert q2.id in ids

    def test_breakdown_for_qism_target_is_empty(self, api_client):
        """مستهدف قسم يُرجع تفصيلاً فارغاً"""
        admin = StatisticsAdminFactory()
        target = TargetFactory(scope_unit=SupervisedQismFactory())  # الافتراضي قسم

        api_client.force_authenticate(user=admin)
        url = reverse('target-breakdown', kwargs={'pk': target.pk})
        response = api_client.get(url)

        assert response.status_code == 200
        assert response.data['breakdown'] == []
