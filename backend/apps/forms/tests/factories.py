import factory
from apps.forms.models import FormTemplate, FormTemplateItem
from apps.organization.tests.factories import QismFactory
from apps.accounts.tests.factories import PlanningSectionUserFactory
from apps.indicators.tests.factories import IndicatorFactory


class FormTemplateFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = FormTemplate

    qism = factory.SubFactory(QismFactory)
    version = 1
    status = "draft"
    created_by = factory.SubFactory(PlanningSectionUserFactory)


class FormTemplateItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = FormTemplateItem

    form_template = factory.SubFactory(FormTemplateFactory)
    indicator = factory.SubFactory(IndicatorFactory)
    is_mandatory = False
    display_order = factory.Sequence(lambda n: n)
