import factory
from django.contrib.auth import get_user_model

from apps.organization.tests.factories import (
    QismFactory,
    PlanningQismFactory,
    StatisticsQismFactory,
)

User = get_user_model()


class StatisticsAdminFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"admin_{n}")
    full_name = factory.Sequence(lambda n: f"مدير إحصاء {n}")
    role = "statistics_admin"
    unit = factory.SubFactory(StatisticsQismFactory)
    password = factory.PostGenerationMethodCall('set_password', 'password123')


class PlanningSectionUserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"planner_{n}")
    full_name = factory.Sequence(lambda n: f"مخطط {n}")
    role = "planning_section"
    unit = factory.SubFactory(PlanningQismFactory)
    password = factory.PostGenerationMethodCall('set_password', 'password123')


class SectionManagerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"manager_{n}")
    full_name = factory.Sequence(lambda n: f"مدير قسم {n}")
    role = "section_manager"
    unit = factory.SubFactory(QismFactory)
    password = factory.PostGenerationMethodCall('set_password', 'password123')


class ViewerFactory(factory.django.DjangoModelFactory):
    """مستخدم بدور viewer — لا يستلزم وحدة."""
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"viewer_{n}")
    full_name = factory.Sequence(lambda n: f"مُطّلِع {n}")
    role = "viewer"
    unit = None
    password = factory.PostGenerationMethodCall('set_password', 'password123')


# Generic alias — useful for tests that need any user
UserFactory = StatisticsAdminFactory
