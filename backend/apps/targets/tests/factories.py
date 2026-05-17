import factory
from apps.targets.models import Target
from apps.organization.tests.factories import QismFactory
from apps.indicators.tests.factories import IndicatorFactory
from apps.accounts.tests.factories import StatisticsAdminFactory


class TargetFactory(factory.django.DjangoModelFactory):
    """مصنع مستهدفات مركّبة.

    الاستخدام:
    - TargetFactory()                          → مستهدف بمؤشّر عشوائي واحد
    - TargetFactory(indicators=[ind1, ind2])   → مستهدف بمكوّنات صريحة
    - TargetFactory(scope_unit=None)           → مستهدف على مستوى المؤسسة
    """
    class Meta:
        model = Target
        skip_postgeneration_save = True

    name = factory.Sequence(lambda n: f"مستهدف {n}")
    scope_unit = factory.SubFactory(QismFactory)
    year = 2025
    target_value = 100.0
    set_by = factory.SubFactory(StatisticsAdminFactory)
    notes = ""

    @factory.post_generation
    def indicators(obj, create, extracted, **kwargs):
        """ربط المؤشّرات (M2M).

        - إن مُرّر `indicators=[...]` صراحة: تُربَط هذه المؤشّرات.
        - وإلّا: يُنشَأ مؤشّر افتراضي واحد ويُربَط.
        """
        if not create:
            return
        if extracted:
            obj.indicators.set(extracted)
        else:
            obj.indicators.add(IndicatorFactory())
