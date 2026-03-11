import pytest
from django.core.exceptions import ValidationError

from .factories import DairaFactory, MudiriyaFactory, QismFactory, PlanningQismFactory


@pytest.mark.django_db
class TestOrganizationUnitValidation:
    """اختبارات التحقق من صحة العلاقات الهرمية للكيانات التنظيمية"""

    def test_daira_cannot_have_parent(self):
        """الدائرة لا يمكن أن تتبع كيانًا آخر"""
        daira = DairaFactory()
        child_daira = DairaFactory.build(parent=daira)
        with pytest.raises(ValidationError) as exc:
            child_daira.full_clean()
        assert "الدائرة يجب أن تكون في المستوى الأعلى" in str(exc.value)

    def test_mudiriya_must_have_daira_parent_or_none(self):
        """المديرية يجب أن تتبع دائرة أو تكون مستقلة"""
        other_mudiriya = MudiriyaFactory()
        invalid_mudiriya = MudiriyaFactory.build(parent=other_mudiriya)
        with pytest.raises(ValidationError) as exc:
            invalid_mudiriya.full_clean()
        assert "المديرية يجب أن تتبع دائرة أو تكون مستقلة" in str(exc.value)

    def test_mudiriya_can_be_independent(self):
        """المديرية يمكن أن تكون مستقلة بدون كيان أب"""
        mudiriya = MudiriyaFactory.build(parent=None)
        mudiriya.full_clean()  # يجب ألا يرفع استثناء

    def test_qism_parent_can_be_mudiriya(self):
        """القسم يمكن أن يتبع مديرية"""
        mudiriya = MudiriyaFactory()
        qism = QismFactory.build(parent=mudiriya)
        qism.full_clean()  # يجب ألا يرفع استثناء

    def test_qism_parent_can_be_daira(self):
        """القسم يمكن أن يتبع دائرة مباشرة"""
        daira = DairaFactory()
        qism = QismFactory.build(parent=daira, unit_type="qism")
        qism.full_clean()  # يجب ألا يرفع استثناء

    def test_qism_cannot_be_parent_of_another_unit(self):
        """القسم لا يمكن أن يكون كيانًا أبًا لأي كيان آخر"""
        qism = QismFactory()
        child = QismFactory.build(parent=qism)
        with pytest.raises(ValidationError) as exc:
            child.full_clean()
        assert "القسم لا يمكن أن يكون كياناً أباً" in str(exc.value)

    def test_get_full_path_returns_ancestor_chain(self):
        """المسار الكامل يرجع سلسلة الأسلاف"""
        daira = DairaFactory(name="دائرة الشؤون")
        mudiriya = MudiriyaFactory(name="مديرية الموارد", parent=daira)
        qism = QismFactory(name="قسم التوظيف", parent=mudiriya)
        assert qism.get_full_path() == "دائرة الشؤون / مديرية الموارد / قسم التوظيف"

    def test_qism_role_forced_to_regular_for_non_qism(self):
        """دور القسم يُعاد تعيينه إلى 'عادي' لغير الأقسام"""
        daira = DairaFactory.build(qism_role="planning")
        daira.full_clean()
        assert daira.qism_role == "regular"

    def test_qism_must_have_parent(self):
        """القسم يجب أن يتبع مديرية أو دائرة"""
        qism = QismFactory.build(parent=None)
        with pytest.raises(ValidationError) as exc:
            qism.full_clean()
        assert "القسم يجب أن يتبع مديرية أو دائرة" in str(exc.value)

    def test_organization_unit_str(self):
        """__str__ يرجع اسم الكيان"""
        daira = DairaFactory.build(name="دائرة الشؤون الإدارية")
        assert str(daira) == "دائرة الشؤون الإدارية"
