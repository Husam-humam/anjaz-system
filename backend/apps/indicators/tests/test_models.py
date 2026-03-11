import pytest
from django.core.exceptions import ValidationError

from .factories import IndicatorFactory, IndicatorCategoryFactory


@pytest.mark.django_db
class TestIndicatorValidation:
    """اختبارات التحقق من صحة المؤشرات"""

    def test_text_indicator_must_use_last_value_accumulation(self):
        """المؤشر النصي يجب أن يستخدم طريقة تجميع 'آخر قيمة' فقط"""
        indicator = IndicatorFactory.build(
            unit_type="text",
            accumulation_type="sum",
        )
        with pytest.raises(ValidationError) as exc:
            indicator.full_clean()
        assert "المؤشرات النصية يجب أن تستخدم طريقة تجميع" in str(exc.value)

    def test_text_indicator_valid_with_last_value(self):
        """المؤشر النصي صالح مع طريقة تجميع 'آخر قيمة'"""
        indicator = IndicatorFactory.build(
            unit_type="text",
            accumulation_type="last_value",
        )
        indicator.full_clean()  # يجب ألا يرفع استثناء

    def test_numeric_indicator_can_use_sum(self):
        """المؤشر الرقمي يمكنه استخدام طريقة تجميع 'مجموع'"""
        indicator = IndicatorFactory.build(
            unit_type="number",
            accumulation_type="sum",
        )
        indicator.full_clean()  # يجب ألا يرفع استثناء

    def test_numeric_indicator_can_use_average(self):
        """المؤشر الرقمي يمكنه استخدام طريقة تجميع 'متوسط'"""
        indicator = IndicatorFactory.build(
            unit_type="number",
            accumulation_type="average",
        )
        indicator.full_clean()  # يجب ألا يرفع استثناء

    def test_indicator_str_returns_name(self):
        """__str__ يرجع اسم المؤشر"""
        indicator = IndicatorFactory.build(name="عدد المعاملات المنجزة")
        assert str(indicator) == "عدد المعاملات المنجزة"

    def test_indicator_category_str_returns_name(self):
        """__str__ لتصنيف المؤشر يرجع الاسم"""
        category = IndicatorCategoryFactory.build(name="إداري")
        assert str(category) == "إداري"

    def test_indicator_is_numeric_for_number_type(self):
        """is_numeric يرجع True للمؤشرات الرقمية"""
        indicator = IndicatorFactory.build(unit_type="number")
        assert indicator.is_numeric is True

    def test_indicator_is_not_numeric_for_text_type(self):
        """is_numeric يرجع False للمؤشرات النصية"""
        indicator = IndicatorFactory.build(unit_type="text")
        assert indicator.is_numeric is False
