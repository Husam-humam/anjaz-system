import pytest
from django.core.exceptions import ValidationError

from apps.indicators.tests.factories import IndicatorFactory
from .factories import TargetFactory


@pytest.mark.django_db
class TestTargetValidation:
    """اختبارات التحقق من صحة المستهدفات السنوية"""

    def test_target_value_must_be_positive(self):
        """القيمة المستهدفة يجب أن تكون أكبر من صفر"""
        target = TargetFactory.build(target_value=0)
        with pytest.raises(ValidationError) as exc:
            target.full_clean()
        assert "القيمة المستهدفة يجب أن تكون أكبر من صفر" in str(exc.value)

    def test_negative_target_value_is_invalid(self):
        """القيمة المستهدفة السالبة غير صالحة"""
        target = TargetFactory.build(target_value=-10)
        with pytest.raises(ValidationError) as exc:
            target.full_clean()
        assert "القيمة المستهدفة يجب أن تكون أكبر من صفر" in str(exc.value)

    def test_valid_target_value(self):
        """القيمة المستهدفة الموجبة صالحة"""
        target = TargetFactory.build(target_value=50.0)
        target.full_clean()  # يجب ألا يرفع استثناء

    def test_text_indicator_cannot_have_target(self):
        """المؤشر النصي لا يمكن تحديد مستهدف له"""
        text_indicator = IndicatorFactory(
            unit_type="text",
            accumulation_type="last_value",
        )
        target = TargetFactory.build(
            indicator=text_indicator,
            target_value=100,
        )
        with pytest.raises(ValidationError) as exc:
            target.full_clean()
        assert "لا يمكن تحديد مستهدف لمؤشر نصي" in str(exc.value)

    def test_target_str(self):
        """__str__ يرجع اسم القسم والمؤشر والسنة"""
        target = TargetFactory.build(year=2025)
        result = str(target)
        assert target.qism.name in result
        assert target.indicator.name in result
        assert "2025" in result

    def test_target_unique_qism_indicator_year(self):
        """لا يمكن إنشاء مستهدفين لنفس القسم والمؤشر والسنة"""
        target1 = TargetFactory()
        with pytest.raises(Exception):
            TargetFactory(
                qism=target1.qism,
                indicator=target1.indicator,
                year=target1.year,
            )
