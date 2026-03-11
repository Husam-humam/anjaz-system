"""
اختبارات خدمات المستهدفات — TargetService.
"""
import pytest
from django.core.exceptions import ValidationError

from apps.targets.models import Target
from apps.targets.services import TargetService
from apps.targets.tests.factories import TargetFactory
from apps.indicators.tests.factories import IndicatorFactory
from apps.organization.tests.factories import QismFactory
from apps.accounts.tests.factories import StatisticsAdminFactory


@pytest.mark.django_db
class TestTargetService:
    """اختبارات خدمة إدارة المستهدفات"""

    def test_create_target(self):
        """اختبار إنشاء مستهدف جديد بنجاح"""
        admin = StatisticsAdminFactory()
        qism = QismFactory()
        indicator = IndicatorFactory()
        data = {
            'qism': qism,
            'indicator': indicator,
            'year': 2025,
            'target_value': 150.0,
            'notes': 'مستهدف اختبار',
        }

        target = TargetService.create_target(data, set_by=admin)

        assert target.pk is not None
        assert target.qism == qism
        assert target.indicator == indicator
        assert target.year == 2025
        assert target.target_value == 150.0
        assert target.set_by == admin
        assert target.notes == 'مستهدف اختبار'

    def test_create_target_with_zero_value_fails(self):
        """اختبار فشل إنشاء مستهدف بقيمة صفر"""
        admin = StatisticsAdminFactory()
        qism = QismFactory()
        indicator = IndicatorFactory()
        data = {
            'qism': qism,
            'indicator': indicator,
            'year': 2025,
            'target_value': 0,
        }

        with pytest.raises(ValidationError) as exc_info:
            TargetService.create_target(data, set_by=admin)

        assert 'target_value' in exc_info.value.message_dict

    def test_create_target_with_negative_value_fails(self):
        """اختبار فشل إنشاء مستهدف بقيمة سالبة"""
        admin = StatisticsAdminFactory()
        qism = QismFactory()
        indicator = IndicatorFactory()
        data = {
            'qism': qism,
            'indicator': indicator,
            'year': 2025,
            'target_value': -10.0,
        }

        with pytest.raises(ValidationError) as exc_info:
            TargetService.create_target(data, set_by=admin)

        assert 'target_value' in exc_info.value.message_dict

    def test_update_target(self):
        """اختبار تحديث مستهدف بنجاح"""
        target = TargetFactory(target_value=100.0)

        updated = TargetService.update_target(
            target, {'target_value': 200.0}
        )

        assert updated.target_value == 200.0
        target.refresh_from_db()
        assert target.target_value == 200.0

    def test_delete_target(self):
        """اختبار حذف مستهدف"""
        target = TargetFactory()
        target_pk = target.pk

        TargetService.delete_target(target)

        assert not Target.objects.filter(pk=target_pk).exists()

    def test_get_targets_for_qism(self):
        """اختبار الحصول على مستهدفات قسم لسنة معينة"""
        qism = QismFactory()
        indicator1 = IndicatorFactory()
        indicator2 = IndicatorFactory()

        # مستهدفات لنفس القسم والسنة
        TargetFactory(qism=qism, indicator=indicator1, year=2025)
        TargetFactory(qism=qism, indicator=indicator2, year=2025)
        # مستهدف لسنة مختلفة — يجب ألا يظهر
        TargetFactory(qism=qism, indicator=IndicatorFactory(), year=2024)
        # مستهدف لقسم مختلف — يجب ألا يظهر
        TargetFactory(year=2025)

        results = TargetService.get_targets_for_qism(qism.pk, 2025)

        assert results.count() == 2
        assert all(t.qism == qism and t.year == 2025 for t in results)

    def test_get_targets_for_qism_empty(self):
        """اختبار إرجاع مجموعة فارغة عند عدم وجود مستهدفات"""
        qism = QismFactory()

        results = TargetService.get_targets_for_qism(qism.pk, 2025)

        assert results.count() == 0
