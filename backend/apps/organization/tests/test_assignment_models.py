"""
اختبارات نماذج التخصيصات: PlanningAssignment، SupervisedUnit، ViewScope.

تركيز:
- قيد OneToOne على planning_unit (لا تكرار)
- قيد OneToOne على supervised unit (مُشرف واحد لكل قسم)
- منع supervised = planning (self-reference)
- ViewScope per-user (OneToOne)
- M2M viewable_units يعمل بشكل صحيح
"""
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.accounts.models import UserRole
from apps.accounts.tests.factories import (
    PlanningSectionUserFactory,
    SectionManagerFactory,
    StatisticsAdminFactory,
)
from apps.organization.models import (
    OrganizationUnit,
    PlanningAssignment,
    SupervisedUnit,
    UnitType,
    ViewScope,
)
from apps.organization.tests.factories import QismFactory


@pytest.mark.django_db
class TestPlanningAssignment:

    def test_create_assignment_basic(self):
        qism = QismFactory()
        a = PlanningAssignment.objects.create(planning_unit=qism)
        assert a.pk is not None
        assert a.planning_unit_id == qism.pk
        assert a.context_parent is None
        assert a.notes == ''

    def test_same_unit_cannot_have_two_assignments(self):
        """OneToOne على planning_unit يمنع التكرار على مستوى DB."""
        qism = QismFactory()
        PlanningAssignment.objects.create(planning_unit=qism)
        with transaction.atomic():
            with pytest.raises(IntegrityError):
                PlanningAssignment.objects.create(planning_unit=qism)

    def test_context_parent_optional(self):
        qism = QismFactory()
        daira = OrganizationUnit.objects.create(
            name='دائرة أ', code='D-CTX', unit_type=UnitType.DAIRA,
        )
        a = PlanningAssignment.objects.create(
            planning_unit=qism, context_parent=daira,
        )
        assert a.context_parent_id == daira.pk

    def test_str_representation(self):
        qism = QismFactory(name='قسم التخطيط في HR')
        a = PlanningAssignment.objects.create(planning_unit=qism)
        assert 'قسم التخطيط في HR' in str(a)
        assert 'تخطيط' in str(a)


@pytest.mark.django_db
class TestSupervisedUnit:

    def _make_assignment(self):
        planning = QismFactory(name='قسم تخطيط')
        return PlanningAssignment.objects.create(planning_unit=planning)

    def test_link_qism_to_assignment(self):
        assignment = self._make_assignment()
        qism = QismFactory(name='قسم مُراقَب')
        link = SupervisedUnit.objects.create(assignment=assignment, unit=qism)
        assert link.pk is not None
        assert link.unit_id == qism.pk

    def test_same_unit_cannot_be_supervised_twice(self):
        """OneToOne على unit يضمن مُشرف واحد لكل وحدة."""
        a1 = self._make_assignment()
        a2 = PlanningAssignment.objects.create(planning_unit=QismFactory())
        qism = QismFactory()
        SupervisedUnit.objects.create(assignment=a1, unit=qism)
        with transaction.atomic():
            with pytest.raises(IntegrityError):
                SupervisedUnit.objects.create(assignment=a2, unit=qism)

    def test_unit_cannot_supervise_itself(self):
        """قسم التخطيط لا يُشرف على نفسه."""
        assignment = self._make_assignment()
        with pytest.raises(ValidationError, match='لا يمكن لقسم التخطيط'):
            SupervisedUnit(
                assignment=assignment,
                unit=assignment.planning_unit,
            ).full_clean()

    def test_assignment_can_have_many_supervised_units(self):
        assignment = self._make_assignment()
        q1 = QismFactory()
        q2 = QismFactory()
        q3 = QismFactory()
        SupervisedUnit.objects.create(assignment=assignment, unit=q1)
        SupervisedUnit.objects.create(assignment=assignment, unit=q2)
        SupervisedUnit.objects.create(assignment=assignment, unit=q3)
        assert assignment.supervised_units.count() == 3

    def test_cascade_delete_when_assignment_removed(self):
        """حذف assignment يحذف كل SupervisedUnit المرتبطة (CASCADE)."""
        assignment = self._make_assignment()
        qism = QismFactory()
        link = SupervisedUnit.objects.create(assignment=assignment, unit=qism)
        link_id = link.pk
        assignment.delete()
        assert not SupervisedUnit.objects.filter(pk=link_id).exists()


@pytest.mark.django_db
class TestViewScope:

    def test_create_view_scope_for_user(self):
        user = StatisticsAdminFactory()  # أي مستخدم
        scope = ViewScope.objects.create(user=user)
        assert scope.pk is not None
        assert scope.viewable_units.count() == 0

    def test_one_view_scope_per_user(self):
        user = StatisticsAdminFactory()
        ViewScope.objects.create(user=user)
        with transaction.atomic():
            with pytest.raises(IntegrityError):
                ViewScope.objects.create(user=user)

    def test_add_viewable_units(self):
        user = StatisticsAdminFactory()
        scope = ViewScope.objects.create(user=user)
        q1 = QismFactory()
        q2 = QismFactory()
        scope.viewable_units.add(q1, q2)
        assert scope.viewable_units.count() == 2
        assert q1 in scope.viewable_units.all()

    def test_cascade_delete_when_user_removed(self):
        user = StatisticsAdminFactory()
        scope = ViewScope.objects.create(user=user)
        scope_id = scope.pk
        user.delete()
        assert not ViewScope.objects.filter(pk=scope_id).exists()


@pytest.mark.django_db
class TestViewerRoleEnum:

    def test_viewer_in_choices(self):
        choices = dict(UserRole.choices)
        assert 'viewer' in choices
        assert choices['viewer'] == 'مُطّلِع'

    def test_user_with_viewer_role_no_unit_required(self):
        """دور viewer لا يستلزم وحدة (نطاقه يأتي من ViewScope)."""
        from apps.accounts.models import User
        u = User(
            username='viewer1', full_name='مُطّلِع',
            role=UserRole.VIEWER, unit=None,
        )
        u.set_password('test123')
        u.full_clean()  # يجب ألاّ يرفع استثناء
        u.save()
        assert u.pk is not None
