import pytest
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from apps.organization.tests.factories import (
    QismFactory,
    PlanningQismFactory,
    StatisticsQismFactory,
    MudiriyaFactory,
)
from .factories import (
    StatisticsAdminFactory,
    PlanningSectionUserFactory,
    SectionManagerFactory,
)

User = get_user_model()


@pytest.mark.django_db
class TestUserRoleUnitValidation:
    """اختبارات التحقق من صحة العلاقة بين دور المستخدم ونوع الوحدة التنظيمية"""

    def test_statistics_admin_must_link_to_statistics_qism(self):
        """مدير الإحصاء يجب أن يرتبط بقسم إحصاء"""
        regular_qism = QismFactory()
        user = User(
            username="invalid_admin",
            full_name="مدير خاطئ",
            role="statistics_admin",
            unit=regular_qism,
        )
        with pytest.raises(ValidationError) as exc:
            user.full_clean()
        assert "مدير قسم الإحصاء يجب أن يرتبط بقسم من نوع" in str(exc.value)

    def test_planning_section_must_link_to_planning_qism(self):
        """قسم التخطيط يجب أن يرتبط بقسم تخطيط"""
        regular_qism = QismFactory()
        user = User(
            username="invalid_planner",
            full_name="مخطط خاطئ",
            role="planning_section",
            unit=regular_qism,
        )
        with pytest.raises(ValidationError) as exc:
            user.full_clean()
        assert "قسم التخطيط يجب أن يرتبط بقسم من نوع" in str(exc.value)

    def test_section_manager_must_link_to_regular_qism(self):
        """مدير القسم يجب أن يرتبط بقسم عادي"""
        planning_qism = PlanningQismFactory()
        user = User(
            username="invalid_manager",
            full_name="مدير خاطئ",
            role="section_manager",
            unit=planning_qism,
        )
        with pytest.raises(ValidationError) as exc:
            user.full_clean()
        assert "مدير القسم يجب أن يرتبط بقسم من نوع" in str(exc.value)

    def test_user_str_returns_full_name(self):
        """__str__ يرجع الاسم الكامل"""
        user = StatisticsAdminFactory(full_name="أحمد محمد")
        assert str(user) == "أحمد محمد"

    def test_statistics_admin_valid_with_statistics_qism(self):
        """مدير الإحصاء صالح عند ارتباطه بقسم إحصاء"""
        stats_qism = StatisticsQismFactory()
        user = User(
            username="valid_admin",
            full_name="مدير إحصاء صالح",
            role="statistics_admin",
            unit=stats_qism,
        )
        user.full_clean()  # يجب ألا يرفع استثناء

    def test_user_must_link_to_qism_not_mudiriya(self):
        """المستخدم يجب أن يرتبط بقسم وليس مديرية"""
        mudiriya = MudiriyaFactory()
        user = User(
            username="invalid_user",
            full_name="مستخدم خاطئ",
            role="section_manager",
            unit=mudiriya,
        )
        with pytest.raises(ValidationError) as exc:
            user.full_clean()
        assert "يجب أن تكون الوحدة التنظيمية من نوع" in str(exc.value)
