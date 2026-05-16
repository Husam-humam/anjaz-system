"""
اختبارات الـ smoke لنقاط النهاية الجديدة في Phase G:
- POST /api/organization/units/sync/
- PlanningAssignmentViewSet (+ supervised-units custom actions)
- ViewScopeViewSet
- ExternalUnitTypeMappingViewSet (+ refresh action)

كل اختبار يركّز على سيناريو واحد (happy-path أو رفض صلاحيّة).
نُموَك العميل الخارجي لتفادي الاتصال الفعلي بالشبكة.
"""
from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.tests.factories import (
    PlanningSectionUserFactory,
    StatisticsAdminFactory,
    ViewerFactory,
)
from apps.organization.integrations import ExternalOrgClient
from apps.organization.models import (
    ExternalUnitTypeMapping,
    PlanningAssignment,
    SupervisedUnit,
    ViewScope,
)
from apps.organization.tests.factories import (
    PlanningQismFactory,
    QismFactory,
)


def _mock_client(tree=None, flat_pages=None):
    """يبني MagicMock لـ ExternalOrgClient — نفس النمط في test_sync_service.py."""
    client = MagicMock(spec=ExternalOrgClient)
    client.is_configured.return_value = True
    client.assert_configured.return_value = None
    client.get_units_tree.return_value = tree or []
    if flat_pages is None:
        flat_pages = [{'results': [], 'pages': 1, 'count': 0}]
    client.get_units_list.side_effect = flat_pages
    return client


@pytest.fixture
def api_client():
    return APIClient()


# ═══════════════════════════════════════════════════════════════
# 1) sync endpoint على OrganizationUnitViewSet
# ═══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestSyncEndpoint:
    """POST /api/organization/units/sync/"""

    def test_admin_can_trigger_sync(self, api_client):
        admin = StatisticsAdminFactory()
        api_client.force_authenticate(user=admin)
        url = reverse('organization-unit-sync-from-external')

        # نُموَك المُنشئ — السرفيس يستدعي ExternalOrgClient() داخلياً
        mock = _mock_client()
        with patch(
            'apps.organization.sync_service.ExternalOrgClient',
            return_value=mock,
        ):
            response = api_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        # التقرير يحوي مفاتيح أساسيّة
        assert 'created' in response.data
        assert 'updated' in response.data
        assert 'deactivated' in response.data
        assert 'summary' in response.data

    def test_planner_cannot_trigger_sync(self, api_client):
        planner = PlanningSectionUserFactory()
        api_client.force_authenticate(user=planner)
        url = reverse('organization-unit-sync-from-external')

        response = api_client.post(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN


# ═══════════════════════════════════════════════════════════════
# 2) PlanningAssignmentViewSet
# ═══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestPlanningAssignmentViewSet:
    """CRUD + supervised-units sub-actions."""

    def test_admin_can_create_assignment(self, api_client):
        admin = StatisticsAdminFactory()
        api_client.force_authenticate(user=admin)
        planning_unit = PlanningQismFactory()

        url = reverse('planning-assignment-list')
        response = api_client.post(
            url,
            {'planning_unit': planning_unit.id, 'notes': 'تجريبي'},
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert PlanningAssignment.objects.filter(
            planning_unit=planning_unit
        ).exists()

    def test_admin_can_list_assignments(self, api_client):
        admin = StatisticsAdminFactory()
        api_client.force_authenticate(user=admin)
        PlanningAssignment.objects.create(planning_unit=PlanningQismFactory())

        url = reverse('planning-assignment-list')
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        results = response.data.get('results', response.data)
        assert len(results) >= 1

    def test_admin_can_add_supervised_unit(self, api_client):
        admin = StatisticsAdminFactory()
        api_client.force_authenticate(user=admin)
        assignment = PlanningAssignment.objects.create(
            planning_unit=PlanningQismFactory()
        )
        unit = QismFactory()

        url = reverse(
            'planning-assignment-add-supervised-unit', kwargs={'pk': assignment.pk}
        )
        response = api_client.post(url, {'unit': unit.id}, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert SupervisedUnit.objects.filter(
            assignment=assignment, unit=unit
        ).exists()

    def test_add_already_supervised_unit_returns_409(self, api_client):
        admin = StatisticsAdminFactory()
        api_client.force_authenticate(user=admin)
        assignment = PlanningAssignment.objects.create(
            planning_unit=PlanningQismFactory()
        )
        unit = QismFactory()
        SupervisedUnit.objects.create(assignment=assignment, unit=unit)

        url = reverse(
            'planning-assignment-add-supervised-unit', kwargs={'pk': assignment.pk}
        )
        response = api_client.post(url, {'unit': unit.id}, format='json')

        assert response.status_code == status.HTTP_409_CONFLICT

    def test_admin_can_remove_supervised_unit(self, api_client):
        admin = StatisticsAdminFactory()
        api_client.force_authenticate(user=admin)
        assignment = PlanningAssignment.objects.create(
            planning_unit=PlanningQismFactory()
        )
        unit = QismFactory()
        SupervisedUnit.objects.create(assignment=assignment, unit=unit)

        url = reverse(
            'planning-assignment-remove-supervised-unit',
            kwargs={'pk': assignment.pk, 'unit_id': unit.pk},
        )
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not SupervisedUnit.objects.filter(
            assignment=assignment, unit=unit
        ).exists()

    def test_admin_can_delete_assignment(self, api_client):
        admin = StatisticsAdminFactory()
        api_client.force_authenticate(user=admin)
        assignment = PlanningAssignment.objects.create(
            planning_unit=PlanningQismFactory()
        )

        url = reverse(
            'planning-assignment-detail', kwargs={'pk': assignment.pk}
        )
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not PlanningAssignment.objects.filter(pk=assignment.pk).exists()

    def test_planner_cannot_create_assignment(self, api_client):
        planner = PlanningSectionUserFactory()
        api_client.force_authenticate(user=planner)
        planning_unit = PlanningQismFactory()

        url = reverse('planning-assignment-list')
        response = api_client.post(
            url, {'planning_unit': planning_unit.id}, format='json',
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


# ═══════════════════════════════════════════════════════════════
# 3) ViewScopeViewSet
# ═══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestViewScopeViewSet:

    def test_admin_can_create_view_scope(self, api_client):
        admin = StatisticsAdminFactory()
        api_client.force_authenticate(user=admin)
        viewer = ViewerFactory()
        q1 = QismFactory()
        q2 = QismFactory()

        url = reverse('view-scope-list')
        response = api_client.post(
            url,
            {'user': viewer.id, 'viewable_units': [q1.id, q2.id]},
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        scope = ViewScope.objects.get(user=viewer)
        assert set(scope.viewable_units.values_list('id', flat=True)) == {
            q1.id, q2.id
        }

    def test_admin_can_update_viewable_units(self, api_client):
        admin = StatisticsAdminFactory()
        api_client.force_authenticate(user=admin)
        viewer = ViewerFactory()
        q1 = QismFactory()
        q2 = QismFactory()
        scope = ViewScope.objects.create(user=viewer)
        scope.viewable_units.add(q1)

        url = reverse('view-scope-detail', kwargs={'pk': scope.pk})
        response = api_client.patch(
            url, {'viewable_units': [q2.id]}, format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        scope.refresh_from_db()
        assert set(scope.viewable_units.values_list('id', flat=True)) == {q2.id}

    def test_planner_cannot_create_view_scope(self, api_client):
        planner = PlanningSectionUserFactory()
        api_client.force_authenticate(user=planner)
        viewer = ViewerFactory()

        url = reverse('view-scope-list')
        response = api_client.post(
            url, {'user': viewer.id, 'viewable_units': []}, format='json',
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


# ═══════════════════════════════════════════════════════════════
# 4) ExternalUnitTypeMappingViewSet
# ═══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestExternalUnitTypeMappingViewSet:

    def test_admin_can_list_mappings(self, api_client):
        admin = StatisticsAdminFactory()
        api_client.force_authenticate(user=admin)

        url = reverse('unit-type-mapping-list')
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK

    def test_admin_can_patch_treat_as(self, api_client):
        admin = StatisticsAdminFactory()
        api_client.force_authenticate(user=admin)
        mapping = ExternalUnitTypeMapping.objects.create(
            external_type_name='نوع جديد', treat_as=None,
        )

        url = reverse('unit-type-mapping-detail', kwargs={'pk': mapping.pk})
        response = api_client.patch(
            url, {'treat_as': 'qism'}, format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        mapping.refresh_from_db()
        assert mapping.treat_as == 'qism'

    def test_admin_refresh_creates_mappings(self, api_client):
        admin = StatisticsAdminFactory()
        api_client.force_authenticate(user=admin)

        mock = MagicMock(spec=ExternalOrgClient)
        mock.is_configured.return_value = True
        mock.assert_configured.return_value = None
        mock.get_unit_types.return_value = [
            {'id': 1, 'name': 'دائرة'},
            {'id': 2, 'name': 'قسم'},
        ]

        url = reverse('unit-type-mapping-refresh-from-external')
        with patch(
            'apps.organization.sync_service.ExternalOrgClient',
            return_value=mock,
        ):
            response = api_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['created'] == 2
        assert ExternalUnitTypeMapping.objects.filter(
            external_type_name='دائرة'
        ).exists()

    def test_admin_cannot_delete_mapping(self, api_client):
        admin = StatisticsAdminFactory()
        api_client.force_authenticate(user=admin)
        mapping = ExternalUnitTypeMapping.objects.create(
            external_type_name='للحذف',
        )

        url = reverse('unit-type-mapping-detail', kwargs={'pk': mapping.pk})
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_planner_cannot_patch_mapping(self, api_client):
        planner = PlanningSectionUserFactory()
        api_client.force_authenticate(user=planner)
        mapping = ExternalUnitTypeMapping.objects.create(
            external_type_name='ممنوع',
        )

        url = reverse('unit-type-mapping-detail', kwargs={'pk': mapping.pk})
        response = api_client.patch(
            url, {'treat_as': 'qism'}, format='json',
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
