"""
Data migration: تحويل بيانات `qism_role='planning'` إلى نموذج
PlanningAssignment + SupervisedUnit الجديد.

المنطق:
1. لكل وحدة بـ `qism_role='planning'`:
   - إنشاء PlanningAssignment(planning_unit=unit, context_parent=unit.parent)
   - إن لم يكن لها parent: تُنشأ بدون supervised (admin يضيف لاحقاً)
2. لكل أقسام `qism_role='regular' AND is_active=True` تحت نفس الـ parent:
   - إنشاء SupervisedUnit(assignment, unit)
   - إذا كان القسم مُسنَداً مسبقاً لمخطّط آخر (OneToOne على unit) → تخطّي مع log

ملاحظات:
- لا نلمس `qism_role` ولا الـ field نفسه — يبقى للـ rollback (سيُحذف في Phase F)
- آمن للتشغيل المتكرّر (idempotent) — get_or_create للـ assignments
- العكس reverse_code يحذف كل PlanningAssignment + SupervisedUnit
  التي أُنشئت بهذه المهاجرة (يتعرّف عليها بأن context_parent matches)
"""
import logging

from django.db import migrations

logger = logging.getLogger(__name__)


def migrate_planning_qism_to_assignments(apps, schema_editor):
    """تحويل qism_role='planning' إلى PlanningAssignment + SupervisedUnit."""
    OrganizationUnit = apps.get_model('organization', 'OrganizationUnit')
    PlanningAssignment = apps.get_model('organization', 'PlanningAssignment')
    SupervisedUnit = apps.get_model('organization', 'SupervisedUnit')

    planning_units = OrganizationUnit.objects.filter(
        unit_type='qism', qism_role='planning'
    )

    created_assignments = 0
    created_supervisions = 0
    skipped_conflicts = 0

    for planning_unit in planning_units:
        # 1. إنشاء PlanningAssignment (idempotent via get_or_create)
        assignment, was_created = PlanningAssignment.objects.get_or_create(
            planning_unit=planning_unit,
            defaults={
                'context_parent': planning_unit.parent,
                'notes': (
                    'تخصيص تلقائي من البيانات السابقة (qism_role=planning). '
                    f'الوحدة الأم: {planning_unit.parent.name if planning_unit.parent else "—"}.'
                ),
            },
        )
        if was_created:
            created_assignments += 1

        # 2. إيجاد الأقسام تحت الإشراف (إن وُجد parent)
        if planning_unit.parent_id is None:
            logger.info(
                'قسم تخطيط %s بدون parent — يُنشأ بدون أقسام مُشرَف عليها. '
                'يمكن للأدمن إضافتها يدوياً لاحقاً.',
                planning_unit.name,
            )
            continue

        # نستخدم MPTT manually عبر lft/rght لأن historical migrations
        # لا تملك ميثودات MPTT مثل get_descendants
        parent = planning_unit.parent
        # الأحفاد = نفس tree_id و lft/rght بداخل النطاق، باستثناء الـ parent نفسه
        regular_descendants = OrganizationUnit.objects.filter(
            tree_id=parent.tree_id,
            lft__gt=parent.lft,
            rght__lt=parent.rght,
            unit_type='qism',
            qism_role='regular',
            is_active=True,
        )

        for unit in regular_descendants:
            # SupervisedUnit.unit هو OneToOne — لا يمكن إعادة الإسناد
            if SupervisedUnit.objects.filter(unit=unit).exists():
                logger.info(
                    'قسم %s مُسنَد مسبقاً لمخطّط آخر — تخطّي.', unit.name
                )
                skipped_conflicts += 1
                continue
            SupervisedUnit.objects.create(assignment=assignment, unit=unit)
            created_supervisions += 1

    logger.info(
        'الهجرة اكتملت: %d تخصيصات، %d قسم مُشرَف عليه، %d تجاوزات.',
        created_assignments, created_supervisions, skipped_conflicts,
    )


def reverse_migration(apps, schema_editor):
    """
    العكس: حذف كل PlanningAssignment وSupervisedUnit.
    آمن لأن الهجرة الحاليّة هي مصدرها الوحيد قبل Phase G (الواجهة).
    """
    PlanningAssignment = apps.get_model('organization', 'PlanningAssignment')
    SupervisedUnit = apps.get_model('organization', 'SupervisedUnit')
    SupervisedUnit.objects.all().delete()
    PlanningAssignment.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('organization', '0003_planningassignment_viewscope_supervisedunit'),
    ]

    operations = [
        migrations.RunPython(
            migrate_planning_qism_to_assignments,
            reverse_migration,
        ),
    ]
