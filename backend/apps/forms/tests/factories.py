import factory
from apps.forms.models import FormTemplate, FormTemplateItem
from apps.organization.models import PlanningAssignment, SupervisedUnit
from apps.organization.tests.factories import PlanningQismFactory, QismFactory
from apps.accounts.tests.factories import PlanningSectionUserFactory
from apps.indicators.tests.factories import IndicatorFactory


class FormTemplateFactory(factory.django.DjangoModelFactory):
    """
    قالب استمارة — يُنشئ تلقائياً قسماً مُسنَداً للتقديم
    (مع PlanningAssignment + SupervisedUnit عند الحاجة) ليمرّ التحقّق.
    """
    class Meta:
        model = FormTemplate
        skip_postgeneration_save = True

    qism = factory.SubFactory(QismFactory)
    version = 1
    status = "draft"
    created_by = factory.SubFactory(PlanningSectionUserFactory)

    @factory.post_generation
    def _ensure_supervisor(obj, create, extracted, **kwargs):
        """ضمان أن الـ qism له SupervisedUnit حتى تنجح full_clean على FormTemplate."""
        if not create:
            return
        if hasattr(obj.qism, 'supervisor_link'):
            return  # موجود مسبقاً
        # ننشئ planning unit بسيط ونربط القسم به
        planning = PlanningQismFactory(parent=obj.qism.parent)
        assignment, _ = PlanningAssignment.objects.get_or_create(planning_unit=planning)
        SupervisedUnit.objects.get_or_create(assignment=assignment, unit=obj.qism)


class FormTemplateItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = FormTemplateItem

    form_template = factory.SubFactory(FormTemplateFactory)
    indicator = factory.SubFactory(IndicatorFactory)
    is_mandatory = False
    display_order = factory.Sequence(lambda n: n)
