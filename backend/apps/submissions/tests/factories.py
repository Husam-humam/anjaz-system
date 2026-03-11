import factory
from django.utils import timezone
from datetime import timedelta

from apps.submissions.models import (
    WeeklyPeriod,
    WeeklySubmission,
    SubmissionAnswer,
    QismExtension,
)
from apps.organization.tests.factories import QismFactory
from apps.forms.tests.factories import FormTemplateFactory, FormTemplateItemFactory
from apps.accounts.tests.factories import StatisticsAdminFactory


class WeeklyPeriodFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = WeeklyPeriod

    year = 2025
    week_number = factory.Sequence(lambda n: n + 1)
    start_date = factory.LazyFunction(lambda: timezone.now().date())
    end_date = factory.LazyFunction(
        lambda: (timezone.now() + timedelta(days=6)).date()
    )
    deadline = factory.LazyFunction(lambda: timezone.now() + timedelta(days=7))
    status = "open"
    created_by = factory.SubFactory(StatisticsAdminFactory)


class WeeklySubmissionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = WeeklySubmission

    qism = factory.SubFactory(QismFactory)
    weekly_period = factory.SubFactory(WeeklyPeriodFactory)
    form_template = factory.SubFactory(FormTemplateFactory)
    status = "draft"


class SubmissionAnswerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SubmissionAnswer

    submission = factory.SubFactory(WeeklySubmissionFactory)
    form_item = factory.SubFactory(FormTemplateItemFactory)
    numeric_value = None
    text_value = ""
    is_qualitative = False
    qualitative_details = ""
    qualitative_status = "none"


class QismExtensionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = QismExtension

    qism = factory.SubFactory(QismFactory)
    weekly_period = factory.SubFactory(WeeklyPeriodFactory)
    new_deadline = factory.LazyFunction(
        lambda: timezone.now() + timedelta(days=14)
    )
    reason = "ظروف طارئة"
    granted_by = factory.SubFactory(StatisticsAdminFactory)
