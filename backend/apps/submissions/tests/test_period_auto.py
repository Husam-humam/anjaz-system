"""
اختبارات الإدارة التلقائية للأسابيع (PeriodAutoService).
تغطي: ترقيم الأسابيع، الإنشاء التلقائي، الإغلاق التلقائي، حالات الحافة.
"""
import datetime
from unittest.mock import patch

import pytest
from django.utils import timezone
from freezegun import freeze_time

from apps.submissions.models import (
    QismExtension,
    SystemConfiguration,
    WeeklyPeriod,
)
from apps.submissions.services import PeriodAutoService
from apps.submissions.tests.factories import (
    QismExtensionFactory,
    WeeklyPeriodFactory,
)


@pytest.mark.django_db
class TestWeekNumberingLogic:
    """اختبار منطق حساب رقم الأسبوع والسنة المنطقية"""

    def test_first_saturday_of_year_is_week_1(self):
        """السبت الأول من السنة يبدأ الأسبوع الأول"""
        # 2027-01-02 هو سبت (اليوم التالي للجمعة 2027-01-01)
        date = datetime.date(2027, 1, 2)
        year, week, start, end = PeriodAutoService.compute_week_number_and_year(
            date, start_day=5  # Saturday
        )
        assert year == 2027
        assert week == 1
        assert start == datetime.date(2027, 1, 2)
        assert end == datetime.date(2027, 1, 8)

    def test_day_within_week_computes_correctly(self):
        """أي يوم داخل الأسبوع يُعيد نفس رقم الأسبوع"""
        # 2027-01-05 (الثلاثاء) ضمن الأسبوع الذي يبدأ 2027-01-02
        date = datetime.date(2027, 1, 5)
        year, week, start, end = PeriodAutoService.compute_week_number_and_year(
            date, start_day=5
        )
        assert year == 2027
        assert week == 1
        assert start == datetime.date(2027, 1, 2)

    def test_days_before_first_saturday_belong_to_previous_year(self):
        """الأيام قبل السبت الأول من السنة تنتمي للسنة السابقة"""
        # 2027-01-01 (الجمعة) — السبت الأول هو 2027-01-02
        # هذا اليوم ينتمي للأسبوع الأخير من 2026
        date = datetime.date(2027, 1, 1)
        year, week, start, end = PeriodAutoService.compute_week_number_and_year(
            date, start_day=5
        )
        assert year == 2026
        # الأسبوع يبدأ 2026-12-26 (السبت)
        assert start == datetime.date(2026, 12, 26)
        assert end == datetime.date(2027, 1, 1)

    def test_jan_1_saturday_is_week_1(self):
        """إذا كان 1 يناير يوم سبت، يكون الأسبوع 1"""
        # 2022-01-01 كان سبت
        date = datetime.date(2022, 1, 1)
        year, week, start, end = PeriodAutoService.compute_week_number_and_year(
            date, start_day=5
        )
        assert year == 2022
        assert week == 1
        assert start == datetime.date(2022, 1, 1)

    def test_mid_year_week(self):
        """يوم في منتصف السنة يُعيد رقم أسبوع معقول"""
        # 2026-06-15 (الاثنين)
        date = datetime.date(2026, 6, 15)
        year, week, start, end = PeriodAutoService.compute_week_number_and_year(
            date, start_day=5
        )
        assert year == 2026
        # يجب أن يكون بين 20 و 30 تقريباً
        assert 20 <= week <= 30

    def test_monday_start_day(self):
        """إذا ضُبطت بداية الأسبوع على الاثنين، يتغيّر الحساب"""
        # 2026-01-05 (الاثنين) يبدأ الأسبوع 2 إذا كانت البداية الاثنين
        # و 2026-01-01 (الخميس) ينتمي للأسبوع السابق
        date = datetime.date(2026, 1, 5)
        year, week, start, end = PeriodAutoService.compute_week_number_and_year(
            date, start_day=0  # Monday
        )
        assert start == datetime.date(2026, 1, 5)

    def test_year_with_53_weeks(self):
        """بعض السنوات تحتوي 53 أسبوعاً — يجب أن يدعمها المنطق"""
        # 2022-01-01 كان سبت، و 2022-12-31 أيضاً سبت
        # هذا يعني أن 2022 لديها 53 سبت كامل (أسابيع 1-53)
        date = datetime.date(2022, 12, 31)
        year, week, start, end = PeriodAutoService.compute_week_number_and_year(
            date, start_day=5
        )
        assert year == 2022
        assert week == 53
        assert start == datetime.date(2022, 12, 31)
        assert end == datetime.date(2023, 1, 6)

    def test_day_after_53rd_week_belongs_to_next_year_week_1(self):
        """الأيام بعد نهاية الأسبوع 53 تنتمي للسنة التالية"""
        # 2023-01-07 (الجمعة) ضمن أسبوع 2022/53 الذي ينتهي 2023-01-06
        # 2023-01-07 هو يوم سبت → بداية الأسبوع الأول من 2023
        date = datetime.date(2023, 1, 7)
        year, week, start, end = PeriodAutoService.compute_week_number_and_year(
            date, start_day=5
        )
        assert year == 2023
        assert week == 1
        assert start == datetime.date(2023, 1, 7)


@pytest.mark.django_db
class TestDeadlineComputation:
    """اختبار حساب الموعد النهائي"""

    def test_deadline_3_days_after_end_at_noon(self):
        """الافتراضي: 3 أيام بعد نهاية الأسبوع، الساعة 12 ظهراً"""
        config = SystemConfiguration.load()
        config.deadline_days_after_week_end = 3
        config.deadline_hour = 12
        config.save()

        week_end = datetime.date(2026, 4, 17)  # الجمعة
        deadline = PeriodAutoService.compute_deadline(week_end, config)
        # الموعد = الاثنين 2026-04-20 الساعة 12
        assert deadline.date() == datetime.date(2026, 4, 20)
        assert deadline.hour == 12

    def test_custom_deadline_configuration(self):
        """إعدادات مخصّصة: يومان و 9 صباحاً"""
        config = SystemConfiguration.load()
        config.deadline_days_after_week_end = 2
        config.deadline_hour = 9
        config.save()

        week_end = datetime.date(2026, 4, 17)
        deadline = PeriodAutoService.compute_deadline(week_end, config)
        assert deadline.date() == datetime.date(2026, 4, 19)
        assert deadline.hour == 9


@pytest.mark.django_db
class TestEnsureCurrentPeriod:
    """اختبار دالة ضمان وجود الأسبوع الحالي"""

    @patch("apps.submissions.services._notify_period_opened")
    def test_creates_new_period_if_none_exists(self, mock_notify):
        """يُنشئ الأسبوع الحالي إذا لم يكن موجوداً"""
        assert WeeklyPeriod.objects.count() == 0
        SystemConfiguration.load()  # ضمان وجود إعدادات افتراضية

        with freeze_time("2026-04-14 10:00:00"):  # الثلاثاء
            result = PeriodAutoService.ensure_current_period()

        assert result['created'] is not None
        period = result['created']
        assert period.status == 'open'
        # الأسبوع يبدأ السبت 2026-04-11 وينتهي الجمعة 2026-04-17
        assert period.start_date == datetime.date(2026, 4, 11)
        assert period.end_date == datetime.date(2026, 4, 17)
        mock_notify.assert_called_once()

    def test_returns_skipped_when_disabled(self):
        """لا يفعل شيئاً إذا كانت الإدارة التلقائية معطّلة"""
        config = SystemConfiguration.load()
        config.auto_create_enabled = False
        config.save()

        result = PeriodAutoService.ensure_current_period()
        assert result.get('skipped') == 'disabled'
        assert WeeklyPeriod.objects.count() == 0

    @patch("apps.submissions.services._notify_period_opened")
    def test_does_not_duplicate_existing_period(self, mock_notify):
        """لا يُنشئ نسخة مكرّرة إذا كان الأسبوع موجوداً"""
        SystemConfiguration.load()

        with freeze_time("2026-04-14 10:00:00"):
            # المرة الأولى: تُنشئ
            result1 = PeriodAutoService.ensure_current_period()
            assert result1['created'] is not None

            # المرة الثانية: لا تُنشئ
            result2 = PeriodAutoService.ensure_current_period()
            assert result2['created'] is None

        assert WeeklyPeriod.objects.count() == 1

    @patch("apps.submissions.services._notify_period_opened")
    @patch("apps.submissions.services._notify_submission_late")
    def test_closes_expired_previous_period(self, mock_late, mock_open):
        """يُغلق الأسبوع السابق إذا مرّ موعده النهائي"""
        config = SystemConfiguration.load()
        config.auto_close_previous = True
        config.save()

        # إنشاء فترة سابقة موعدها مرّ
        old_deadline = timezone.make_aware(datetime.datetime(2026, 4, 1, 12, 0))
        old_period = WeeklyPeriodFactory(
            year=2026,
            week_number=13,
            start_date=datetime.date(2026, 3, 21),
            end_date=datetime.date(2026, 3, 27),
            deadline=old_deadline,
            status='open',
        )

        with freeze_time("2026-04-14 10:00:00"):
            result = PeriodAutoService.ensure_current_period()

        old_period.refresh_from_db()
        assert old_period.status == 'closed'
        assert old_period.id in result['closed']

    @patch("apps.submissions.services._notify_period_opened")
    def test_does_not_close_period_with_active_extension(self, mock_notify):
        """لا يُغلق فترة بها تمديد ساري"""
        SystemConfiguration.load()

        # فترة سابقة بموعد منتهٍ
        old_deadline = timezone.make_aware(datetime.datetime(2026, 4, 1, 12, 0))
        old_period = WeeklyPeriodFactory(
            year=2026,
            week_number=13,
            start_date=datetime.date(2026, 3, 21),
            end_date=datetime.date(2026, 3, 27),
            deadline=old_deadline,
            status='open',
        )
        # تمديد ساري (ينتهي بعد "الآن" الافتراضي)
        QismExtensionFactory(
            weekly_period=old_period,
            new_deadline=timezone.make_aware(datetime.datetime(2026, 4, 20, 12, 0)),
        )

        with freeze_time("2026-04-14 10:00:00"):
            result = PeriodAutoService.ensure_current_period()

        old_period.refresh_from_db()
        assert old_period.status == 'open'  # لم يُغلق
        assert old_period.id not in result['closed']
