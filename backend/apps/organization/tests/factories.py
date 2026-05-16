import factory

from apps.organization.models import (
    OrganizationUnit,
    PlanningAssignment,
    SupervisedUnit,
)


class DairaFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = OrganizationUnit

    name = factory.Sequence(lambda n: f"دائرة {n}")
    code = factory.Sequence(lambda n: f"D{n:03d}")
    unit_type = "daira"
    parent = None


class MudiriyaFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = OrganizationUnit

    name = factory.Sequence(lambda n: f"مديرية {n}")
    code = factory.Sequence(lambda n: f"M{n:03d}")
    unit_type = "mudiriya"
    parent = factory.SubFactory(DairaFactory)


class QismFactory(factory.django.DjangoModelFactory):
    """
    قسم عام — افتراضياً يُنشأ بـ SupervisedUnit (قابل للتقديم).

    لتعطيل ذلك، استخدم: QismFactory(_create_supervisor=False)
    أو استخدم PlanningQismFactory للحصول على قسم تخطيط.
    """
    class Meta:
        model = OrganizationUnit
        skip_postgeneration_save = True

    name = factory.Sequence(lambda n: f"قسم {n}")
    code = factory.Sequence(lambda n: f"Q{n:03d}")
    unit_type = "qism"
    parent = factory.SubFactory(MudiriyaFactory)

    class Params:
        # عند True (افتراضي): يُنشأ SupervisedUnit مع mock planning unit
        # عند False: قسم خام بدون أي تخصيص (يدويّ)
        with_supervisor = False

    @factory.post_generation
    def _create_supervisor(obj, create, extracted, **kwargs):
        """لا نُنشئ SupervisedUnit افتراضياً — التحكم في التخصيصات يكون
        صريحاً في كل اختبار حسب حاجته."""
        return


class PlanningQismFactory(QismFactory):
    """
    قسم تخطيط — اسماً وكوداً فقط (لا يُنشئ PlanningAssignment تلقائياً).

    لإنشاء planning section كامل: استخدم هذا الـ factory ثم أنشئ
    PlanningAssignment يدوياً في الاختبار. هذا التحكّم الصريح يجنّب
    تعارضات الإنشاء المُكرّر.
    """
    name = factory.Sequence(lambda n: f"قسم تخطيط {n}")
    code = factory.Sequence(lambda n: f"P{n:03d}")


class StatisticsQismFactory(QismFactory):
    """
    قسم إحصاء — بعد Phase F: قسم عادي بدون تمييز خاصّ.
    statistics_admin role لا يحتاج لربط بوحدة من نوع معيّن.
    يُحتفَظ بالـ factory للتوافق الخلفي لكن دون أي سلوك خاصّ.
    """
    name = factory.Sequence(lambda n: f"قسم إحصاء {n}")
    code = factory.Sequence(lambda n: f"S{n:03d}")


class SupervisedQismFactory(QismFactory):
    """قسم مُسنَد للتقديم — يُنشأ مع SupervisedUnit إلى planner مُحدَّد."""

    @factory.post_generation
    def _supervise_under(obj, create, extracted, **kwargs):
        """
        Pass `_supervise_under=<PlanningAssignment instance>` لربط القسم.
        إن لم يُمرَّر شيء، يُنشأ planning_unit + assignment تلقائياً.
        """
        if not create:
            return
        if isinstance(extracted, PlanningAssignment):
            assignment = extracted
        else:
            planning_unit = PlanningQismFactory(parent=obj.parent)
            assignment = PlanningAssignment.objects.get(planning_unit=planning_unit)
        SupervisedUnit.objects.create(assignment=assignment, unit=obj)
