"""
اختبارات منطق الصلاحيّات الجديد المبني على PlanningAssignment + ViewScope.

تركيز:
- _planning_section_scope_qism_ids يعتمد على SupervisedUnit عند وجوده
- يعود للـ MPTT legacy إن لم يوجد assignment
- _user_view_scope_qism_ids يدمج managed + ViewScope
- viewer يعود set() من scope الإدارة و فقط ViewScope من scope الرؤية
- IsNotViewer permission يمنع الإجراءات
"""
import pytest
from rest_framework.test import APIRequestFactory

from apps.accounts.models import UserRole
from apps.accounts.tests.factories import (
    PlanningSectionUserFactory,
    SectionManagerFactory,
    StatisticsAdminFactory,
    ViewerFactory,
)
from apps.organization.models import (
    PlanningAssignment,
    SupervisedUnit,
    ViewScope,
)
from apps.organization.tests.factories import (
    MudiriyaFactory,
    PlanningQismFactory,
    QismFactory,
)
from apps.submissions.permissions import IsNotViewer
from apps.submissions.services import (
    _planning_section_scope_qism_ids,
    _user_can_review_submissions,
    _user_view_scope_qism_ids,
)


@pytest.mark.django_db
class TestManageScopeWithAssignment:
    """نطاق الإدارة يعتمد على SupervisedUnit عند وجود assignment."""

    def test_planner_with_assignment_manages_supervised_only(self):
        planning_unit = PlanningQismFactory()
        planner = PlanningSectionUserFactory(unit=planning_unit)
        # تخصيص: يدير ٢ من ٣ أقسام موجودة
        q1 = QismFactory()
        q2 = QismFactory()
        q3 = QismFactory()
        assignment = PlanningAssignment.objects.create(planning_unit=planning_unit)
        SupervisedUnit.objects.create(assignment=assignment, unit=q1)
        SupervisedUnit.objects.create(assignment=assignment, unit=q2)

        scope = _planning_section_scope_qism_ids(planner)

        assert scope == {q1.id, q2.id}
        assert q3.id not in scope

    def test_planner_without_assignment_has_empty_scope(self):
        """بعد Phase F: لا يوجد MPTT fallback. بدون assignment = نطاق فارغ."""
        mudiriya = MudiriyaFactory()
        planning_unit = PlanningQismFactory(parent=mudiriya)
        planner = PlanningSectionUserFactory(unit=planning_unit)
        QismFactory(parent=mudiriya)  # أخ في نفس المديرية — لكنه ليس supervised

        scope = _planning_section_scope_qism_ids(planner)

        # بدون PlanningAssignment: لا نطاق
        assert scope == set()

    def test_section_manager_not_a_planner(self):
        """
        section_manager ليس planner — `_planning_section_scope_qism_ids` لا
        تنطبق عليه. نطاق section_manager = {user.unit_id} يُعالَج في querysets.
        """
        qism = QismFactory()
        mgr = SectionManagerFactory(unit=qism)
        # الدالة تُرجع set() لأنه لا يوجد PlanningAssignment لقسم section_manager
        assert _planning_section_scope_qism_ids(mgr) == set()

    def test_viewer_manages_nothing(self):
        viewer = ViewerFactory()
        assert _planning_section_scope_qism_ids(viewer) == set()

    def test_admin_manages_everything(self):
        admin = StatisticsAdminFactory()
        # دلالة `None` = نطاق كامل (لكن admin لا يستخدم هذه الدالّة عادةً)
        # فحص _user_view_scope_qism_ids يكفي
        assert _user_view_scope_qism_ids(admin) is None


@pytest.mark.django_db
class TestViewScopeForPlanner:
    """ViewScope يُضيف وحدات لرؤية المخطّط فقط."""

    def test_planner_view_scope_includes_managed_plus_viewscope(self):
        planning_unit = PlanningQismFactory()
        planner = PlanningSectionUserFactory(unit=planning_unit)
        managed = QismFactory()
        view_only = QismFactory()
        # تخصيص الإدارة
        assignment = PlanningAssignment.objects.create(planning_unit=planning_unit)
        SupervisedUnit.objects.create(assignment=assignment, unit=managed)
        # ViewScope إضافة (مثلاً تخطيط دائرة يطّلع على أقسام مديريّاتها)
        scope = ViewScope.objects.create(user=planner)
        scope.viewable_units.add(view_only)

        view_ids = _user_view_scope_qism_ids(planner)

        assert managed.id in view_ids
        assert view_only.id in view_ids

    def test_planner_without_viewscope_sees_only_managed(self):
        planning_unit = PlanningQismFactory()
        planner = PlanningSectionUserFactory(unit=planning_unit)
        managed = QismFactory()
        assignment = PlanningAssignment.objects.create(planning_unit=planning_unit)
        SupervisedUnit.objects.create(assignment=assignment, unit=managed)

        view_ids = _user_view_scope_qism_ids(planner)
        assert view_ids == {managed.id}


@pytest.mark.django_db
class TestViewScopeForViewer:
    """viewer يرى فقط ViewScope.viewable_units."""

    def test_viewer_sees_only_viewscope_units(self):
        viewer = ViewerFactory()
        q1 = QismFactory()
        q2 = QismFactory()
        q3 = QismFactory()
        scope = ViewScope.objects.create(user=viewer)
        scope.viewable_units.add(q1, q2)

        view_ids = _user_view_scope_qism_ids(viewer)

        assert view_ids == {q1.id, q2.id}
        assert q3.id not in view_ids

    def test_viewer_without_viewscope_sees_nothing(self):
        viewer = ViewerFactory()
        view_ids = _user_view_scope_qism_ids(viewer)
        assert view_ids == set()

    def test_viewer_manages_nothing_even_with_viewscope(self):
        """ViewScope لا يمنح صلاحيّة الإدارة — فقط الرؤية."""
        viewer = ViewerFactory()
        q1 = QismFactory()
        scope = ViewScope.objects.create(user=viewer)
        scope.viewable_units.add(q1)

        assert _planning_section_scope_qism_ids(viewer) == set()


@pytest.mark.django_db
class TestUserCanReviewSubmissions:

    def test_viewer_cannot_review(self):
        viewer = ViewerFactory()
        assert _user_can_review_submissions(viewer) is False

    def test_section_manager_can_review(self):
        assert _user_can_review_submissions(SectionManagerFactory(unit=QismFactory())) is True

    def test_planner_can_review(self):
        assert _user_can_review_submissions(PlanningSectionUserFactory()) is True

    def test_admin_can_review(self):
        assert _user_can_review_submissions(StatisticsAdminFactory()) is True


@pytest.mark.django_db
class TestIsNotViewerPermission:
    """صلاحيّة `IsNotViewer` تمنع viewer من الإجراءات وتسمح بالـ GET."""

    def setup_method(self):
        self.factory = APIRequestFactory()
        self.perm = IsNotViewer()

    def _check(self, method, user):
        request = getattr(self.factory, method.lower())('/test/')
        request.user = user
        return self.perm.has_permission(request, view=None)

    def test_viewer_blocked_from_post(self):
        viewer = ViewerFactory()
        assert self._check('post', viewer) is False

    def test_viewer_blocked_from_patch_and_delete(self):
        viewer = ViewerFactory()
        assert self._check('patch', viewer) is False
        assert self._check('delete', viewer) is False

    def test_viewer_allowed_get(self):
        viewer = ViewerFactory()
        assert self._check('get', viewer) is True

    def test_planner_allowed_all_methods(self):
        planner = PlanningSectionUserFactory()
        assert self._check('post', planner) is True
        assert self._check('patch', planner) is True
        assert self._check('get', planner) is True

    def test_admin_allowed_all_methods(self):
        admin = StatisticsAdminFactory()
        assert self._check('post', admin) is True
        assert self._check('delete', admin) is True
