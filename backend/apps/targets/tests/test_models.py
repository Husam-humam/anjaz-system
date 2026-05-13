import pytest
from django.core.exceptions import ValidationError

from apps.indicators.tests.factories import IndicatorFactory
from apps.organization.tests.factories import (
    DairaFactory,
    MudiriyaFactory,
    PlanningQismFactory,
    QismFactory,
)
from .factories import TargetFactory


@pytest.mark.django_db
class TestTargetValidation:
    """اختبارات التحقق من صحة المستهدفات"""

    def test_target_value_must_be_positive(self):
        """القيمة المستهدفة يجب أن تكون أكبر من صفر"""
        qism = QismFactory()
        indicator = IndicatorFactory(
            unit_type="number", accumulation_type="sum"
        )
        target = TargetFactory.build(
            scope_unit=qism, indicator=indicator, target_value=0
        )
        with pytest.raises(ValidationError) as exc:
            target.full_clean()
        assert 'target_value' in exc.value.message_dict

    def test_negative_target_value_is_invalid(self):
        """القيمة المستهدفة السالبة غير صالحة"""
        qism = QismFactory()
        indicator = IndicatorFactory(
            unit_type="number", accumulation_type="sum"
        )
        target = TargetFactory.build(
            scope_unit=qism, indicator=indicator, target_value=-10
        )
        with pytest.raises(ValidationError) as exc:
            target.full_clean()
        assert 'target_value' in exc.value.message_dict

    def test_valid_target_value(self):
        """القيمة المستهدفة الموجبة صالحة"""
        qism = QismFactory()
        indicator = IndicatorFactory(
            unit_type="number", accumulation_type="sum"
        )
        target = TargetFactory(
            scope_unit=qism, indicator=indicator, target_value=50.0
        )
        assert target.pk is not None

    def test_text_indicator_cannot_have_target(self):
        """المؤشر النصي لا يمكن تحديد مستهدف له"""
        qism = QismFactory()
        text_indicator = IndicatorFactory(
            unit_type="text",
            accumulation_type="last_value",
        )
        target = TargetFactory.build(
            scope_unit=qism,
            indicator=text_indicator,
            target_value=100,
        )
        with pytest.raises(ValidationError) as exc:
            target.full_clean()
        assert 'indicator' in exc.value.message_dict
        assert any(
            'نصي' in msg for msg in exc.value.message_dict['indicator']
        )

    def test_target_str_includes_scope_and_indicator(self):
        """__str__ يرجع اسم النطاق والمؤشر والسنة"""
        qism = QismFactory()
        indicator = IndicatorFactory(
            unit_type="number", accumulation_type="sum"
        )
        target = TargetFactory(
            scope_unit=qism, indicator=indicator, year=2025
        )
        result = str(target)
        assert qism.name in result
        assert indicator.name in result
        assert "2025" in result

    def test_institution_level_target_str(self):
        """__str__ لمستهدف على مستوى المؤسسة يُظهر 'المؤسسة كاملة'"""
        indicator = IndicatorFactory(
            unit_type="number", accumulation_type="sum"
        )
        target = TargetFactory(
            scope_unit=None, indicator=indicator, year=2025
        )
        result = str(target)
        assert "المؤسسة كاملة" in result


@pytest.mark.django_db
class TestHierarchicalScope:
    """اختبارات النطاق الهرمي (مؤسسة/دائرة/مديرية/قسم)"""

    def test_institution_level_target_allowed(self):
        """المستهدفات على مستوى المؤسسة مسموحة (scope_unit=None)"""
        indicator = IndicatorFactory(
            unit_type="number", accumulation_type="sum"
        )
        target = TargetFactory(scope_unit=None, indicator=indicator)
        assert target.scope_unit is None
        assert target.scope_level == 'institution'

    def test_daira_level_target_allowed(self):
        """المستهدفات على مستوى الدائرة مسموحة"""
        daira = DairaFactory()
        indicator = IndicatorFactory(
            unit_type="number", accumulation_type="sum"
        )
        target = TargetFactory(scope_unit=daira, indicator=indicator)
        assert target.scope_level == 'daira'

    def test_mudiriya_level_target_allowed(self):
        """المستهدفات على مستوى المديرية مسموحة"""
        mudiriya = MudiriyaFactory()
        indicator = IndicatorFactory(
            unit_type="number", accumulation_type="sum"
        )
        target = TargetFactory(scope_unit=mudiriya, indicator=indicator)
        assert target.scope_level == 'mudiriya'

    def test_qism_level_target_allowed(self):
        """المستهدفات على مستوى القسم مسموحة"""
        qism = QismFactory()
        target = TargetFactory(scope_unit=qism)
        assert target.scope_level == 'qism'

    def test_special_qism_cannot_be_scope(self):
        """الأقسام الخاصة (تخطيط/إحصاء) لا يمكن أن تكون نطاقاً"""
        planning_qism = PlanningQismFactory()
        indicator = IndicatorFactory(
            unit_type="number", accumulation_type="sum"
        )
        target = TargetFactory.build(
            scope_unit=planning_qism, indicator=indicator
        )
        with pytest.raises(ValidationError) as exc:
            target.full_clean()
        # الوصول للرسائل عبر message_dict لتجنّب مشكلة Unicode escaping في str()
        assert 'scope_unit' in exc.value.message_dict
        assert any(
            'الخاصة' in msg
            for msg in exc.value.message_dict['scope_unit']
        )

    def test_last_value_indicator_at_mudiriya_level_rejected(self):
        """مؤشر 'آخر قيمة' لا يُسمح به على مستوى المديرية"""
        mudiriya = MudiriyaFactory()
        lv_indicator = IndicatorFactory(
            unit_type="number", accumulation_type="last_value"
        )
        target = TargetFactory.build(
            scope_unit=mudiriya, indicator=lv_indicator
        )
        with pytest.raises(ValidationError) as exc:
            target.full_clean()
        assert "آخر قيمة" in str(exc.value)

    def test_last_value_indicator_at_institution_level_rejected(self):
        """مؤشر 'آخر قيمة' لا يُسمح به على مستوى المؤسسة"""
        lv_indicator = IndicatorFactory(
            unit_type="number", accumulation_type="last_value"
        )
        target = TargetFactory.build(
            scope_unit=None, indicator=lv_indicator
        )
        with pytest.raises(ValidationError) as exc:
            target.full_clean()
        assert "آخر قيمة" in str(exc.value)

    def test_last_value_indicator_at_qism_level_allowed(self):
        """مؤشر 'آخر قيمة' مسموح على مستوى القسم"""
        qism = QismFactory()
        lv_indicator = IndicatorFactory(
            unit_type="number", accumulation_type="last_value"
        )
        target = TargetFactory(scope_unit=qism, indicator=lv_indicator)
        target.full_clean()  # يجب ألا يرفع استثناء


@pytest.mark.django_db
class TestUniqueConstraint:
    """اختبارات فريدة القيد (scope_unit, indicator, year)"""

    def test_cannot_duplicate_qism_target(self):
        """لا يمكن إنشاء مستهدفين لنفس القسم والمؤشر والسنة"""
        target1 = TargetFactory()
        with pytest.raises(Exception):
            TargetFactory(
                scope_unit=target1.scope_unit,
                indicator=target1.indicator,
                year=target1.year,
            )

    def test_cannot_duplicate_institution_target(self):
        """لا يمكن إنشاء مستهدفين على مستوى المؤسسة لنفس المؤشر والسنة"""
        indicator = IndicatorFactory(
            unit_type="number", accumulation_type="sum"
        )
        TargetFactory(scope_unit=None, indicator=indicator, year=2026)
        with pytest.raises(ValidationError) as exc:
            TargetFactory(scope_unit=None, indicator=indicator, year=2026)
        assert "يوجد مسبقاً مستهدف على مستوى المؤسسة" in str(exc.value)

    def test_same_indicator_different_scope_levels_allowed(self):
        """نفس المؤشر يمكن أن يكون له مستهدفات على مستويات مختلفة"""
        indicator = IndicatorFactory(
            unit_type="number", accumulation_type="sum"
        )
        daira = DairaFactory()
        mudiriya = MudiriyaFactory(parent=daira)
        qism = QismFactory(parent=mudiriya)

        # ثلاث مستهدفات مختلفة لنفس المؤشر والسنة
        TargetFactory(scope_unit=None, indicator=indicator, year=2026)
        TargetFactory(scope_unit=daira, indicator=indicator, year=2026)
        TargetFactory(scope_unit=mudiriya, indicator=indicator, year=2026)
        TargetFactory(scope_unit=qism, indicator=indicator, year=2026)
        # لا يجب أن ترفع أي أخطاء
