"""
اختبارات SubmissionAdminService — تدفّق مراجعة الإحصاء (الطبقة الثالثة).
يغطّي:
- اعتماد بسيط + قفل ضد المراجعة الثانية
- تعديل إجابات مع تسجيل audit + سبب إلزامي
- إرجاع للتخطيط مع سبب إلزامي + انتقال الحالة
- إعادة تصفير حقول المراجعة عند إعادة اعتماد التخطيط
- is_editable دائماً True لحالة returned_by_admin
"""
from datetime import datetime
from unittest.mock import patch

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
from freezegun import freeze_time

from apps.accounts.tests.factories import (
    PlanningSectionUserFactory,
    SectionManagerFactory,
    StatisticsAdminFactory,
)
from apps.audit.models import AuditLog
from apps.forms.tests.factories import FormTemplateFactory, FormTemplateItemFactory
from apps.indicators.tests.factories import IndicatorFactory
from apps.organization.tests.factories import QismFactory

from ..models import SubmissionAnswer, WeeklySubmission
from ..services import SubmissionAdminService, SubmissionService
from .factories import (
    SubmissionAnswerFactory,
    WeeklyPeriodFactory,
    WeeklySubmissionFactory,
)


@pytest.fixture
def approved_submission(db):
    """منجز معتمد من التخطيط وجاهز لمراجعة الإحصاء."""
    qism = QismFactory()
    indicator = IndicatorFactory(unit_type='number', accumulation_type='sum')
    template = FormTemplateFactory(qism=qism, status='approved')
    item = FormTemplateItemFactory(
        form_template=template, indicator=indicator, is_mandatory=True
    )
    period = WeeklyPeriodFactory(status='open')
    submission = WeeklySubmissionFactory(
        qism=qism,
        weekly_period=period,
        form_template=template,
        status='approved',
    )
    answer = SubmissionAnswerFactory(
        submission=submission,
        form_item=item,
        numeric_value=100,
    )
    return submission, answer


@pytest.mark.django_db
class TestSubmissionAdminServiceApprove:

    def test_admin_approve_marks_as_reviewed(self, approved_submission):
        submission, _ = approved_submission
        admin = StatisticsAdminFactory()

        result = SubmissionAdminService.approve(submission, admin)

        assert result.admin_reviewed_at is not None
        assert result.admin_reviewed_by == admin
        assert result.admin_review_action == 'approved'
        # الحالة تبقى approved — الإحصائيّات تستمر في احتسابه
        assert result.status == WeeklySubmission.Status.APPROVED

    def test_admin_approve_writes_audit_log(self, approved_submission):
        submission, _ = approved_submission
        admin = StatisticsAdminFactory()

        SubmissionAdminService.approve(submission, admin)

        log = AuditLog.objects.filter(
            target_model='WeeklySubmission',
            target_id=submission.pk,
            action_type=AuditLog.ActionType.SUBMISSION_ADMIN_APPROVED,
        ).first()
        assert log is not None
        assert log.actor == admin
        assert log.actor_role == 'statistics_admin'
        assert log.reason == ''

    def test_admin_approve_second_time_fails_for_another_admin(self, approved_submission):
        """بعد مراجعة موظّف إحصاء، لا يُسمح لموظّف آخر بالمراجعة."""
        submission, _ = approved_submission
        admin1 = StatisticsAdminFactory()
        admin2 = StatisticsAdminFactory()

        SubmissionAdminService.approve(submission, admin1)

        submission.refresh_from_db()
        with pytest.raises(ValidationError, match='تمّت مراجعة هذا المنجز'):
            SubmissionAdminService.approve(submission, admin2)

    def test_admin_approve_rejects_non_admin_user(self, approved_submission):
        submission, _ = approved_submission
        planner = PlanningSectionUserFactory()

        with pytest.raises(PermissionDenied):
            SubmissionAdminService.approve(submission, planner)

    def test_admin_approve_rejects_non_approved_submission(self, approved_submission):
        submission, _ = approved_submission
        submission.status = WeeklySubmission.Status.SUBMITTED
        submission.save(update_fields=['status'])

        admin = StatisticsAdminFactory()
        with pytest.raises(ValidationError, match='المعتمدة من قسم التخطيط'):
            SubmissionAdminService.approve(submission, admin)


@pytest.mark.django_db
class TestSubmissionAdminServiceEdit:

    def test_admin_edit_changes_answer_and_logs_diff(self, approved_submission):
        submission, answer = approved_submission
        admin = StatisticsAdminFactory()

        result = SubmissionAdminService.edit(
            submission,
            admin,
            answer_edits=[{'answer_id': answer.pk, 'numeric_value': 250}],
            reason='تصحيح خطأ إدخال',
        )

        from decimal import Decimal
        answer.refresh_from_db()
        assert Decimal(answer.numeric_value) == Decimal('250')
        assert result.admin_review_action == 'edited'

        log = AuditLog.objects.filter(
            target_model='WeeklySubmission',
            target_id=submission.pk,
            action_type=AuditLog.ActionType.SUBMISSION_ADMIN_EDITED,
        ).first()
        assert log is not None
        assert log.reason == 'تصحيح خطأ إدخال'
        assert len(log.field_changes) == 1
        assert log.field_changes[0]['field'] == 'numeric_value'
        # نُقارن عبر Decimal لتفادي اختلاف تمثيل '100' vs '100.0'
        assert Decimal(log.field_changes[0]['old']) == Decimal('100')
        assert Decimal(log.field_changes[0]['new']) == Decimal('250')

    def test_admin_edit_requires_reason(self, approved_submission):
        submission, answer = approved_submission
        admin = StatisticsAdminFactory()

        with pytest.raises(ValidationError, match='سبب التعديل'):
            SubmissionAdminService.edit(
                submission,
                admin,
                answer_edits=[{'answer_id': answer.pk, 'numeric_value': 250}],
                reason='',
            )

    def test_admin_edit_rejects_unchanged_values(self, approved_submission):
        submission, answer = approved_submission
        admin = StatisticsAdminFactory()

        with pytest.raises(ValidationError, match='لم يتم تعديل أي حقل'):
            SubmissionAdminService.edit(
                submission,
                admin,
                answer_edits=[{'answer_id': answer.pk, 'numeric_value': 100}],
                reason='محاولة بدون تغيير',
            )

    def test_admin_edit_locks_submission(self, approved_submission):
        """بعد تعديل موظّف، لا يمكن لموظّف آخر إجراء شيء."""
        submission, answer = approved_submission
        admin1 = StatisticsAdminFactory()
        admin2 = StatisticsAdminFactory()

        SubmissionAdminService.edit(
            submission,
            admin1,
            answer_edits=[{'answer_id': answer.pk, 'numeric_value': 150}],
            reason='تصحيح',
        )

        submission.refresh_from_db()
        with pytest.raises(ValidationError, match='تمّت مراجعة هذا المنجز'):
            SubmissionAdminService.approve(submission, admin2)


@pytest.mark.django_db
class TestSubmissionAdminServiceReturn:

    def test_admin_return_transitions_to_returned_by_admin(self, approved_submission):
        submission, _ = approved_submission
        admin = StatisticsAdminFactory()

        result = SubmissionAdminService.return_to_planning(
            submission, admin, reason='بيانات تحتاج إعادة تدقيق'
        )

        assert result.status == WeeklySubmission.Status.RETURNED_BY_ADMIN
        assert result.admin_review_action == 'returned'
        assert 'إرجاع من الإحصاء' in result.notes

    def test_admin_return_requires_reason(self, approved_submission):
        submission, _ = approved_submission
        admin = StatisticsAdminFactory()

        with pytest.raises(ValidationError, match='سبب الإرجاع'):
            SubmissionAdminService.return_to_planning(submission, admin, reason='')

    def test_admin_return_writes_audit_with_reason(self, approved_submission):
        submission, _ = approved_submission
        admin = StatisticsAdminFactory()

        SubmissionAdminService.return_to_planning(
            submission, admin, reason='رقم غير منطقي'
        )

        log = AuditLog.objects.filter(
            action_type=AuditLog.ActionType.SUBMISSION_ADMIN_RETURNED,
            target_id=submission.pk,
        ).first()
        assert log is not None
        assert log.reason == 'رقم غير منطقي'

    def test_returned_by_admin_is_always_editable(self, approved_submission):
        """المنجز المُرجَع من الإحصاء قابل للتعديل حتى لو انتهى الأسبوع."""
        submission, _ = approved_submission
        admin = StatisticsAdminFactory()

        # جعل الأسبوع «منتهياً» — deadline في الماضي + الفترة مغلقة
        submission.weekly_period.status = 'closed'
        submission.weekly_period.deadline = (
            timezone.now() - timezone.timedelta(days=7)
        )
        submission.weekly_period.save()

        SubmissionAdminService.return_to_planning(
            submission, admin, reason='تصحيح'
        )

        submission.refresh_from_db()
        assert submission.is_editable() is True


@pytest.mark.django_db
class TestPlanningReapproveAfterAdminReturn:
    """
    بعد إرجاع الإحصاء → تعديل التخطيط → إعادة الاعتماد: يجب أن تُمسَح
    حقول admin_reviewed_* حتى يُراجع الإحصاء النسخة الجديدة.
    """

    @patch('apps.submissions.services._notify_submission_approved')
    def test_planning_reapprove_resets_admin_review_fields(
        self, _mock_notify, approved_submission
    ):
        submission, _ = approved_submission
        admin = StatisticsAdminFactory()
        SubmissionAdminService.return_to_planning(
            submission, admin, reason='تصحيح'
        )

        # التخطيط يُعيد اعتماد المنجز
        submission.refresh_from_db()
        planner = PlanningSectionUserFactory(unit=submission.qism)
        # تجنّب فحص النطاق — نُلبّي الشرط بتعيين unit=submission.qism.parent
        # نُستخدم patch للطبقة الفحصيّة
        with patch.object(
            SubmissionService, '_assert_planning_scope', return_value=None
        ):
            SubmissionService.approve(submission, planner)

        submission.refresh_from_db()
        assert submission.status == WeeklySubmission.Status.APPROVED
        assert submission.admin_reviewed_at is None
        assert submission.admin_reviewed_by is None
        assert submission.admin_review_action == ''
