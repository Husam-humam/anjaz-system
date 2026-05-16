"""
اختبارات خدمات قوالب الاستمارات — FormTemplateService.
"""
import pytest
from django.core.exceptions import ValidationError

from apps.forms.models import FormTemplate
from apps.forms.services import FormTemplateService
from apps.forms.tests.factories import FormTemplateFactory, FormTemplateItemFactory
from apps.indicators.tests.factories import IndicatorFactory
from apps.organization.models import PlanningAssignment, SupervisedUnit
from apps.organization.tests.factories import QismFactory, MudiriyaFactory
from apps.accounts.tests.factories import (
    PlanningSectionUserFactory,
    StatisticsAdminFactory,
)


def _supervise(planning_unit, *qisms):
    """Helper: يُنشئ PlanningAssignment + SupervisedUnit للأقسام."""
    assignment, _ = PlanningAssignment.objects.get_or_create(planning_unit=planning_unit)
    for q in qisms:
        SupervisedUnit.objects.get_or_create(assignment=assignment, unit=q)
    return assignment


@pytest.mark.django_db
class TestFormTemplateServiceCreate:
    """اختبارات إنشاء قوالب الاستمارات"""

    def test_create_template_auto_version(self):
        """اختبار أن رقم الإصدار يحسب تلقائياً"""
        mudiriya = MudiriyaFactory()
        qism = QismFactory(parent=mudiriya)
        # المخطط يجب أن ينتمي لنفس المديرية + يكون مُسنَداً لإدارة هذا القسم
        planner = PlanningSectionUserFactory(unit__parent=mudiriya)
        _supervise(planner.unit, qism)
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
        _supervise(planner.unit, qism)
        data = {'qism': qism, 'notes': ''}

        with pytest.raises(ValidationError) as exc_info:
            FormTemplateService.create_template(data, [], planner)

        assert 'items' in exc_info.value.message_dict

    def test_create_template_for_unsupervised_qism_fails(self):
        """قالب يتطلّب قسماً مُسنَداً للتقديم (له SupervisedUnit)."""
        mudiriya = MudiriyaFactory()
        # قسم بدون SupervisedUnit (مهما كان نوعه)
        unassigned_qism = QismFactory(parent=mudiriya)
        planner = PlanningSectionUserFactory(unit__parent=mudiriya)
        indicator = IndicatorFactory()
        data = {'qism': unassigned_qism, 'notes': ''}
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

    def test_approve_supersedes_same_effective_week(self):
        """
        اعتماد قالب جديد بنفس أسبوع تفعيل قالب معتمد سابق يُستبدِل القديم.
        (سيناريو «نفس الأسبوع» — تحديث الخطة قبل أن تسري).
        """
        qism = QismFactory()
        admin = StatisticsAdminFactory()

        # قالب مُجدوَل للأسبوع 5 من سنة 2099 (مستقبلي)
        old_template = FormTemplateFactory(
            qism=qism, status='approved', version=1,
            effective_from_week=5, effective_from_year=2099,
        )
        FormTemplateItemFactory(form_template=old_template)

        new_template = FormTemplateFactory(
            qism=qism, status='pending_approval', version=2,
        )
        FormTemplateItemFactory(form_template=new_template)

        result = FormTemplateService.approve_template(
            new_template,
            approved_by=admin,
            effective_from_week=5,
            effective_from_year=2099,
        )

        assert result.status == FormTemplate.Status.APPROVED
        assert result.effective_from_week == 5
        assert result.effective_from_year == 2099

        # القالب السابق (نفس التاريخ) أصبح مُستبدَلاً
        old_template.refresh_from_db()
        assert old_template.status == FormTemplate.Status.SUPERSEDED

    def test_approve_future_template_keeps_currently_active(self):
        """
        اعتماد قالب لتاريخ مستقبلي يجب أن لا يُستبدِل القالب الفعّال حالياً.
        الهدف: تجنّب ثغرة تغطية الأسابيع بين الآن وتاريخ التفعيل الجديد.
        """
        qism = QismFactory()
        admin = StatisticsAdminFactory()

        # قالب حالياً فعّال (effective_from في الماضي)
        current_active = FormTemplateFactory(
            qism=qism, status='approved', version=1,
            effective_from_week=1, effective_from_year=2025,
        )
        FormTemplateItemFactory(form_template=current_active)

        new_template = FormTemplateFactory(
            qism=qism, status='pending_approval', version=2,
        )
        FormTemplateItemFactory(form_template=new_template)

        FormTemplateService.approve_template(
            new_template,
            approved_by=admin,
            effective_from_week=10,
            effective_from_year=2099,
        )

        # القالب الفعّال يبقى APPROVED ليغطّي الأسابيع حتى يحلّ التاريخ الجديد
        current_active.refresh_from_db()
        assert current_active.status == FormTemplate.Status.APPROVED

    def test_approve_rejects_retroactive_effective_date(self):
        """اعتماد قالب بتاريخ تفعيل في الماضي يجب أن يُرفَض"""
        template = FormTemplateFactory(status='pending_approval')
        FormTemplateItemFactory(form_template=template)
        admin = StatisticsAdminFactory()

        with pytest.raises(ValidationError) as exc_info:
            FormTemplateService.approve_template(
                template,
                approved_by=admin,
                effective_from_week=1,
                effective_from_year=2020,
            )

        assert 'ماضٍ' in str(exc_info.value)

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
                effective_from_year=2099,
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
