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
    """اختبارات التحقق من صحة العلاقة بين دور المستخدم والوحدة التنظيمية.

    بعد Phase F: لم تَعُد قاعدة «نوع القسم» (qism_role) موجودة. التحقّق
    الوحيد المتبقّي هو أن:
    - section_manager و planning_section يجب أن يكون لهما `unit`
    - statistics_admin و viewer لا يحتاجان وحدة
    """

    def test_section_manager_must_have_unit(self):
        """مدير القسم يجب أن يكون مرتبطاً بوحدة (لا يُسمح بدون unit)."""
        user = User(
            username="manager_no_unit",
            full_name="مدير بلا قسم",
            role="section_manager",
            unit=None,
        )
        with pytest.raises(ValidationError) as exc:
            user.full_clean()
        assert "مدير القسم يجب أن يكون مرتبطاً بقسم" in str(exc.value)

    def test_planning_section_must_have_unit(self):
        """قسم التخطيط يجب أن يكون مرتبطاً بوحدة."""
        user = User(
            username="planner_no_unit",
            full_name="مخطط بلا وحدة",
            role="planning_section",
            unit=None,
        )
        with pytest.raises(ValidationError) as exc:
            user.full_clean()
        assert "قسم التخطيط يجب أن يرتبط بوحدة" in str(exc.value)

    def test_section_manager_valid_with_any_qism(self):
        """بعد Phase F: مدير القسم صالح مع أي قسم بصرف النظر عن «نوعه»."""
        # قسم تخطيط أو قسم عادي — كلاهما مقبول الآن (لا يوجد qism_role)
        planning_qism = PlanningQismFactory()
        user = User(
            username="manager_any",
            full_name="مدير قسم",
            role="section_manager",
            unit=planning_qism,
        )
        user.set_password("pwd123")
        user.full_clean()  # يجب ألا يرفع استثناء

    def test_user_str_returns_full_name(self):
        """__str__ يرجع الاسم الكامل"""
        user = StatisticsAdminFactory(full_name="أحمد محمد")
        assert str(user) == "أحمد محمد"

    def test_statistics_admin_valid_without_unit(self):
        """بعد Phase F: مدير الإحصاء لا يحتاج وحدة على الإطلاق."""
        user = User(
            username="admin_no_unit",
            full_name="مدير إحصاء بلا وحدة",
            role="statistics_admin",
            unit=None,
        )
        user.set_password("pwd123")
        user.full_clean()  # يجب ألا يرفع استثناء

    def test_statistics_admin_valid_with_any_unit(self):
        """مدير الإحصاء صالح مع أي وحدة (لا قيود على النوع)."""
        stats_qism = StatisticsQismFactory()
        user = User(
            username="valid_admin",
            full_name="مدير إحصاء صالح",
            role="statistics_admin",
            unit=stats_qism,
        )
        user.set_password("pwd123")
        user.full_clean()  # يجب ألا يرفع استثناء

    def test_viewer_valid_without_unit(self):
        """دور viewer لا يستلزم وحدة."""
        user = User(
            username="viewer_no_unit",
            full_name="مُطّلِع بلا وحدة",
            role="viewer",
            unit=None,
        )
        user.set_password("pwd123")
        user.full_clean()  # يجب ألا يرفع استثناء
