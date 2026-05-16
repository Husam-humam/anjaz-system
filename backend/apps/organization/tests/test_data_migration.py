"""
اختبار منطق الـ data migration: تحويل qism_role='planning' إلى
PlanningAssignment + SupervisedUnit.

لا نستدعي migration framework مباشرةً (معقّد ضمن pytest-django) —
نستخرج الدالّة من ملف الـ migration ونُشغّلها يدوياً على Django models
الحاليّة (apps.get_model يعمل تماماً).
"""
import importlib

import pytest

from apps.organization.models import (
    OrganizationUnit,
    PlanningAssignment,
    QismRole,
    SupervisedUnit,
    UnitType,
)
from apps.organization.tests.factories import (
    DairaFactory,
    MudiriyaFactory,
    PlanningQismFactory,
    QismFactory,
)


def run_migration_forward():
    """يستدعي دالّة الـ migration باستخدام apps الحالي (موحَّد لكل الاختبارات)."""
    from django.apps import apps

    mod = importlib.import_module(
        'apps.organization.migrations.0004_migrate_qism_role_to_assignments'
    )
    mod.migrate_planning_qism_to_assignments(apps, schema_editor=None)


@pytest.mark.django_db
class TestPlanningMigration:

    def test_planner_under_mudiriya_gets_assignment(self):
        """قسم تخطيط تحت مديريّة → assignment + supervised = الأقسام الأخوة العاديّة."""
        mudiriya = MudiriyaFactory()
        planning = PlanningQismFactory(parent=mudiriya)
        regular_1 = QismFactory(parent=mudiriya)
        regular_2 = QismFactory(parent=mudiriya)
        # قسم تخطيط آخر تحت نفس المديرية — لا يُعتبر "تحت إشراف"
        another_planning = PlanningQismFactory(parent=mudiriya)

        run_migration_forward()

        # تخصيص للقسم الأول
        assignment = PlanningAssignment.objects.get(planning_unit=planning)
        assert assignment.context_parent_id == mudiriya.pk
        supervised_ids = set(
            assignment.supervised_units.values_list('unit_id', flat=True)
        )
        # نتأكّد أن الأقسام العاديّة فقط هي المُشرَف عليها
        assert regular_1.id in supervised_ids
        assert regular_2.id in supervised_ids
        # قسم التخطيط الآخر ليس "regular" → لا يُدرَج
        assert another_planning.id not in supervised_ids

    def test_planner_without_parent_gets_empty_assignment(self):
        """قسم تخطيط بدون parent → assignment فارغ (admin يُضيف يدوياً)."""
        # نُنشئ بـ qism_role='planning' لكن بدون parent باستخدام bypass
        planning = OrganizationUnit(
            name='قسم تخطيط مركزي',
            code='CENTRAL-PLAN',
            unit_type=UnitType.QISM,
            qism_role=QismRole.PLANNING,
            parent=None,
            lft=0, rght=0, tree_id=0, level=0,
        )
        planning.save_base()
        # إعادة بناء MPTT لجعل الكائن قابلاً للاستخدام
        OrganizationUnit.objects.rebuild()

        run_migration_forward()

        assignment = PlanningAssignment.objects.get(planning_unit=planning)
        assert assignment.context_parent_id is None
        assert assignment.supervised_units.count() == 0

    def test_migration_is_idempotent(self):
        """تشغيل الـ migration مرّتَين لا يُكرّر التخصيصات."""
        mudiriya = MudiriyaFactory()
        planning = PlanningQismFactory(parent=mudiriya)
        QismFactory(parent=mudiriya)

        run_migration_forward()
        first_count = PlanningAssignment.objects.count()
        first_supervised = SupervisedUnit.objects.count()

        # تشغيل ثانٍ
        run_migration_forward()
        assert PlanningAssignment.objects.count() == first_count
        assert SupervisedUnit.objects.count() == first_supervised

    def test_inactive_units_not_supervised(self):
        """الأقسام المُعطَّلة لا تُشمَل في supervised."""
        mudiriya = MudiriyaFactory()
        planning = PlanningQismFactory(parent=mudiriya)
        active = QismFactory(parent=mudiriya, is_active=True)
        inactive = QismFactory(parent=mudiriya, is_active=False)

        run_migration_forward()

        assignment = PlanningAssignment.objects.get(planning_unit=planning)
        supervised_ids = set(
            assignment.supervised_units.values_list('unit_id', flat=True)
        )
        assert active.id in supervised_ids
        assert inactive.id not in supervised_ids

    def test_planner_under_daira_gets_deep_descendants(self):
        """قسم تخطيط على مستوى دائرة → يُشرف على كل أقسامها الفرعيّة."""
        daira = DairaFactory()
        mudiriya = MudiriyaFactory(parent=daira)
        planning_at_daira = PlanningQismFactory(parent=daira)
        qism_under_mudiriya = QismFactory(parent=mudiriya)
        qism_under_daira_directly = QismFactory(parent=daira)

        run_migration_forward()

        assignment = PlanningAssignment.objects.get(planning_unit=planning_at_daira)
        supervised_ids = set(
            assignment.supervised_units.values_list('unit_id', flat=True)
        )
        # كلا القسمَين يجب أن يكونا تحت إشرافه
        assert qism_under_mudiriya.id in supervised_ids
        assert qism_under_daira_directly.id in supervised_ids
