import pytest
from django.core.exceptions import ValidationError

from apps.indicators.tests.factories import IndicatorFactory
from apps.organization.models import PlanningAssignment
from apps.organization.tests.factories import (
    DairaFactory,
    MudiriyaFactory,
    PlanningQismFactory,
    QismFactory,
    SupervisedQismFactory,
)
from apps.targets.models import Target
from .factories import TargetFactory


@pytest.mark.django_db
class TestTargetValidation:
    """اختبارات التحقق من صحة المستهدفات"""

    def test_target_value_must_be_positive(self):
        """القيمة المستهدفة يجب أن تكون أكبر من صفر"""
        qism = QismFactory()
        target = TargetFactory.build(
            name="مستهدف اختبار",
            scope_unit=qism,
            target_value=0,
        )
        with pytest.raises(ValidationError) as exc:
            target.full_clean()
        assert 'target_value' in exc.value.message_dict

    def test_negative_target_value_is_invalid(self):
        """القيمة المستهدفة السالبة غير صالحة"""
        qism = QismFactory()
        target = TargetFactory.build(
            name="مستهدف اختبار",
            scope_unit=qism,
            target_value=-10,
        )
        with pytest.raises(ValidationError) as exc:
            target.full_clean()
        assert 'target_value' in exc.value.message_dict

    def test_valid_target_value(self):
        """القيمة المستهدفة الموجبة صالحة"""
        qism = SupervisedQismFactory()
        indicator = IndicatorFactory(
            unit_type="number", accumulation_type="sum"
        )
        target = TargetFactory(
            scope_unit=qism, indicators=[indicator], target_value=50.0
        )
        assert target.pk is not None

    def test_text_indicator_cannot_have_target(self):
        """المؤشر النصي لا يمكن تحديد مستهدف له"""
        qism = SupervisedQismFactory()
        text_indicator = IndicatorFactory(
            unit_type="text",
            accumulation_type="last_value",
        )
        # المؤشر النصي يُرفَض في validate_components (M2M بعد الحفظ)
        target = Target.objects.create(
            name="مستهدف نصّي",
            scope_unit=qism,
            year=2026,
            target_value=100,
        )
        with pytest.raises(ValidationError) as exc:
            target.validate_components([text_indicator])
        assert 'indicators' in exc.value.message_dict
        assert any(
            'نصّيّة' in msg or 'نصي' in msg
            for msg in exc.value.message_dict['indicators']
        )

    def test_target_str_includes_scope_and_name(self):
        """__str__ يرجع اسم النطاق والمستهدف والسنة"""
        qism = SupervisedQismFactory()
        indicator = IndicatorFactory(
            unit_type="number", accumulation_type="sum"
        )
        target = TargetFactory(
            name="إعداد التقارير",
            scope_unit=qism,
            indicators=[indicator],
            year=2025,
        )
        result = str(target)
        assert qism.name in result
        assert "إعداد التقارير" in result
        assert "2025" in result

    def test_institution_level_target_str(self):
        """__str__ لمستهدف على مستوى المؤسسة يُظهر 'المؤسسة كاملة'"""
        indicator = IndicatorFactory(
            unit_type="number", accumulation_type="sum"
        )
        target = TargetFactory(
            scope_unit=None, indicators=[indicator], year=2025
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
        target = TargetFactory(scope_unit=None, indicators=[indicator])
        assert target.scope_unit is None
        assert target.scope_level == 'institution'

    def test_daira_level_target_allowed(self):
        """المستهدفات على مستوى الدائرة مسموحة"""
        daira = DairaFactory()
        indicator = IndicatorFactory(
            unit_type="number", accumulation_type="sum"
        )
        target = TargetFactory(scope_unit=daira, indicators=[indicator])
        assert target.scope_level == 'daira'

    def test_mudiriya_level_target_allowed(self):
        """المستهدفات على مستوى المديرية مسموحة"""
        mudiriya = MudiriyaFactory()
        indicator = IndicatorFactory(
            unit_type="number", accumulation_type="sum"
        )
        target = TargetFactory(scope_unit=mudiriya, indicators=[indicator])
        assert target.scope_level == 'mudiriya'

    def test_qism_level_target_allowed(self):
        """المستهدفات على مستوى القسم مسموحة"""
        qism = SupervisedQismFactory()
        target = TargetFactory(scope_unit=qism)
        assert target.scope_level == 'qism'

    def test_special_qism_cannot_be_scope(self):
        """الأقسام الخاصة (تخطيط/إحصاء) لا يمكن أن تكون نطاقاً"""
        planning_qism = PlanningQismFactory()
        # بعد Phase F: قسم التخطيط يُحدَّد عبر PlanningAssignment
        PlanningAssignment.objects.create(planning_unit=planning_qism)
        target = TargetFactory.build(
            name="مستهدف غير صالح",
            scope_unit=planning_qism,
        )
        with pytest.raises(ValidationError) as exc:
            target.full_clean()
        # الوصول للرسائل عبر message_dict لتجنّب مشكلة Unicode escaping في str()
        assert 'scope_unit' in exc.value.message_dict

    def test_last_value_indicator_at_mudiriya_level_rejected(self):
        """مؤشر 'آخر قيمة' لا يُسمح به على مستوى المديرية"""
        mudiriya = MudiriyaFactory()
        lv_indicator = IndicatorFactory(
            unit_type="number", accumulation_type="last_value"
        )
        # last_value يُرفَض في validate_components (M2M بعد الحفظ)
        target = Target.objects.create(
            name="مستهدف آخر قيمة",
            scope_unit=mudiriya,
            year=2026,
            target_value=100,
        )
        with pytest.raises(ValidationError) as exc:
            target.validate_components([lv_indicator])
        assert "آخر قيمة" in str(exc.value)

    def test_last_value_indicator_at_institution_level_rejected(self):
        """مؤشر 'آخر قيمة' لا يُسمح به على مستوى المؤسسة"""
        lv_indicator = IndicatorFactory(
            unit_type="number", accumulation_type="last_value"
        )
        target = Target.objects.create(
            name="مستهدف آخر قيمة مؤسسة",
            scope_unit=None,
            year=2026,
            target_value=100,
        )
        with pytest.raises(ValidationError) as exc:
            target.validate_components([lv_indicator])
        assert "آخر قيمة" in str(exc.value)

    def test_last_value_indicator_at_qism_level_allowed(self):
        """مؤشر 'آخر قيمة' مسموح على مستوى القسم"""
        qism = SupervisedQismFactory()
        lv_indicator = IndicatorFactory(
            unit_type="number", accumulation_type="last_value"
        )
        target = TargetFactory(scope_unit=qism, indicators=[lv_indicator])
        # validate_components يجب ألّا يرفع استثناء على مستوى القسم
        target.validate_components([lv_indicator])


@pytest.mark.django_db
class TestUniqueConstraint:
    """اختبارات تفرّد اسم المستهدف داخل (scope_unit, year)"""

    def test_cannot_duplicate_name_in_same_scope_and_year(self):
        """لا يمكن إنشاء مستهدفين بنفس الاسم في نفس القسم والسنة"""
        qism = SupervisedQismFactory()
        indicator = IndicatorFactory(
            unit_type="number", accumulation_type="sum"
        )
        TargetFactory(
            name="إعداد التقارير",
            scope_unit=qism,
            indicators=[indicator],
            year=2026,
        )
        # محاولة إنشاء مستهدف ثانٍ بنفس الاسم/النطاق/السنة → فشل
        # validate_components يُجري الفحص.
        second = Target.objects.create(
            name="إعداد التقارير",
            scope_unit=qism,
            year=2026,
            target_value=50,
        )
        with pytest.raises(ValidationError) as exc:
            second.validate_components([indicator])
        assert 'name' in exc.value.message_dict

    def test_cannot_duplicate_institution_name(self):
        """لا يمكن إنشاء مستهدفين بنفس الاسم على مستوى المؤسسة لنفس السنة"""
        indicator = IndicatorFactory(
            unit_type="number", accumulation_type="sum"
        )
        TargetFactory(
            name="مستهدف مؤسسي",
            scope_unit=None,
            indicators=[indicator],
            year=2026,
        )
        second = Target.objects.create(
            name="مستهدف مؤسسي",
            scope_unit=None,
            year=2026,
            target_value=100,
        )
        with pytest.raises(ValidationError) as exc:
            second.validate_components([indicator])
        assert 'name' in exc.value.message_dict

    def test_same_name_different_scope_levels_allowed(self):
        """نفس اسم المستهدف يمكن أن يكون له مستهدفات على مستويات مختلفة"""
        indicator = IndicatorFactory(
            unit_type="number", accumulation_type="sum"
        )
        daira = DairaFactory()
        mudiriya = MudiriyaFactory(parent=daira)
        qism = SupervisedQismFactory(parent=mudiriya)

        # أربع مستهدفات بنفس الاسم على نطاقات مختلفة وسنة واحدة
        TargetFactory(
            name="إعداد التقارير", scope_unit=None,
            indicators=[indicator], year=2026,
        )
        TargetFactory(
            name="إعداد التقارير", scope_unit=daira,
            indicators=[indicator], year=2026,
        )
        TargetFactory(
            name="إعداد التقارير", scope_unit=mudiriya,
            indicators=[indicator], year=2026,
        )
        TargetFactory(
            name="إعداد التقارير", scope_unit=qism,
            indicators=[indicator], year=2026,
        )
        # لا يجب أن ترفع أي أخطاء — التفرّد يكون داخل (scope_unit, year, name)
