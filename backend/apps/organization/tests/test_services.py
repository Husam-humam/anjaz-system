"""
اختبارات طبقة الخدمات لتطبيق الهيكل التنظيمي.
"""
import pytest
from django.core.exceptions import ValidationError

from apps.organization.models import OrganizationUnit
from apps.organization.services import OrganizationService
from apps.organization.tests.factories import (
    DairaFactory,
    MudiriyaFactory,
    QismFactory,
)
from apps.accounts.tests.factories import StatisticsAdminFactory


@pytest.mark.django_db
class TestOrganizationServiceCreateUnit:
    """اختبارات إنشاء كيان تنظيمي"""

    def test_create_unit_valid(self):
        """التحقق من إنشاء كيان تنظيمي صالح (دائرة بدون أب)"""
        data = {
            'name': 'دائرة الموارد البشرية',
            'code': 'D100',
            'unit_type': 'daira',
        }
        unit = OrganizationService.create_unit(data)

        assert unit.pk is not None
        assert unit.name == 'دائرة الموارد البشرية'
        assert unit.code == 'D100'
        assert unit.unit_type == 'daira'
        assert unit.parent is None
        assert unit.is_active is True

    def test_create_unit_valid_mudiriya_under_daira(self):
        """التحقق من إنشاء مديرية تحت دائرة"""
        daira = DairaFactory()
        data = {
            'name': 'مديرية التطوير',
            'code': 'M100',
            'unit_type': 'mudiriya',
            'parent': daira,
        }
        unit = OrganizationService.create_unit(data)

        assert unit.pk is not None
        assert unit.parent == daira
        assert unit.unit_type == 'mudiriya'

    def test_create_unit_valid_qism_under_mudiriya(self):
        """التحقق من إنشاء قسم تحت مديرية"""
        mudiriya = MudiriyaFactory()
        data = {
            'name': 'قسم البرمجة',
            'code': 'Q100',
            'unit_type': 'qism',
            'qism_role': 'regular',
            'parent': mudiriya,
        }
        unit = OrganizationService.create_unit(data)

        assert unit.pk is not None
        assert unit.parent == mudiriya

    def test_create_unit_invalid_hierarchy_daira_with_parent(self):
        """التحقق من رفض إنشاء دائرة لها كيان أب"""
        daira = DairaFactory()
        data = {
            'name': 'دائرة فرعية',
            'code': 'D200',
            'unit_type': 'daira',
            'parent': daira,
        }
        with pytest.raises(ValidationError) as exc_info:
            OrganizationService.create_unit(data)
        assert 'parent' in exc_info.value.message_dict

    def test_create_unit_invalid_hierarchy_qism_without_parent(self):
        """التحقق من رفض إنشاء قسم بدون كيان أب"""
        data = {
            'name': 'قسم مستقل',
            'code': 'Q200',
            'unit_type': 'qism',
        }
        with pytest.raises(ValidationError) as exc_info:
            OrganizationService.create_unit(data)
        assert 'parent' in exc_info.value.message_dict

    def test_create_unit_invalid_hierarchy_qism_under_qism(self):
        """التحقق من رفض إنشاء قسم تحت قسم آخر"""
        qism = QismFactory()
        data = {
            'name': 'قسم فرعي',
            'code': 'Q300',
            'unit_type': 'qism',
            'parent': qism,
        }
        with pytest.raises(ValidationError) as exc_info:
            OrganizationService.create_unit(data)
        assert 'parent' in exc_info.value.message_dict

    def test_create_unit_invalid_hierarchy_mudiriya_under_mudiriya(self):
        """التحقق من رفض إنشاء مديرية تحت مديرية"""
        mudiriya = MudiriyaFactory()
        data = {
            'name': 'مديرية فرعية',
            'code': 'M200',
            'unit_type': 'mudiriya',
            'parent': mudiriya,
        }
        with pytest.raises(ValidationError) as exc_info:
            OrganizationService.create_unit(data)
        assert 'parent' in exc_info.value.message_dict


@pytest.mark.django_db
class TestOrganizationServiceUpdateUnit:
    """اختبارات تحديث كيان تنظيمي"""

    def test_update_unit(self):
        """التحقق من تحديث بيانات كيان تنظيمي بنجاح"""
        daira = DairaFactory(name='دائرة قديمة')
        updated = OrganizationService.update_unit(daira, {'name': 'دائرة جديدة'})

        assert updated.name == 'دائرة جديدة'
        daira.refresh_from_db()
        assert daira.name == 'دائرة جديدة'

    def test_update_unit_code(self):
        """التحقق من تحديث رمز الكيان"""
        daira = DairaFactory(code='D999')
        updated = OrganizationService.update_unit(daira, {'code': 'D888'})

        updated.refresh_from_db()
        assert updated.code == 'D888'


@pytest.mark.django_db
class TestOrganizationServiceDeactivateUnit:
    """اختبارات تعطيل كيان تنظيمي"""

    def test_deactivate_unit(self):
        """التحقق من تعطيل كيان تنظيمي ليس له أبناء نشطون"""
        qism = QismFactory()
        result = OrganizationService.deactivate_unit(qism)

        assert result.is_active is False
        qism.refresh_from_db()
        assert qism.is_active is False

    def test_deactivate_unit_with_active_children_fails(self):
        """التحقق من رفض تعطيل كيان له كيانات فرعية نشطة"""
        daira = DairaFactory()
        # إنشاء مديرية نشطة تحت الدائرة
        MudiriyaFactory(parent=daira, is_active=True)

        with pytest.raises(ValidationError) as exc_info:
            OrganizationService.deactivate_unit(daira)
        assert 'لا يمكن تعطيل كيان يحتوي على كيانات فرعية نشطة' in str(
            exc_info.value
        )

    def test_deactivate_unit_with_inactive_children_succeeds(self):
        """التحقق من نجاح تعطيل كيان له كيانات فرعية غير نشطة فقط"""
        daira = DairaFactory()
        MudiriyaFactory(parent=daira, is_active=False)

        result = OrganizationService.deactivate_unit(daira)
        assert result.is_active is False


@pytest.mark.django_db
class TestOrganizationServiceGetTree:
    """اختبارات الحصول على شجرة الهيكل التنظيمي"""

    def test_get_tree_returns_root_units(self):
        """التحقق من أن get_tree تُرجع الكيانات الجذرية فقط"""
        daira1 = DairaFactory(name='دائرة 100')
        daira2 = DairaFactory(name='دائرة 200')
        # مديرية تحت الدائرة الأولى — يجب ألا تظهر في النتائج
        MudiriyaFactory(parent=daira1)

        roots = OrganizationService.get_tree()
        root_ids = list(roots.values_list('id', flat=True))

        assert daira1.id in root_ids
        assert daira2.id in root_ids
        # يجب ألا تحتوي القائمة على أكثر من كيانين جذريين
        assert len(root_ids) == 2

    def test_get_tree_excludes_inactive_units(self):
        """التحقق من استبعاد الكيانات غير النشطة من الشجرة"""
        DairaFactory(is_active=True)
        inactive_daira = DairaFactory(is_active=False)

        roots = OrganizationService.get_tree()
        root_ids = list(roots.values_list('id', flat=True))

        assert inactive_daira.id not in root_ids

    def test_get_tree_admin_sees_all(self):
        """التحقق من أن مدير الإحصاء يرى جميع الكيانات الجذرية"""
        admin = StatisticsAdminFactory()
        daira1 = DairaFactory()
        daira2 = DairaFactory()

        roots = OrganizationService.get_tree(user=admin)
        root_ids = list(roots.values_list('id', flat=True))

        assert daira1.id in root_ids
        assert daira2.id in root_ids
