import factory
from apps.targets.models import Target
from apps.organization.tests.factories import QismFactory
from apps.indicators.tests.factories import IndicatorFactory
from apps.accounts.tests.factories import StatisticsAdminFactory


class TargetFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Target

    qism = factory.SubFactory(QismFactory)
    indicator = factory.SubFactory(IndicatorFactory)
    year = 2025
    target_value = 100.0
    set_by = factory.SubFactory(StatisticsAdminFactory)
    notes = ""
