import factory
from apps.organization.models import OrganizationUnit


class DairaFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = OrganizationUnit

    name = factory.Sequence(lambda n: f"دائرة {n}")
    code = factory.Sequence(lambda n: f"D{n:03d}")
    unit_type = "daira"
    qism_role = "regular"
    parent = None


class MudiriyaFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = OrganizationUnit

    name = factory.Sequence(lambda n: f"مديرية {n}")
    code = factory.Sequence(lambda n: f"M{n:03d}")
    unit_type = "mudiriya"
    qism_role = "regular"
    parent = factory.SubFactory(DairaFactory)


class QismFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = OrganizationUnit

    name = factory.Sequence(lambda n: f"قسم {n}")
    code = factory.Sequence(lambda n: f"Q{n:03d}")
    unit_type = "qism"
    qism_role = "regular"
    parent = factory.SubFactory(MudiriyaFactory)


class PlanningQismFactory(QismFactory):
    qism_role = "planning"


class StatisticsQismFactory(QismFactory):
    qism_role = "statistics"
