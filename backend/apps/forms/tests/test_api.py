"""
اختبارات واجهات API لقوالب الاستمارات.
"""
import pytest
from django.urls import reverse

from apps.forms.models import FormTemplate
from apps.forms.tests.factories import FormTemplateFactory, FormTemplateItemFactory
from apps.indicators.tests.factories import IndicatorFactory
from apps.organization.tests.factories import QismFactory, MudiriyaFactory
from apps.accounts.tests.factories import (
    StatisticsAdminFactory,
    PlanningSectionUserFactory,
    SectionManagerFactory,
)


@pytest.mark.django_db
class TestFormTemplateListAPI:
    """اختبارات عرض قائمة قوالب الاستمارات"""

    def test_list_templates(self, api_client):
        """اختبار عرض قائمة قوالب الاستمارات للمستخدم المصادق عليه"""
        admin = StatisticsAdminFactory()
        FormTemplateFactory.create_batch(3)

        api_client.force_authenticate(user=admin)
        url = reverse('form-template-list')
        response = api_client.get(url)

        assert response.status_code == 200
        assert len(response.data['results']) == 3

    def test_unauthenticated_returns_401(self, api_client):
        """اختبار أن الطلبات غير المصادق عليها ترجع 401"""
        url = reverse('form-template-list')
        response = api_client.get(url)

        assert response.status_code in (401, 403)


@pytest.mark.django_db
class TestFormTemplateSubmitAPI:
    """اختبارات تقديم القالب للاعتماد عبر API"""

    def test_submit_template_for_approval_endpoint(self, api_client):
        """اختبار تقديم قالب للاعتماد عبر نقطة النهاية"""
        mudiriya = MudiriyaFactory()
        qism = QismFactory(parent=mudiriya)
        planner = PlanningSectionUserFactory(unit__parent=mudiriya)
        template = FormTemplateFactory(
            qism=qism, status='draft', created_by=planner,
        )
        FormTemplateItemFactory(form_template=template)

        api_client.force_authenticate(user=planner)
        url = reverse('form-template-submit', kwargs={'pk': template.pk})
        response = api_client.post(url)

        assert response.status_code == 200
        assert response.data['status'] == FormTemplate.Status.PENDING_APPROVAL

    def test_submit_by_non_planner_fails(self, api_client):
        """اختبار أن غير قسم التخطيط لا يمكنه تقديم القالب"""
        admin = StatisticsAdminFactory()
        template = FormTemplateFactory(status='draft')
        FormTemplateItemFactory(form_template=template)

        api_client.force_authenticate(user=admin)
        url = reverse('form-template-submit', kwargs={'pk': template.pk})
        response = api_client.post(url)

        assert response.status_code == 403


@pytest.mark.django_db
class TestFormTemplateApproveAPI:
    """اختبارات اعتماد القالب عبر API"""

    def test_approve_template_admin_only(self, api_client):
        """اختبار اعتماد القالب من قبل مدير الإحصاء فقط"""
        admin = StatisticsAdminFactory()
        template = FormTemplateFactory(status='pending_approval')
        FormTemplateItemFactory(form_template=template)

        api_client.force_authenticate(user=admin)
        url = reverse('form-template-approve', kwargs={'pk': template.pk})
        data = {
            'effective_from_week': 5,
            'effective_from_year': 2025,
        }
        response = api_client.post(url, data=data, format='json')

        assert response.status_code == 200
        assert response.data['status'] == FormTemplate.Status.APPROVED

    def test_non_admin_cannot_approve(self, api_client):
        """اختبار أن غير مدير الإحصاء لا يمكنه اعتماد القالب"""
        planner = PlanningSectionUserFactory()
        template = FormTemplateFactory(status='pending_approval')
        FormTemplateItemFactory(form_template=template)

        api_client.force_authenticate(user=planner)
        url = reverse('form-template-approve', kwargs={'pk': template.pk})
        data = {
            'effective_from_week': 5,
            'effective_from_year': 2025,
        }
        response = api_client.post(url, data=data, format='json')

        assert response.status_code == 403


@pytest.mark.django_db
class TestFormTemplateRejectAPI:
    """اختبارات رفض القالب عبر API"""

    def test_reject_template_admin_only(self, api_client):
        """اختبار رفض القالب من قبل مدير الإحصاء فقط"""
        admin = StatisticsAdminFactory()
        template = FormTemplateFactory(status='pending_approval')
        FormTemplateItemFactory(form_template=template)

        api_client.force_authenticate(user=admin)
        url = reverse('form-template-reject', kwargs={'pk': template.pk})
        data = {'rejection_reason': 'البيانات غير مكتملة'}
        response = api_client.post(url, data=data, format='json')

        assert response.status_code == 200
        assert response.data['status'] == FormTemplate.Status.REJECTED
        assert response.data['rejection_reason'] == 'البيانات غير مكتملة'

    def test_non_admin_cannot_reject(self, api_client):
        """اختبار أن غير مدير الإحصاء لا يمكنه رفض القالب"""
        planner = PlanningSectionUserFactory()
        template = FormTemplateFactory(status='pending_approval')
        FormTemplateItemFactory(form_template=template)

        api_client.force_authenticate(user=planner)
        url = reverse('form-template-reject', kwargs={'pk': template.pk})
        data = {'rejection_reason': 'سبب ما'}
        response = api_client.post(url, data=data, format='json')

        assert response.status_code == 403


@pytest.mark.django_db
class TestFormTemplateActiveAPI:
    """اختبارات الحصول على القالب النشط عبر API"""

    def test_active_template_endpoint(self, api_client):
        """اختبار الحصول على القالب النشط لقسم محدد"""
        admin = StatisticsAdminFactory()
        qism = QismFactory()
        template = FormTemplateFactory(
            qism=qism, status='approved', version=1,
            effective_from_week=1, effective_from_year=2025,
        )
        FormTemplateItemFactory(form_template=template)

        api_client.force_authenticate(user=admin)
        url = reverse('form-template-active')
        response = api_client.get(url, {'qism_id': qism.pk})

        assert response.status_code == 200
        assert response.data['id'] == template.pk

    def test_active_template_missing_qism_id(self, api_client):
        """اختبار فشل الطلب بدون تحديد معرف القسم"""
        admin = StatisticsAdminFactory()

        api_client.force_authenticate(user=admin)
        url = reverse('form-template-active')
        response = api_client.get(url)

        assert response.status_code == 400
