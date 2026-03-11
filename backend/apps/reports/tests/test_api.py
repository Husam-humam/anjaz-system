"""
اختبارات واجهة API لتطبيق التقارير.
"""
import pytest
from rest_framework.test import APIClient

from apps.accounts.tests.factories import StatisticsAdminFactory
from apps.forms.tests.factories import FormTemplateFactory
from apps.organization.tests.factories import QismFactory
from apps.submissions.tests.factories import (
    WeeklyPeriodFactory,
    WeeklySubmissionFactory,
)


@pytest.mark.django_db
class TestReportSummaryAPI:
    """اختبارات نقطة نهاية ملخص التقارير"""

    def test_summary_endpoint(self, api_client):
        """الحصول على ملخص التقارير"""
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

        api_client.force_authenticate(admin)
        response = api_client.get("/api/reports/summary/", {"year": 2025})

        assert response.status_code == 200
        assert "total_submissions" in response.data
        assert "compliance_rate" in response.data

    def test_unauthenticated_returns_401(self):
        """الطلب بدون مصادقة يرجع 401"""
        client = APIClient()
        response = client.get("/api/reports/summary/")
        assert response.status_code == 401


@pytest.mark.django_db
class TestReportComplianceAPI:
    """اختبارات نقطة نهاية تقرير الامتثال"""

    def test_compliance_endpoint(self, api_client):
        """الحصول على تقرير الامتثال"""
        admin = StatisticsAdminFactory()
        qism = QismFactory()
        period = WeeklyPeriodFactory(year=2025, week_number=5)
        template = FormTemplateFactory(qism=qism, status="approved")
        WeeklySubmissionFactory(
            qism=qism,
            weekly_period=period,
            form_template=template,
            status="submitted",
        )

        api_client.force_authenticate(admin)
        response = api_client.get("/api/reports/compliance/", {"year": 2025})

        assert response.status_code == 200
        assert isinstance(response.data, list)

    def test_compliance_unauthenticated(self):
        """تقرير الامتثال بدون مصادقة يرجع 401"""
        client = APIClient()
        response = client.get("/api/reports/compliance/")
        assert response.status_code == 401


@pytest.mark.django_db
class TestReportPeriodicAPI:
    """اختبارات نقطة نهاية التقرير الدوري"""

    def test_periodic_endpoint(self, api_client):
        """الحصول على تقرير دوري"""
        admin = StatisticsAdminFactory()

        api_client.force_authenticate(admin)
        response = api_client.get(
            "/api/reports/periodic/",
            {"period_type": "weekly", "year": 2025, "period_number": 1},
        )

        assert response.status_code == 200
        assert "results" in response.data
        assert "period_type" in response.data


@pytest.mark.django_db
class TestReportQualitativeAPI:
    """اختبارات نقطة نهاية تقرير المنجزات النوعية"""

    def test_qualitative_endpoint(self, api_client):
        """الحصول على تقرير المنجزات النوعية"""
        admin = StatisticsAdminFactory()

        api_client.force_authenticate(admin)
        response = api_client.get(
            "/api/reports/qualitative/",
            {"year": 2025},
        )

        assert response.status_code == 200
        assert isinstance(response.data, list)
