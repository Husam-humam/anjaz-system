"""
اختبارات طبقة الخدمات لتطبيق التقارير.
"""
import io

import pytest

from apps.accounts.tests.factories import StatisticsAdminFactory
from apps.forms.tests.factories import FormTemplateFactory, FormTemplateItemFactory
from apps.indicators.tests.factories import IndicatorFactory
from apps.organization.tests.factories import QismFactory
from apps.reports.services import ReportService
from apps.submissions.tests.factories import (
    SubmissionAnswerFactory,
    WeeklyPeriodFactory,
    WeeklySubmissionFactory,
)


@pytest.mark.django_db
class TestReportServiceSummary:
    """اختبارات ملخص لوحة التحكم"""

    def test_get_summary(self):
        """الحصول على ملخص لوحة التحكم للمدير"""
        admin = StatisticsAdminFactory()
        qism = QismFactory()
        period = WeeklyPeriodFactory(year=2025, week_number=10)

        template = FormTemplateFactory(qism=qism, status="approved")
        WeeklySubmissionFactory(
            qism=qism,
            weekly_period=period,
            form_template=template,
            status="approved",
        )

        summary = ReportService.get_summary(admin, year=2025, week_number=10)

        assert "total_submissions" in summary
        assert "compliance_rate" in summary
        assert "approved_submissions" in summary
        assert "pending_qualitative" in summary
        assert "status_breakdown" in summary
        assert summary["total_submissions"] >= 1
        assert summary["approved_submissions"] >= 1

    def test_get_summary_empty(self):
        """الملخص بدون بيانات"""
        admin = StatisticsAdminFactory()
        summary = ReportService.get_summary(admin, year=2030)

        assert summary["total_submissions"] == 0
        assert summary["compliance_rate"] == 0


@pytest.mark.django_db
class TestReportServiceCompliance:
    """اختبارات تقرير الامتثال"""

    def test_get_compliance_report(self):
        """تقرير الامتثال يرجع بيانات لكل قسم"""
        qism = QismFactory()
        period = WeeklyPeriodFactory(year=2025, week_number=5)
        template = FormTemplateFactory(qism=qism, status="approved")
        WeeklySubmissionFactory(
            qism=qism,
            weekly_period=period,
            form_template=template,
            status="approved",
        )

        compliance = ReportService.get_compliance_report(year=2025)

        assert isinstance(compliance, list)
        # يجب أن يتضمن القسم الذي أنشأناه
        qism_names = [c["qism_name"] for c in compliance]
        assert qism.name in qism_names

        qism_data = next(c for c in compliance if c["qism_name"] == qism.name)
        assert qism_data["submitted"] >= 1
        assert "compliance_rate" in qism_data
        assert "total_periods" in qism_data
        assert "late" in qism_data


@pytest.mark.django_db
class TestReportServiceAggregation:
    """اختبارات تجميع القيم في التقارير"""

    def test_aggregate_values_sum(self):
        """تجميع القيم بطريقة المجموع"""
        result = ReportService._aggregate_values([10, 20, 30], "sum")
        assert result == 60

    def test_aggregate_values_average(self):
        """تجميع القيم بطريقة المتوسط"""
        result = ReportService._aggregate_values([10, 20, 30], "average")
        assert result == 20.0

    def test_aggregate_values_last_value(self):
        """تجميع القيم بطريقة آخر قيمة"""
        result = ReportService._aggregate_values([10, 20, 30], "last_value")
        assert result == 30

    def test_aggregate_values_empty(self):
        """تجميع قائمة فارغة يرجع صفر"""
        result = ReportService._aggregate_values([], "sum")
        assert result == 0


@pytest.mark.django_db
class TestReportServiceExport:
    """اختبارات تصدير التقارير"""

    def test_export_excel_returns_bytesio(self):
        """تصدير Excel يرجع كائن BytesIO"""
        report_data = {
            "results": [
                {
                    "qism_name": "قسم التقنية",
                    "indicator_name": "عدد الأجهزة",
                    "aggregated_value": 150,
                    "accumulation_type": "sum",
                    "data_points": 4,
                }
            ],
            "period_type": "weekly",
            "year": 2025,
        }

        output = ReportService.export_excel(report_data, "تقرير أسبوعي - 2025")

        assert isinstance(output, io.BytesIO)
        # التحقق من أن الملف ليس فارغاً
        content = output.read()
        assert len(content) > 0

    def test_export_pdf_returns_bytesio(self):
        """تصدير PDF يرجع كائن BytesIO"""
        report_data = {
            "results": [
                {
                    "qism_name": "قسم الشؤون",
                    "indicator_name": "ساعات العمل",
                    "aggregated_value": 320,
                    "accumulation_type": "sum",
                    "data_points": 8,
                }
            ],
            "period_type": "monthly",
            "year": 2025,
        }

        output = ReportService.export_pdf(report_data, "تقرير شهري - 2025")

        assert isinstance(output, io.BytesIO)
        content = output.read()
        assert len(content) > 0

    def test_export_excel_empty_results(self):
        """تصدير Excel بدون نتائج"""
        report_data = {"results": []}
        output = ReportService.export_excel(report_data, "تقرير فارغ")

        assert isinstance(output, io.BytesIO)
        content = output.read()
        assert len(content) > 0

    def test_export_pdf_empty_results(self):
        """تصدير PDF بدون نتائج"""
        report_data = {"results": []}
        output = ReportService.export_pdf(report_data, "تقرير فارغ")

        assert isinstance(output, io.BytesIO)
        content = output.read()
        assert len(content) > 0
