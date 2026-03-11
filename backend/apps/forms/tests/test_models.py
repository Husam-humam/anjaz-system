import pytest
from django.core.exceptions import ValidationError

from apps.organization.tests.factories import QismFactory, PlanningQismFactory
from .factories import FormTemplateFactory, FormTemplateItemFactory


@pytest.mark.django_db
class TestFormTemplateValidation:
    """اختبارات التحقق من صحة قوالب الاستمارات"""

    def test_form_template_must_be_for_regular_qism(self):
        """قالب الاستمارة يجب أن يكون مرتبطًا بقسم عادي"""
        planning_qism = PlanningQismFactory()
        template = FormTemplateFactory.build(qism=planning_qism, version=1)
        with pytest.raises(ValidationError) as exc:
            template.full_clean()
        assert "يجب أن تكون الاستمارة مرتبطة بقسم عادي فقط" in str(exc.value)

    def test_form_template_valid_for_regular_qism(self):
        """قالب الاستمارة صالح لقسم عادي"""
        regular_qism = QismFactory()
        template = FormTemplateFactory.build(qism=regular_qism, version=1)
        template.full_clean()  # يجب ألا يرفع استثناء

    def test_form_template_str(self):
        """__str__ يرجع اسم القسم ورقم الإصدار"""
        qism = QismFactory(name="قسم الحسابات")
        template = FormTemplateFactory(qism=qism, version=3)
        assert str(template) == "قسم الحسابات - الإصدار 3"

    def test_form_template_item_str(self):
        """__str__ لبند الاستمارة يرجع اسم القالب والمؤشر"""
        template = FormTemplateFactory()
        item = FormTemplateItemFactory(form_template=template)
        result = str(item)
        assert template.qism.name in result
        assert item.indicator.name in result

    def test_form_template_unique_qism_version(self):
        """لا يمكن إنشاء إصدارين بنفس الرقم لنفس القسم"""
        qism = QismFactory()
        FormTemplateFactory(qism=qism, version=1)
        with pytest.raises(Exception):
            FormTemplateFactory(qism=qism, version=1)

    def test_form_template_item_unique_per_template_indicator(self):
        """لا يمكن إضافة نفس المؤشر مرتين في نفس القالب"""
        template = FormTemplateFactory()
        item = FormTemplateItemFactory(form_template=template)
        with pytest.raises(Exception):
            FormTemplateItemFactory(
                form_template=template,
                indicator=item.indicator,
            )
