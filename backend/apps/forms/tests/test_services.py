"""
اختبارات خدمات قوالب الاستمارات — FormTemplateService.
"""
import pytest
from django.core.exceptions import ValidationError

from apps.forms.models import FormTemplate
from apps.forms.services import FormTemplateService
from apps.forms.tests.factories import FormTemplateFactory, FormTemplateItemFactory
from apps.indicators.tests.factories import IndicatorFactory
from apps.organization.tests.factories import QismFactory, MudiriyaFactory
from apps.accounts.tests.factories import (
    PlanningSectionUserFactory,
    StatisticsAdminFactory,
)


@pytest.mark.django_db
class TestFormTemplateServiceCreate:
    """اختبارات إنشاء قوالب الاستمارات"""

    def test_create_template_auto_version(self):
        """اختبار أن رقم الإصدار يحسب تلقائياً"""
        mudiriya = MudiriyaFactory()
        qism = QismFactory(parent=mudiriya)
        # المخطط يجب أن ينتمي لنفس المديرية
        planner = PlanningSectionUserFactory(
            unit__parent=mudiriya,
        )
        indicator = IndicatorFactory()

        data = {'qism': qism, 'notes': ''}
        items_data = [
            {'indicator': indicator, 'is_mandatory': True, 'display_order': 0}
        ]

        template1 = FormTemplateService.create_template(data, items_data, planner)
        assert template1.version == 1

        # إنشاء قالب ثانٍ لنفس القسم — الإصدار يجب أن يكون 2
        indicator2 = IndicatorFactory()
        items_data2 = [
            {'indicator': indicator2, 'is_mandatory': False, 'display_order': 0}
        ]
        template2 = FormTemplateService.create_template(
            {'qism': qism, 'notes': ''}, items_data2, planner
        )
        assert template2.version == 2

    def test_create_template_must_have_items(self):
        """اختبار فشل إنشاء قالب بدون بنود"""
        mudiriya = MudiriyaFactory()
        qism = QismFactory(parent=mudiriya)
        planner = PlanningSectionUserFactory(unit__parent=mudiriya)
        data = {'qism': qism, 'notes': ''}

        with pytest.raises(ValidationError) as exc_info:
            FormTemplateService.create_template(data, [], planner)

        assert 'items' in exc_info.value.message_dict

    def test_create_template_non_regular_qism_fails(self):
        """اختبار فشل إنشاء قالب لقسم غير عادي"""
        mudiriya = MudiriyaFactory()
        # قسم تخطيط بدلاً من عادي
        planning_qism = QismFactory(parent=mudiriya, qism_role='planning')
        planner = PlanningSectionUserFactory(unit__parent=mudiriya)
        indicator = IndicatorFactory()
        data = {'qism': planning_qism, 'notes': ''}
        items_data = [
            {'indicator': indicator, 'is_mandatory': True, 'display_order': 0}
        ]

        with pytest.raises(ValidationError) as exc_info:
            FormTemplateService.create_template(data, items_data, planner)

        assert 'qism' in exc_info.value.message_dict


@pytest.mark.django_db
class TestFormTemplateServiceUpdate:
    """اختبارات تحديث قوالب الاستمارات"""

    def test_update_template_only_in_draft(self):
        """اختبار أن التحديث مسموح فقط في حالة المسودة"""
        template = FormTemplateFactory(status='pending_approval')
        FormTemplateItemFactory(form_template=template)

        with pytest.raises(ValidationError) as exc_info:
            FormTemplateService.update_template(
                template, {'notes': 'تحديث'}, None
            )

        assert 'المسودة' in str(exc_info.value)

    def test_update_template_in_draft_succeeds(self):
        """اختبار نجاح التحديث في حالة المسودة"""
        template = FormTemplateFactory(status='draft')
        FormTemplateItemFactory(form_template=template)

        updated = FormTemplateService.update_template(
            template, {'notes': 'ملاحظة جديدة'}, None
        )

        assert updated.notes == 'ملاحظة جديدة'


@pytest.mark.django_db
class TestFormTemplateServiceSubmit:
    """اختبارات تقديم القالب للاعتماد"""

    def test_submit_for_approval(self):
        """اختبار تقديم قالب مسودة للاعتماد بنجاح"""
        template = FormTemplateFactory(status='draft')
        FormTemplateItemFactory(form_template=template)

        result = FormTemplateService.submit_for_approval(template)

        assert result.status == FormTemplate.Status.PENDING_APPROVAL

    def test_submit_empty_template_fails(self):
        """اختبار فشل تقديم قالب فارغ (بدون بنود) للاعتماد"""
        template = FormTemplateFactory(status='draft')
        # بدون إنشاء أي بنود

        with pytest.raises(ValidationError) as exc_info:
            FormTemplateService.submit_for_approval(template)

        assert 'فارغة' in str(exc_info.value)

    def test_submit_non_draft_fails(self):
        """اختبار فشل تقديم قالب ليس في حالة المسودة"""
        template = FormTemplateFactory(status='approved')
        FormTemplateItemFactory(form_template=template)

        with pytest.raises(ValidationError):
            FormTemplateService.submit_for_approval(template)


@pytest.mark.django_db
class TestFormTemplateServiceApprove:
    """اختبارات اعتماد القالب"""

    def test_approve_supersedes_old_version(self):
        """اختبار أن اعتماد قالب جديد يستبدل القالب المعتمد السابق"""
        qism = QismFactory()
        admin = StatisticsAdminFactory()

        # إنشاء قالب معتمد سابقاً
        old_template = FormTemplateFactory(
            qism=qism, status='approved', version=1,
            effective_from_week=1, effective_from_year=2025,
        )
        FormTemplateItemFactory(form_template=old_template)

        # إنشاء قالب جديد بانتظار الاعتماد
        new_template = FormTemplateFactory(
            qism=qism, status='pending_approval', version=2,
        )
        FormTemplateItemFactory(form_template=new_template)

        result = FormTemplateService.approve_template(
            new_template,
            approved_by=admin,
            effective_from_week=5,
            effective_from_year=2025,
        )

        assert result.status == FormTemplate.Status.APPROVED
        assert result.effective_from_week == 5
        assert result.effective_from_year == 2025
        assert result.approved_by == admin
        assert result.approved_at is not None

        # التحقق من أن القالب السابق أصبح مُستبدَلاً
        old_template.refresh_from_db()
        assert old_template.status == FormTemplate.Status.SUPERSEDED

    def test_approve_requires_pending_status(self):
        """اختبار فشل الاعتماد إذا لم يكن القالب بانتظار الاعتماد"""
        template = FormTemplateFactory(status='draft')
        FormTemplateItemFactory(form_template=template)
        admin = StatisticsAdminFactory()

        with pytest.raises(ValidationError) as exc_info:
            FormTemplateService.approve_template(
                template,
                approved_by=admin,
                effective_from_week=1,
                effective_from_year=2025,
            )

        assert 'بانتظار الاعتماد' in str(exc_info.value)


@pytest.mark.django_db
class TestFormTemplateServiceReject:
    """اختبارات رفض القالب"""

    def test_reject_template_requires_reason(self):
        """اختبار أن رفض القالب يتطلب تحديد سبب الرفض"""
        template = FormTemplateFactory(status='pending_approval')
        FormTemplateItemFactory(form_template=template)
        admin = StatisticsAdminFactory()

        with pytest.raises(ValidationError) as exc_info:
            FormTemplateService.reject_template(
                template, rejected_by=admin, reason=''
            )

        assert 'rejection_reason' in exc_info.value.message_dict

    def test_reject_template_succeeds_with_reason(self):
        """اختبار نجاح رفض القالب مع تحديد سبب"""
        template = FormTemplateFactory(status='pending_approval')
        FormTemplateItemFactory(form_template=template)
        admin = StatisticsAdminFactory()

        result = FormTemplateService.reject_template(
            template, rejected_by=admin, reason='بيانات ناقصة'
        )

        assert result.status == FormTemplate.Status.REJECTED
        assert result.rejected_by == admin
        assert result.rejection_reason == 'بيانات ناقصة'

    def test_reject_non_pending_fails(self):
        """اختبار فشل رفض قالب ليس بانتظار الاعتماد"""
        template = FormTemplateFactory(status='draft')
        admin = StatisticsAdminFactory()

        with pytest.raises(ValidationError):
            FormTemplateService.reject_template(
                template, rejected_by=admin, reason='سبب ما'
            )


@pytest.mark.django_db
class TestFormTemplateServiceGetActive:
    """اختبارات الحصول على القالب النشط"""

    def test_get_active_template(self):
        """اختبار الحصول على القالب النشط لقسم معين"""
        qism = QismFactory()

        template = FormTemplateFactory(
            qism=qism,
            status='approved',
            version=1,
            effective_from_week=1,
            effective_from_year=2025,
        )
        FormTemplateItemFactory(form_template=template)

        result = FormTemplateService.get_active_template(
            qism_id=qism.pk, year=2025, week_number=10,
        )

        assert result.pk == template.pk

    def test_get_active_template_no_template_raises(self):
        """اختبار إثارة خطأ عند عدم وجود قالب نشط"""
        qism = QismFactory()

        with pytest.raises(ValidationError) as exc_info:
            FormTemplateService.get_active_template(qism_id=qism.pk)

        assert 'لا يوجد قالب استمارة نشط' in str(exc_info.value)

    def test_get_active_template_returns_latest(self):
        """اختبار إرجاع أحدث قالب نشط عند وجود أكثر من واحد"""
        qism = QismFactory()

        FormTemplateFactory(
            qism=qism, status='approved', version=1,
            effective_from_week=1, effective_from_year=2025,
        )
        newer = FormTemplateFactory(
            qism=qism, status='approved', version=2,
            effective_from_week=10, effective_from_year=2025,
        )

        result = FormTemplateService.get_active_template(
            qism_id=qism.pk, year=2025, week_number=15,
        )

        assert result.pk == newer.pk
