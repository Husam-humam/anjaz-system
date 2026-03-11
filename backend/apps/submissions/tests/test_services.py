"""
اختبارات طبقة الخدمات لتطبيق المنجزات.
تغطي: SubmissionService، QismExtensionService، AggregationService، QualitativeService.
"""
import pytest
from datetime import datetime
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.utils import timezone
from freezegun import freeze_time

from apps.accounts.tests.factories import (
    PlanningSectionUserFactory,
    SectionManagerFactory,
    StatisticsAdminFactory,
)
from apps.forms.tests.factories import FormTemplateFactory, FormTemplateItemFactory
from apps.indicators.tests.factories import IndicatorFactory
from apps.organization.tests.factories import QismFactory

from ..services import (
    AggregationService,
    QismExtensionService,
    QualitativeService,
    SubmissionService,
)
from .factories import (
    QismExtensionFactory,
    SubmissionAnswerFactory,
    WeeklyPeriodFactory,
    WeeklySubmissionFactory,
)


@pytest.mark.django_db
class TestSubmissionServiceSubmit:
    """اختبارات خدمة إرسال المنجز"""

    @freeze_time("2025-04-14 10:00:00")
    @patch("apps.submissions.services._notify_submission_received")
    def test_submit_transitions_to_submitted(self, mock_notify):
        """إرسال المنجز ينقل الحالة من مسودة إلى مُرسل"""
        qism = QismFactory()
        indicator = IndicatorFactory(unit_type="number", accumulation_type="sum")
        template = FormTemplateFactory(qism=qism, status="approved")
        item = FormTemplateItemFactory(
            form_template=template, indicator=indicator, is_mandatory=True
        )

        period = WeeklyPeriodFactory(
            status="open",
            deadline=timezone.make_aware(datetime(2025, 4, 15, 23, 59, 0)),
        )
        submission = WeeklySubmissionFactory(
            qism=qism,
            weekly_period=period,
            form_template=template,
            status="draft",
        )
        # تعبئة الحقل الإلزامي
        SubmissionAnswerFactory(
            submission=submission,
            form_item=item,
            numeric_value=42,
        )

        user = SectionManagerFactory(unit=qism)
        result = SubmissionService.submit(submission, user)

        assert result.status == "submitted"
        assert result.submitted_at is not None
        mock_notify.assert_called_once()

    @freeze_time("2025-04-16 10:00:00")
    def test_submit_fails_if_not_editable(self):
        """إرسال المنجز يفشل بعد انتهاء الموعد النهائي"""
        qism = QismFactory()
        template = FormTemplateFactory(qism=qism, status="approved")

        period = WeeklyPeriodFactory(
            status="open",
            deadline=timezone.make_aware(datetime(2025, 4, 14, 23, 59, 0)),
        )
        submission = WeeklySubmissionFactory(
            qism=qism,
            weekly_period=period,
            form_template=template,
            status="draft",
        )

        user = SectionManagerFactory(unit=qism)
        with pytest.raises(ValidationError) as exc:
            SubmissionService.submit(submission, user)
        assert "لا يمكن إرسال هذا المنجز" in str(exc.value)

    @freeze_time("2025-04-14 10:00:00")
    def test_submit_fails_from_approved_status(self):
        """لا يمكن إرسال منجز في حالة 'معتمد'"""
        qism = QismFactory()
        template = FormTemplateFactory(qism=qism, status="approved")

        period = WeeklyPeriodFactory(
            status="open",
            deadline=timezone.make_aware(datetime(2025, 4, 15, 23, 59, 0)),
        )
        submission = WeeklySubmissionFactory(
            qism=qism,
            weekly_period=period,
            form_template=template,
            status="approved",
        )
        user = SectionManagerFactory(unit=qism)
        with pytest.raises(ValidationError) as exc:
            SubmissionService.submit(submission, user)
        assert "الحالة الحالية غير مسموح بها" in str(exc.value)


@pytest.mark.django_db
class TestSubmissionServiceApprove:
    """اختبارات خدمة اعتماد المنجز"""

    @patch("apps.submissions.services._notify_submission_approved")
    @patch("apps.submissions.services._notify_qualitative_pending")
    def test_approve_transitions_to_approved(self, mock_qual, mock_notify):
        """اعتماد المنجز ينقل الحالة من مُرسل إلى معتمد"""
        submission = WeeklySubmissionFactory(status="submitted")
        planner = PlanningSectionUserFactory()

        result = SubmissionService.approve(submission, planner)

        assert result.status == "approved"
        assert result.planning_approved_by == planner
        assert result.planning_approved_at is not None
        mock_notify.assert_called_once()

    @patch("apps.submissions.services._notify_submission_approved")
    @patch("apps.submissions.services._notify_qualitative_pending")
    def test_approve_moves_qualitative_to_pending_statistics(
        self, mock_qual, mock_notify
    ):
        """اعتماد المنجز ينقل المنجزات النوعية إلى بانتظار اعتماد الإحصاء"""
        qism = QismFactory()
        indicator = IndicatorFactory(unit_type="number", accumulation_type="sum")
        template = FormTemplateFactory(qism=qism, status="approved")
        item = FormTemplateItemFactory(
            form_template=template, indicator=indicator
        )

        submission = WeeklySubmissionFactory(
            qism=qism,
            form_template=template,
            status="submitted",
        )

        answer = SubmissionAnswerFactory(
            submission=submission,
            form_item=item,
            numeric_value=10,
            is_qualitative=True,
            qualitative_details="إنجاز نوعي مهم",
            qualitative_status="pending_planning",
        )

        planner = PlanningSectionUserFactory()
        SubmissionService.approve(submission, planner)

        answer.refresh_from_db()
        assert answer.qualitative_status == "pending_statistics"
        mock_qual.assert_called_once()

    def test_approve_fails_if_not_submitted(self):
        """لا يمكن اعتماد منجز ليس في حالة 'مُرسل'"""
        submission = WeeklySubmissionFactory(status="draft")
        planner = PlanningSectionUserFactory()

        with pytest.raises(ValidationError) as exc:
            SubmissionService.approve(submission, planner)
        assert 'يجب أن يكون بحالة "مُرسل"' in str(exc.value)


@pytest.mark.django_db
class TestQismExtensionService:
    """اختبارات خدمة تمديد المواعيد"""

    @patch("apps.submissions.services._notify_extension_granted")
    def test_grant_extension(self, mock_notify):
        """منح تمديد ناجح يُنشئ سجل التمديد ويحدّث حالة المنجز"""
        qism = QismFactory()
        admin = StatisticsAdminFactory()
        period = WeeklyPeriodFactory(
            deadline=timezone.make_aware(datetime(2025, 4, 14, 23, 59, 0)),
        )
        template = FormTemplateFactory(qism=qism, status="approved")
        submission = WeeklySubmissionFactory(
            qism=qism,
            weekly_period=period,
            form_template=template,
            status="draft",
        )

        new_deadline = timezone.make_aware(datetime(2025, 4, 20, 23, 59, 0))
        data = {
            "qism": qism,
            "weekly_period": period,
            "new_deadline": new_deadline,
            "reason": "ظروف طارئة",
        }

        extension = QismExtensionService.grant_extension(data, granted_by=admin)

        assert extension.qism == qism
        assert extension.new_deadline == new_deadline
        submission.refresh_from_db()
        assert submission.status == "extended"
        mock_notify.assert_called_once()

    def test_grant_extension_fails_if_before_deadline(self):
        """منح تمديد يفشل إذا كان الموعد الجديد قبل الأصلي"""
        qism = QismFactory()
        admin = StatisticsAdminFactory()
        period = WeeklyPeriodFactory(
            deadline=timezone.make_aware(datetime(2025, 4, 14, 23, 59, 0)),
        )

        earlier_deadline = timezone.make_aware(datetime(2025, 4, 13, 23, 59, 0))
        data = {
            "qism": qism,
            "weekly_period": period,
            "new_deadline": earlier_deadline,
            "reason": "محاولة تمديد خاطئة",
        }

        with pytest.raises(ValidationError) as exc:
            QismExtensionService.grant_extension(data, granted_by=admin)
        assert "الموعد الجديد يجب أن يكون بعد الموعد الأصلي" in str(exc.value)

    @patch("apps.submissions.services._notify_extension_granted")
    def test_grant_extension_fails_if_duplicate(self, mock_notify):
        """منح تمديد يفشل إذا وُجد تمديد مسبق"""
        qism = QismFactory()
        admin = StatisticsAdminFactory()
        period = WeeklyPeriodFactory(
            deadline=timezone.make_aware(datetime(2025, 4, 14, 23, 59, 0)),
        )

        new_deadline = timezone.make_aware(datetime(2025, 4, 20, 23, 59, 0))

        # التمديد الأول
        QismExtensionFactory(
            qism=qism,
            weekly_period=period,
            new_deadline=new_deadline,
        )

        data = {
            "qism": qism,
            "weekly_period": period,
            "new_deadline": timezone.make_aware(datetime(2025, 4, 25, 23, 59, 0)),
            "reason": "محاولة تمديد ثانية",
        }

        with pytest.raises(ValidationError) as exc:
            QismExtensionService.grant_extension(data, granted_by=admin)
        assert "يوجد تمديد مسبق" in str(exc.value)


@pytest.mark.django_db
class TestAggregationService:
    """اختبارات خدمة تجميع البيانات"""

    def test_aggregate_sum(self):
        """التجميع بطريقة المجموع"""
        values = [10, 20, 30]
        result = AggregationService.aggregate(values, "sum")
        assert result == 60

    def test_aggregate_average(self):
        """التجميع بطريقة المتوسط"""
        values = [10, 20, 30]
        result = AggregationService.aggregate(values, "average")
        assert result == 20.0

    def test_aggregate_last_value(self):
        """التجميع بطريقة آخر قيمة"""
        values = [10, 20, 30]
        result = AggregationService.aggregate(values, "last_value")
        assert result == 30

    def test_aggregate_empty_returns_none(self):
        """التجميع بدون قيم يرجع None"""
        result = AggregationService.aggregate([], "sum")
        assert result is None

    def test_aggregate_with_answer_objects(self):
        """التجميع باستخدام كائنات SubmissionAnswer"""
        indicator = IndicatorFactory(unit_type="number", accumulation_type="sum")
        template_item = FormTemplateItemFactory(indicator=indicator)
        submission = WeeklySubmissionFactory(
            form_template=template_item.form_template
        )

        a1 = SubmissionAnswerFactory(
            submission=submission, form_item=template_item, numeric_value=15
        )
        # كائن إجابة آخر بمؤشر مختلف لتجنب unique_together
        indicator2 = IndicatorFactory(unit_type="number", accumulation_type="sum")
        item2 = FormTemplateItemFactory(
            form_template=template_item.form_template, indicator=indicator2
        )
        a2 = SubmissionAnswerFactory(
            submission=submission, form_item=item2, numeric_value=25
        )

        result = AggregationService.aggregate([a1, a2], "sum")
        assert result == 40


@pytest.mark.django_db
class TestQualitativeService:
    """اختبارات خدمة المنجزات النوعية"""

    @patch("apps.submissions.services._notify_qualitative_approved")
    def test_qualitative_approve(self, mock_notify):
        """اعتماد المنجز النوعي ينقل الحالة إلى معتمد"""
        indicator = IndicatorFactory(unit_type="number", accumulation_type="sum")
        item = FormTemplateItemFactory(indicator=indicator)
        submission = WeeklySubmissionFactory(form_template=item.form_template)

        answer = SubmissionAnswerFactory(
            submission=submission,
            form_item=item,
            numeric_value=10,
            is_qualitative=True,
            qualitative_details="إنجاز نوعي",
            qualitative_status="pending_statistics",
        )

        admin = StatisticsAdminFactory()
        result = QualitativeService.approve_qualitative(answer, admin)

        assert result.qualitative_status == "approved"
        assert result.qualitative_approved_by == admin
        assert result.qualitative_approved_at is not None
        mock_notify.assert_called_once()

    @patch("apps.submissions.services._notify_qualitative_rejected")
    def test_qualitative_reject(self, mock_notify):
        """رفض المنجز النوعي ينقل الحالة إلى مرفوض"""
        indicator = IndicatorFactory(unit_type="number", accumulation_type="sum")
        item = FormTemplateItemFactory(indicator=indicator)
        submission = WeeklySubmissionFactory(form_template=item.form_template)

        answer = SubmissionAnswerFactory(
            submission=submission,
            form_item=item,
            numeric_value=10,
            is_qualitative=True,
            qualitative_details="إنجاز نوعي",
            qualitative_status="pending_statistics",
        )

        admin = StatisticsAdminFactory()
        reason = "البيانات غير مكتملة"
        result = QualitativeService.reject_qualitative(answer, admin, reason)

        assert result.qualitative_status == "rejected"
        assert result.rejection_reason == reason
        assert result.qualitative_approved_by == admin
        mock_notify.assert_called_once()

    def test_qualitative_reject_requires_reason(self):
        """رفض المنجز النوعي يتطلب تحديد السبب"""
        indicator = IndicatorFactory(unit_type="number", accumulation_type="sum")
        item = FormTemplateItemFactory(indicator=indicator)
        submission = WeeklySubmissionFactory(form_template=item.form_template)

        answer = SubmissionAnswerFactory(
            submission=submission,
            form_item=item,
            numeric_value=10,
            is_qualitative=True,
            qualitative_details="إنجاز نوعي",
            qualitative_status="pending_statistics",
        )

        admin = StatisticsAdminFactory()
        with pytest.raises(ValidationError) as exc:
            QualitativeService.reject_qualitative(answer, admin, "")
        assert "يجب تحديد سبب الرفض" in str(exc.value)

    def test_qualitative_approve_fails_if_wrong_status(self):
        """اعتماد المنجز النوعي يفشل إذا لم يكن في حالة بانتظار اعتماد الإحصاء"""
        indicator = IndicatorFactory(unit_type="number", accumulation_type="sum")
        item = FormTemplateItemFactory(indicator=indicator)
        submission = WeeklySubmissionFactory(form_template=item.form_template)

        answer = SubmissionAnswerFactory(
            submission=submission,
            form_item=item,
            numeric_value=10,
            is_qualitative=True,
            qualitative_details="إنجاز نوعي",
            qualitative_status="pending_planning",
        )

        admin = StatisticsAdminFactory()
        with pytest.raises(ValidationError) as exc:
            QualitativeService.approve_qualitative(answer, admin)
        assert "بانتظار اعتماد الإحصاء" in str(exc.value)
