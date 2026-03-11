import factory
from apps.indicators.models import Indicator, IndicatorCategory
from apps.accounts.tests.factories import StatisticsAdminFactory


class IndicatorCategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = IndicatorCategory

    name = factory.Sequence(lambda n: f"تصنيف {n}")
    is_active = True


class IndicatorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Indicator

    name = factory.Sequence(lambda n: f"مؤشر {n}")
    unit_type = "number"
    unit_label = "جهاز"
    accumulation_type = "sum"
    category = factory.SubFactory(IndicatorCategoryFactory)
    is_active = True
    created_by = factory.SubFactory(StatisticsAdminFactory)
