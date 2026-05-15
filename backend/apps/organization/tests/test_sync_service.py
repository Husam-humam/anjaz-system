"""
اختبارات OrganizationSyncService.

نُموَّك ExternalOrgClient لتجنّب الاتصال الفعلي بالشبكة.
كل اختبار يفحص سيناريو محدّداً من سيناريوهات المزامنة.
"""
from unittest.mock import MagicMock

import pytest

from apps.organization.integrations import ExternalOrgClient
from apps.organization.models import OrganizationUnit, UnitType
from apps.organization.sync_service import (
    DEFAULT_UNIT_TYPE_MAP,
    OrganizationSyncService,
)


def make_mock_client(tree=None, flat_pages=None):
    """يصنع mock client بشجرة وقائمة مسطّحة محدّدتَين."""
    client = MagicMock(spec=ExternalOrgClient)
    client.is_configured.return_value = True
    client.assert_configured.return_value = None
    client.get_units_tree.return_value = tree or []
    # get_units_list يُرجع dict بـ results/pages/count
    if flat_pages is None:
        flat_pages = [{'results': [], 'pages': 1, 'count': 0}]
    client.get_units_list.side_effect = flat_pages
    return client


def build_flat(units):
    """يبني صفحة واحدة من الردّ المسطّح."""
    return {'results': units, 'pages': 1, 'count': len(units)}


@pytest.mark.django_db
class TestSyncServiceCreate:
    """سيناريوهات إنشاء وحدات جديدة."""

    def test_create_single_daira(self):
        tree = [{'id': 100, 'name': 'دائرة أ', 'children': None}]
        flat = build_flat([
            {'id': 100, 'name': 'دائرة أ', 'code': 'D001',
             'unit_type_name': 'دائرة', 'is_active': True}
        ])
        service = OrganizationSyncService(client=make_mock_client(tree, [flat]))

        report = service.sync()

        assert report.created == 1
        assert report.updated == 0
        assert report.errors == []
        unit = OrganizationUnit.objects.get(external_id=100)
        assert unit.name == 'دائرة أ'
        assert unit.code == 'D001'
        assert unit.unit_type == UnitType.DAIRA
        assert unit.parent is None
        assert unit.external_synced_at is not None

    def test_create_full_tree_with_parents(self):
        """دائرة → مديرية → قسم — تربيط parent يعمل."""
        tree = [{
            'id': 1, 'name': 'دائرة الإدارة', 'children': [
                {'id': 2, 'name': 'مديرية HR', 'children': [
                    {'id': 3, 'name': 'قسم التوظيف', 'children': None},
                ]},
            ],
        }]
        flat = build_flat([
            {'id': 1, 'name': 'دائرة الإدارة', 'code': 'D1',
             'unit_type_name': 'دائرة', 'is_active': True},
            {'id': 2, 'name': 'مديرية HR', 'code': 'M1',
             'unit_type_name': 'مديرية', 'is_active': True},
            {'id': 3, 'name': 'قسم التوظيف', 'code': 'Q1',
             'unit_type_name': 'قسم', 'is_active': True},
        ])
        service = OrganizationSyncService(client=make_mock_client(tree, [flat]))

        report = service.sync()

        assert report.created == 3
        daira = OrganizationUnit.objects.get(external_id=1)
        mudiriya = OrganizationUnit.objects.get(external_id=2)
        qism = OrganizationUnit.objects.get(external_id=3)
        assert daira.parent is None
        assert mudiriya.parent_id == daira.pk
        assert qism.parent_id == mudiriya.pk


@pytest.mark.django_db
class TestSyncServiceUpdate:
    """سيناريوهات تحديث وحدات موجودة."""

    def test_update_changes_name_and_code(self):
        # وحدة موجودة من مزامنة سابقة (نستخدم daira لتفادي clean() قواعد parent)
        existing = OrganizationUnit.objects.create(
            external_id=50, name='اسم قديم', code='OLD',
            unit_type=UnitType.DAIRA, parent=None,
        )

        tree = [{'id': 50, 'name': 'اسم جديد', 'children': None}]
        flat = build_flat([
            {'id': 50, 'name': 'اسم جديد', 'code': 'NEW',
             'unit_type_name': 'دائرة', 'is_active': True}
        ])
        service = OrganizationSyncService(client=make_mock_client(tree, [flat]))

        report = service.sync()

        assert report.created == 0
        assert report.updated == 1
        existing.refresh_from_db()
        assert existing.name == 'اسم جديد'
        assert existing.code == 'NEW'

    def test_update_preserves_qism_role(self):
        """qism_role محلي ولا تمسّه المزامنة."""
        existing = OrganizationUnit.objects.create(
            external_id=60, name='قسم تخطيط', code='P1',
            unit_type=UnitType.QISM, parent=None, qism_role='planning',
        )

        tree = [{'id': 60, 'name': 'قسم تخطيط محدَّث', 'children': None}]
        flat = build_flat([
            {'id': 60, 'name': 'قسم تخطيط محدَّث', 'code': 'P1',
             'unit_type_name': 'قسم', 'is_active': True}
        ])
        service = OrganizationSyncService(client=make_mock_client(tree, [flat]))
        service.sync()

        existing.refresh_from_db()
        assert existing.qism_role == 'planning'  # لم يتغيّر

    def test_update_no_change_returns_no_count(self):
        OrganizationUnit.objects.create(
            external_id=70, name='ثابت', code='S1',
            unit_type=UnitType.DAIRA, parent=None, is_active=True,
        )
        tree = [{'id': 70, 'name': 'ثابت', 'children': None}]
        flat = build_flat([
            {'id': 70, 'name': 'ثابت', 'code': 'S1',
             'unit_type_name': 'دائرة', 'is_active': True}
        ])
        service = OrganizationSyncService(client=make_mock_client(tree, [flat]))

        report = service.sync()
        # نُعدّ updated فقط عندما يتغيّر شيء فعلاً
        assert report.updated == 0


@pytest.mark.django_db
class TestSyncServiceDeactivate:
    """سيناريوهات الـ soft delete (وحدة اختفت من النظام الخارجي)."""

    def test_deactivate_disappeared_unit(self):
        # وحدة كانت تأتي من النظام الخارجي، اختفت الآن (نستخدم daira للتبسيط)
        existing = OrganizationUnit.objects.create(
            external_id=99, name='دائرة قديمة', code='G1',
            unit_type=UnitType.DAIRA, parent=None, is_active=True,
        )

        # النظام الخارجي لا يحتوي على external_id=99 بعد الآن
        service = OrganizationSyncService(
            client=make_mock_client(tree=[], flat_pages=[build_flat([])])
        )

        report = service.sync()

        assert report.deactivated == 1
        existing.refresh_from_db()
        assert existing.is_active is False

    def test_local_only_units_untouched(self):
        """الوحدات اليدوية (external_id IS NULL) لا تُمسّ بالمزامنة."""
        manual = OrganizationUnit.objects.create(
            external_id=None, name='يدويّة', code='LOCAL',
            unit_type=UnitType.DAIRA, parent=None, is_active=True,
        )

        service = OrganizationSyncService(
            client=make_mock_client(tree=[], flat_pages=[build_flat([])])
        )
        service.sync()

        manual.refresh_from_db()
        assert manual.is_active is True  # لم تتأثّر


@pytest.mark.django_db
class TestSyncServiceUnknownType:
    """تعامل مع أنواع وحدات غير معروفة."""

    def test_unknown_unit_type_is_skipped(self):
        tree = [{'id': 1, 'name': 'كيان', 'children': None}]
        flat = build_flat([
            {'id': 1, 'name': 'كيان', 'code': 'X',
             'unit_type_name': 'نوع غريب', 'is_active': True}
        ])
        service = OrganizationSyncService(client=make_mock_client(tree, [flat]))

        report = service.sync()

        assert report.skipped_unknown_type == 1
        assert report.created == 0
        assert not OrganizationUnit.objects.filter(external_id=1).exists()


@pytest.mark.django_db
class TestSyncServiceDryRun:
    """سيناريوهات الـ dry-run — لا تكتب أي شيء."""

    def test_dry_run_does_not_create(self):
        tree = [{'id': 1, 'name': 'دائرة', 'children': None}]
        flat = build_flat([
            {'id': 1, 'name': 'دائرة', 'code': 'D',
             'unit_type_name': 'دائرة', 'is_active': True}
        ])
        service = OrganizationSyncService(client=make_mock_client(tree, [flat]))

        report = service.sync(dry_run=True)

        assert report.dry_run is True
        assert report.created == 1  # سيُنشئ
        assert OrganizationUnit.objects.filter(external_id=1).count() == 0  # لم يُنشَأ فعلياً


@pytest.mark.django_db
class TestSyncServiceMapping:
    """خريطة أنواع الوحدات."""

    def test_default_map_includes_three_types(self):
        assert 'دائرة' in DEFAULT_UNIT_TYPE_MAP
        assert 'مديرية' in DEFAULT_UNIT_TYPE_MAP
        assert 'قسم' in DEFAULT_UNIT_TYPE_MAP

    def test_custom_map_can_override(self):
        custom = {'إدارة عامة': UnitType.DAIRA}
        tree = [{'id': 1, 'name': 'الإدارة', 'children': None}]
        flat = build_flat([
            {'id': 1, 'name': 'الإدارة', 'code': 'A',
             'unit_type_name': 'إدارة عامة', 'is_active': True}
        ])
        service = OrganizationSyncService(
            client=make_mock_client(tree, [flat]),
            unit_type_map=custom,
        )

        report = service.sync()
        assert report.created == 1
        unit = OrganizationUnit.objects.get(external_id=1)
        assert unit.unit_type == UnitType.DAIRA
