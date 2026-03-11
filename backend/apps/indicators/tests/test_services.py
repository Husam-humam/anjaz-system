"""
اختبارات خدمات المؤشرات — IndicatorService و IndicatorCategoryService.
"""
import pytest
from django.core.exceptions import ValidationError

from apps.indicators.services import IndicatorCategoryService, IndicatorService
from apps.indicators.tests.factories import IndicatorCategoryFactory, IndicatorFactory
from apps.accounts.tests.factories import StatisticsAdminFactory


@pytest.mark.django_db
class TestIndicatorService:
    """اختبارات خدمة إدارة المؤشرات"""

    def test_create_indicator(self):
        """اختبار إنشاء مؤشر جديد بنجاح"""
        user = StatisticsAdminFactory()
        category = IndicatorCategoryFactory()
        data = {
            'name': 'عدد الأجهزة',
            'unit_type': 'number',
            'unit_label': 'جهاز',
            'accumulation_type': 'sum',
            'category': category,
        }

        indicator = IndicatorService.create_indicator(data, created_by=user)

        assert indicator.pk is not None
        assert indicator.name == 'عدد الأجهزة'
        assert indicator.unit_type == 'number'
        assert indicator.unit_label == 'جهاز'
        assert indicator.accumulation_type == 'sum'
        assert indicator.category == category
        assert indicator.created_by == user
        assert indicator.is_active is True

    def test_create_indicator_text_with_invalid_accumulation_fails(self):
        """اختبار فشل إنشاء مؤشر نصي مع طريقة تجميع غير آخر قيمة"""
        user = StatisticsAdminFactory()
        category = IndicatorCategoryFactory()
        data = {
            'name': 'مؤشر نصي',
            'unit_type': 'text',
            'unit_label': '',
            'accumulation_type': 'sum',
            'category': category,
        }

        with pytest.raises(ValidationError) as exc_info:
            IndicatorService.create_indicator(data, created_by=user)

        assert 'accumulation_type' in exc_info.value.message_dict

    def test_update_indicator(self):
        """اختبار تحديث مؤشر بنجاح"""
        indicator = IndicatorFactory()
        new_name = 'مؤشر محدث'

        updated = IndicatorService.update_indicator(
            indicator, {'name': new_name}
        )

        assert updated.name == new_name
        indicator.refresh_from_db()
        assert indicator.name == new_name

    def test_deactivate_indicator(self):
        """اختبار تعطيل مؤشر (حذف ناعم)"""
        indicator = IndicatorFactory(is_active=True)

        result = IndicatorService.deactivate_indicator(indicator)

        assert result.is_active is False
        indicator.refresh_from_db()
        assert indicator.is_active is False


@pytest.mark.django_db
class TestIndicatorCategoryService:
    """اختبارات خدمة إدارة تصنيفات المؤشرات"""

    def test_create_category(self):
        """اختبار إنشاء تصنيف جديد بنجاح"""
        data = {'name': 'تصنيف جديد'}

        category = IndicatorCategoryService.create_category(data)

        assert category.pk is not None
        assert category.name == 'تصنيف جديد'
        assert category.is_active is True

    def test_deactivate_category_with_active_indicators_fails(self):
        """اختبار فشل تعطيل تصنيف يحتوي على مؤشرات نشطة"""
        category = IndicatorCategoryFactory()
        # إنشاء مؤشر نشط مرتبط بالتصنيف
        IndicatorFactory(category=category, is_active=True)

        with pytest.raises(ValidationError) as exc_info:
            IndicatorCategoryService.deactivate_category(category)

        assert 'لا يمكن تعطيل تصنيف يحتوي على مؤشرات نشطة' in str(exc_info.value)

    def test_deactivate_category_without_indicators_succeeds(self):
        """اختبار نجاح تعطيل تصنيف بدون مؤشرات نشطة"""
        category = IndicatorCategoryFactory(is_active=True)

        result = IndicatorCategoryService.deactivate_category(category)

        assert result.is_active is False
        category.refresh_from_db()
        assert category.is_active is False

    def test_deactivate_category_with_inactive_indicators_succeeds(self):
        """اختبار نجاح تعطيل تصنيف يحتوي على مؤشرات غير نشطة فقط"""
        category = IndicatorCategoryFactory(is_active=True)
        IndicatorFactory(category=category, is_active=False)

        result = IndicatorCategoryService.deactivate_category(category)

        assert result.is_active is False
