import pytest
from rest_framework.test import APIClient

from apps.accounts.tests.factories import (
    StatisticsAdminFactory,
    PlanningSectionUserFactory,
    SectionManagerFactory,
)
from apps.organization.tests.factories import (
    DairaFactory,
    MudiriyaFactory,
    QismFactory,
    PlanningQismFactory,
)
from .factories import WeeklySubmissionFactory, WeeklyPeriodFactory


@pytest.mark.django_db
class TestSubmissionPermissions:
    """اختبارات صلاحيات الوصول للمنجزات"""

    def test_section_manager_cannot_approve_submission(self, api_client):
        """مدير القسم لا يمكنه اعتماد المنجز"""
        manager = SectionManagerFactory()
        submission = WeeklySubmissionFactory(
            qism=manager.unit,
            status="submitted",
        )
        api_client.force_authenticate(manager)
        response = api_client.post(f"/api/submissions/{submission.id}/approve/")
        assert response.status_code == 403

    def test_planning_section_cannot_access_other_directorate(self, api_client):
        """قسم التخطيط لا يمكنه الوصول لمنجزات مديرية أخرى"""
        # إنشاء مديرية أولى مع قسم تخطيط
        daira = DairaFactory()
        mudiriya1 = MudiriyaFactory(parent=daira)
        planning_qism = PlanningQismFactory(parent=mudiriya1)
        planner = PlanningSectionUserFactory(unit=planning_qism)

        # إنشاء مديرية ثانية مع قسم ومنجز
        mudiriya2 = MudiriyaFactory(parent=daira)
        other_qism = QismFactory(parent=mudiriya2)
        submission = WeeklySubmissionFactory(qism=other_qism)

        api_client.force_authenticate(planner)
        response = api_client.get(f"/api/submissions/{submission.id}/")
        assert response.status_code == 404  # النطاق المحدود يرجع 404

    def test_unauthenticated_request_returns_401(self):
        """الطلب بدون مصادقة يرجع 401"""
        client = APIClient()
        response = client.get("/api/submissions/")
        assert response.status_code == 401

    def test_statistics_admin_can_access_all_submissions(self, api_client):
        """مدير الإحصاء يمكنه الوصول لجميع المنجزات"""
        admin = StatisticsAdminFactory()
        WeeklySubmissionFactory()
        WeeklySubmissionFactory()
        api_client.force_authenticate(admin)
        response = api_client.get("/api/submissions/")
        assert response.status_code == 200

    def test_section_manager_can_only_see_own_submissions(self, api_client):
        """مدير القسم يرى منجزات قسمه فقط"""
        manager = SectionManagerFactory()
        # منجز قسم المدير
        own_submission = WeeklySubmissionFactory(qism=manager.unit)
        # منجز قسم آخر
        other_submission = WeeklySubmissionFactory()

        api_client.force_authenticate(manager)
        response = api_client.get("/api/submissions/")
        assert response.status_code == 200
        submission_ids = [s["id"] for s in response.data["results"]] if "results" in response.data else [s["id"] for s in response.data]
        assert own_submission.id in submission_ids
        assert other_submission.id not in submission_ids

    def test_planning_section_approve_requires_submitted_status(self, api_client):
        """اعتماد المنجز يتطلب أن يكون في حالة 'مُرسل'"""
        daira = DairaFactory()
        mudiriya = MudiriyaFactory(parent=daira)
        planning_qism = PlanningQismFactory(parent=mudiriya)
        planner = PlanningSectionUserFactory(unit=planning_qism)

        regular_qism = QismFactory(parent=mudiriya)
        submission = WeeklySubmissionFactory(
            qism=regular_qism,
            status="draft",
        )

        api_client.force_authenticate(planner)
        response = api_client.post(f"/api/submissions/{submission.id}/approve/")
        assert response.status_code == 422
