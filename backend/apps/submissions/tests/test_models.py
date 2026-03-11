import pytest
from freezegun import freeze_time
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import datetime

from .factories import (
    WeeklySubmissionFactory,
    WeeklyPeriodFactory,
    QismExtensionFactory,
    SubmissionAnswerFactory,
)
from apps.forms.tests.factories import FormTemplateItemFactory
from apps.indicators.tests.factories import IndicatorFactory


@pytest.mark.django_db
class TestWeeklySubmissionEditability:
    """اختبارات التحقق من إمكانية تعديل المنجز الأسبوعي"""

    @freeze_time("2025-04-14 10:00:00")
    def test_submission_is_editable_before_deadline(self):
        """المنجز قابل للتعديل قبل الموعد النهائي"""
        submission = WeeklySubmissionFactory(
            weekly_period__status="open",
            weekly_period__deadline=timezone.make_aware(
                datetime(2025, 4, 14, 23, 59, 0)
            ),
        )
        assert submission.is_editable() is True

    @freeze_time("2025-04-15 01:00:00")
    def test_submission_not_editable_after_deadline(self):
        """المنجز غير قابل للتعديل بعد الموعد النهائي"""
        submission = WeeklySubmissionFactory(
            weekly_period__status="open",
            weekly_period__deadline=timezone.make_aware(
                datetime(2025, 4, 14, 23, 59, 0)
            ),
        )
        assert submission.is_editable() is False

    @freeze_time("2025-04-15 10:00:00")
    def test_submission_editable_with_valid_extension(self):
        """المنجز قابل للتعديل مع وجود تمديد صالح"""
        submission = WeeklySubmissionFactory(
            weekly_period__deadline=timezone.make_aware(
                datetime(2025, 4, 14, 23, 59, 0)
            ),
        )
        QismExtensionFactory(
            qism=submission.qism,
            weekly_period=submission.weekly_period,
            new_deadline=timezone.make_aware(
                datetime(2025, 4, 16, 23, 59, 0)
            ),
        )
        assert submission.is_editable() is True

    @freeze_time("2025-04-17 10:00:00")
    def test_submission_not_editable_after_extension_expires(self):
        """المنجز غير قابل للتعديل بعد انتهاء التمديد"""
        submission = WeeklySubmissionFactory(
            weekly_period__deadline=timezone.make_aware(
                datetime(2025, 4, 14, 23, 59, 0)
            ),
        )
        QismExtensionFactory(
            qism=submission.qism,
            weekly_period=submission.weekly_period,
            new_deadline=timezone.make_aware(
                datetime(2025, 4, 16, 23, 59, 0)
            ),
        )
        assert submission.is_editable() is False

    @freeze_time("2025-04-14 10:00:00")
    def test_submission_not_editable_when_period_closed(self):
        """المنجز غير قابل للتعديل عند إغلاق الفترة"""
        submission = WeeklySubmissionFactory(
            weekly_period__status="closed",
            weekly_period__deadline=timezone.make_aware(
                datetime(2025, 4, 14, 23, 59, 0)
            ),
        )
        assert submission.is_editable() is False


@pytest.mark.django_db
class TestSubmissionAnswerValidation:
    """اختبارات التحقق من صحة إجابات المنجز"""

    def test_qualitative_details_required_when_flagged(self):
        """تفاصيل المنجز النوعي مطلوبة عند تفعيل علامة النوعي"""
        indicator = IndicatorFactory(unit_type="number")
        template_item = FormTemplateItemFactory(indicator=indicator)
        submission = WeeklySubmissionFactory(form_template=template_item.form_template)

        answer = SubmissionAnswerFactory.build(
            submission=submission,
            form_item=template_item,
            is_qualitative=True,
            qualitative_details="",
            numeric_value=10,
        )
        with pytest.raises(ValidationError) as exc:
            answer.full_clean()
        assert "يجب إدخال تفاصيل المنجز النوعي" in str(exc.value)

    def test_qualitative_valid_with_details(self):
        """إجابة نوعية صالحة مع وجود تفاصيل"""
        indicator = IndicatorFactory(unit_type="number")
        template_item = FormTemplateItemFactory(indicator=indicator)
        submission = WeeklySubmissionFactory(form_template=template_item.form_template)

        answer = SubmissionAnswerFactory.build(
            submission=submission,
            form_item=template_item,
            is_qualitative=True,
            qualitative_details="تم إنجاز تقرير السلامة المهنية",
            numeric_value=10,
        )
        answer.full_clean()  # يجب ألا يرفع استثناء

    def test_percentage_value_must_be_between_0_and_100(self):
        """النسبة المئوية يجب أن تكون بين 0 و 100"""
        indicator = IndicatorFactory(unit_type="percentage", accumulation_type="average")
        template_item = FormTemplateItemFactory(indicator=indicator)
        submission = WeeklySubmissionFactory(form_template=template_item.form_template)

        answer = SubmissionAnswerFactory.build(
            submission=submission,
            form_item=template_item,
            numeric_value=150,
        )
        with pytest.raises(ValidationError) as exc:
            answer.full_clean()
        assert "النسبة المئوية يجب أن تكون بين 0 و 100" in str(exc.value)


@pytest.mark.django_db
class TestWeeklyPeriodValidation:
    """اختبارات التحقق من صحة الفترة الأسبوعية"""

    def test_week_number_must_be_between_1_and_53(self):
        """رقم الأسبوع يجب أن يكون بين 1 و 53"""
        period = WeeklyPeriodFactory.build(week_number=0)
        with pytest.raises(ValidationError) as exc:
            period.full_clean()
        assert "رقم الأسبوع يجب أن يكون بين 1 و 53" in str(exc.value)

    def test_end_date_must_be_after_start_date(self):
        """تاريخ النهاية يجب أن يكون بعد تاريخ البداية"""
        from datetime import date
        period = WeeklyPeriodFactory.build(
            start_date=date(2025, 4, 15),
            end_date=date(2025, 4, 10),
        )
        with pytest.raises(ValidationError) as exc:
            period.full_clean()
        assert "تاريخ النهاية يجب أن يكون بعد تاريخ البداية" in str(exc.value)

    def test_weekly_period_str(self):
        """__str__ يرجع رقم الأسبوع والسنة"""
        period = WeeklyPeriodFactory.build(year=2025, week_number=15)
        assert str(period) == "الأسبوع 15 / 2025"

    def test_weekly_submission_str(self):
        """__str__ يرجع اسم القسم والفترة"""
        submission = WeeklySubmissionFactory.build()
        result = str(submission)
        assert submission.qism.name in result


@pytest.mark.django_db
class TestQismExtensionValidation:
    """اختبارات التحقق من صحة تمديد الموعد"""

    def test_new_deadline_must_be_after_original(self):
        """الموعد الجديد يجب أن يكون بعد الموعد الأصلي"""
        period = WeeklyPeriodFactory(
            deadline=timezone.make_aware(datetime(2025, 4, 14, 23, 59, 0))
        )
        extension = QismExtensionFactory.build(
            weekly_period=period,
            new_deadline=timezone.make_aware(datetime(2025, 4, 13, 23, 59, 0)),
        )
        with pytest.raises(ValidationError) as exc:
            extension.full_clean()
        assert "الموعد الجديد يجب أن يكون بعد الموعد الأصلي" in str(exc.value)

    def test_extension_str(self):
        """__str__ يرجع معلومات التمديد"""
        extension = QismExtensionFactory.build()
        result = str(extension)
        assert "تمديد" in result
