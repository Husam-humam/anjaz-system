# TESTING.md — Testing Strategy & Test Cases

---

## 1. Testing Philosophy

- **Test behavior, not implementation.** Tests verify that the system does the right thing, not how it does it.
- **Every business rule has a test.** See `docs/DATABASE.md` section 4 for business rules — each one maps to at least one test.
- **Arabic error messages are part of the contract.** Test that the correct Arabic message is returned.
- **No test should depend on another test.** Each test is fully isolated.

---

## 2. Backend Testing Stack

| Tool | Purpose |
|---|---|
| `pytest` + `pytest-django` | Test runner |
| `factory_boy` | Test data factories |
| `faker` | Fake Arabic data |
| `pytest-cov` | Coverage reporting |
| `freezegun` | Time mocking (for deadline tests) |

**Run tests:**
```bash
pytest --cov=apps --cov-report=html
# Target: > 85% coverage
```

---

## 3. Test File Structure

```
apps/organization/tests/
├── factories.py          # OrganizationUnitFactory, etc.
├── test_models.py        # Model validation tests
├── test_services.py      # Business logic tests
└── test_api.py           # API endpoint tests

apps/submissions/tests/
├── factories.py
├── test_models.py        # is_editable(), business rules
├── test_services.py      # SubmissionService tests
├── test_aggregation.py   # Accumulation logic tests
└── test_api.py
```

---

## 4. Factories

```python
# apps/organization/tests/factories.py
import factory
from apps.organization.models import OrganizationUnit

class DairaFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = OrganizationUnit

    name = factory.Sequence(lambda n: f"دائرة {n}")
    code = factory.Sequence(lambda n: f"D{n:03d}")
    unit_type = "daira"
    qism_role = "regular"
    parent = None

class MudiriyaFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = OrganizationUnit

    name = factory.Sequence(lambda n: f"مديرية {n}")
    code = factory.Sequence(lambda n: f"M{n:03d}")
    unit_type = "mudiriya"
    qism_role = "regular"
    parent = factory.SubFactory(DairaFactory)

class QismFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = OrganizationUnit

    name = factory.Sequence(lambda n: f"قسم {n}")
    code = factory.Sequence(lambda n: f"Q{n:03d}")
    unit_type = "qism"
    qism_role = "regular"
    parent = factory.SubFactory(MudiriyaFactory)

class PlanningQismFactory(QismFactory):
    qism_role = "planning"

class StatisticsQismFactory(QismFactory):
    qism_role = "statistics"
```

---

## 5. Model Tests

### 5.1 Organization Validation Tests

```python
# apps/organization/tests/test_models.py
import pytest
from django.core.exceptions import ValidationError
from .factories import DairaFactory, MudiriyaFactory, QismFactory

class TestOrganizationUnitValidation:

    def test_daira_cannot_have_parent(self):
        daira = DairaFactory()
        child_daira = DairaFactory.build(parent=daira)
        with pytest.raises(ValidationError) as exc:
            child_daira.full_clean()
        assert "الدائرة لا يمكن أن تتبع كيانًا آخر" in str(exc.value)

    def test_mudiriya_must_have_daira_parent_or_none(self):
        other_mudiriya = MudiriyaFactory()
        invalid_mudiriya = MudiriyaFactory.build(parent=other_mudiriya)
        with pytest.raises(ValidationError):
            invalid_mudiriya.full_clean()

    def test_mudiriya_can_be_independent(self):
        mudiriya = MudiriyaFactory.build(parent=None)
        mudiriya.full_clean()  # Should not raise

    def test_qism_parent_can_be_mudiriya(self):
        mudiriya = MudiriyaFactory()
        qism = QismFactory.build(parent=mudiriya)
        qism.full_clean()  # Should not raise

    def test_qism_parent_can_be_daira(self):
        daira = DairaFactory()
        qism = QismFactory.build(parent=daira, unit_type="qism")
        qism.full_clean()  # Should not raise

    def test_qism_cannot_be_parent_of_another_unit(self):
        qism = QismFactory()
        child = QismFactory.build(parent=qism)
        with pytest.raises(ValidationError):
            child.full_clean()

    def test_get_full_path_returns_ancestor_chain(self):
        daira = DairaFactory(name="دائرة الشؤون")
        mudiriya = MudiriyaFactory(name="مديرية الموارد", parent=daira)
        qism = QismFactory(name="قسم التوظيف", parent=mudiriya)
        assert qism.get_full_path() == "دائرة الشؤون / مديرية الموارد / قسم التوظيف"
```

### 5.2 Submission Editability Tests

```python
# apps/submissions/tests/test_models.py
import pytest
from freezegun import freeze_time
from django.utils import timezone
from .factories import WeeklySubmissionFactory, QismExtensionFactory

class TestWeeklySubmissionEditability:

    @freeze_time("2025-04-14 10:00:00")
    def test_submission_is_editable_before_deadline(self):
        submission = WeeklySubmissionFactory(
            weekly_period__status="open",
            weekly_period__deadline=timezone.datetime(2025, 4, 14, 23, 59, 0)
        )
        assert submission.is_editable() is True

    @freeze_time("2025-04-15 01:00:00")
    def test_submission_not_editable_after_deadline(self):
        submission = WeeklySubmissionFactory(
            weekly_period__status="open",
            weekly_period__deadline=timezone.datetime(2025, 4, 14, 23, 59, 0)
        )
        assert submission.is_editable() is False

    @freeze_time("2025-04-15 10:00:00")
    def test_submission_editable_with_valid_extension(self):
        submission = WeeklySubmissionFactory(
            weekly_period__deadline=timezone.datetime(2025, 4, 14, 23, 59, 0)
        )
        QismExtensionFactory(
            qism=submission.qism,
            weekly_period=submission.weekly_period,
            new_deadline=timezone.datetime(2025, 4, 16, 23, 59, 0)
        )
        assert submission.is_editable() is True

    @freeze_time("2025-04-17 10:00:00")
    def test_submission_not_editable_after_extension_expires(self):
        submission = WeeklySubmissionFactory(
            weekly_period__deadline=timezone.datetime(2025, 4, 14, 23, 59, 0)
        )
        QismExtensionFactory(
            qism=submission.qism,
            weekly_period=submission.weekly_period,
            new_deadline=timezone.datetime(2025, 4, 16, 23, 59, 0)
        )
        assert submission.is_editable() is False
```

---

## 6. Service Layer Tests

### 6.1 Submission Service Tests

```python
# apps/submissions/tests/test_services.py
import pytest
from django.core.exceptions import ValidationError
from apps.submissions.services import SubmissionService
from .factories import WeeklySubmissionFactory

class TestSubmissionService:

    def test_submit_transitions_to_submitted(self):
        submission = WeeklySubmissionFactory(status="draft")
        SubmissionService.submit(submission, submission.qism.users.first())
        submission.refresh_from_db()
        assert submission.status == "submitted"
        assert submission.submitted_at is not None

    def test_submit_fails_after_deadline(self, frozen_after_deadline):
        submission = WeeklySubmissionFactory(status="draft")
        with pytest.raises(ValidationError) as exc:
            SubmissionService.submit(submission, user=None)
        assert "انقضاء الموعد" in str(exc.value)

    def test_approve_transitions_to_approved(self):
        submission = WeeklySubmissionFactory(status="submitted")
        planner = submission.qism.parent.users.filter(
            role="planning_section"
        ).first()
        SubmissionService.approve(submission, planner)
        submission.refresh_from_db()
        assert submission.status == "approved"

    def test_approve_sends_qualitative_to_pending_statistics(self):
        submission = WeeklySubmissionFactory(status="submitted")
        SubmissionAnswerFactory(
            submission=submission,
            is_qualitative=True,
            qualitative_status="pending_planning"
        )
        SubmissionService.approve(submission, planner=None)
        answer = submission.answers.first()
        assert answer.qualitative_status == "pending_statistics"
```

### 6.2 Aggregation Tests

```python
# apps/submissions/tests/test_aggregation.py
import pytest
from apps.submissions.services import AggregationService
from apps.indicators.models import Indicator

class TestAggregation:

    def test_sum_accumulation_adds_weekly_values(self):
        """SUM indicator: monthly value = sum of 4 weeks."""
        indicator = IndicatorFactory(accumulation_type="sum")
        submissions = [
            SubmissionAnswerFactory(
                numeric_value=val,
                form_item__indicator=indicator
            )
            for val in [10, 15, 8, 12]
        ]
        result = AggregationService.aggregate(submissions, "sum")
        assert result == 45

    def test_average_accumulation(self):
        """AVERAGE indicator: monthly value = avg of weeks."""
        indicator = IndicatorFactory(accumulation_type="average")
        values = [10, 20, 30, 40]
        result = AggregationService.aggregate(
            create_answers(indicator, values), "average"
        )
        assert result == 25.0

    def test_last_value_accumulation(self):
        """LAST_VALUE indicator: returns only the most recent week's value."""
        indicator = IndicatorFactory(accumulation_type="last_value")
        # Weeks 10, 11, 12 — week 12 is most recent
        result = AggregationService.aggregate(
            create_ordered_answers(indicator, week_values={10: 5, 11: 8, 12: 3}),
            "last_value"
        )
        assert result == 3

    def test_no_target_does_not_break_aggregation(self):
        """Aggregation works normally when no target is set."""
        indicator = IndicatorFactory(accumulation_type="sum")
        # No Target object created
        answers = [SubmissionAnswerFactory(numeric_value=10)]
        result = AggregationService.aggregate(answers, "sum")
        assert result == 10
        # No exception raised

    def test_hierarchical_sum_aggregation(self):
        """Mudiriya total = sum of all qisms under it."""
        mudiriya = MudiriyaFactory()
        qism1 = QismFactory(parent=mudiriya)
        qism2 = QismFactory(parent=mudiriya)
        # qism1 submitted 30, qism2 submitted 20
        result = AggregationService.aggregate_hierarchy(mudiriya, indicator, year=2025)
        assert result == 50
```

---

## 7. API Tests

### 7.1 Permission Tests

```python
# apps/submissions/tests/test_api.py
import pytest
from rest_framework.test import APIClient
from apps.accounts.tests.factories import UserFactory

class TestSubmissionPermissions:

    def test_section_manager_cannot_approve_submission(self, api_client):
        manager = UserFactory(role="section_manager")
        submission = WeeklySubmissionFactory(status="submitted")
        api_client.force_authenticate(manager)
        response = api_client.post(f"/api/submissions/{submission.id}/approve/")
        assert response.status_code == 403

    def test_planning_section_cannot_access_other_directorate(self, api_client):
        planner = UserFactory(role="planning_section")
        other_qism = QismFactory()  # Different directorate
        submission = WeeklySubmissionFactory(qism=other_qism)
        api_client.force_authenticate(planner)
        response = api_client.get(f"/api/submissions/{submission.id}/")
        assert response.status_code == 404  # Scoped query returns 404

    def test_unauthenticated_request_returns_401(self):
        client = APIClient()
        response = client.get("/api/submissions/")
        assert response.status_code == 401

    def test_statistics_admin_can_access_all_submissions(self, api_client):
        admin = UserFactory(role="statistics_admin")
        api_client.force_authenticate(admin)
        response = api_client.get("/api/submissions/")
        assert response.status_code == 200
```

### 7.2 Validation Error Message Tests (Arabic)

```python
class TestArabicErrorMessages:

    def test_missing_mandatory_field_returns_arabic_error(self, api_client, section_manager):
        api_client.force_authenticate(section_manager)
        response = api_client.post("/api/submissions/", data={})
        assert response.status_code == 400
        # Error messages must be in Arabic
        error_data = response.json()
        assert "مطلوب" in str(error_data)

    def test_deadline_passed_returns_arabic_error(self, api_client, section_manager):
        submission = WeeklySubmissionFactory(status="draft")
        with freeze_time("2025-04-20"):  # Past deadline
            response = api_client.post(f"/api/submissions/{submission.id}/submit/")
        assert response.status_code == 422
        assert "انقضاء الموعد" in response.json()["message"]

    def test_permission_denied_returns_arabic_error(self, api_client):
        manager = UserFactory(role="section_manager")
        api_client.force_authenticate(manager)
        response = api_client.post("/api/users/", data={})
        assert response.status_code == 403
        assert "صلاحية" in response.json()["message"]
```

### 7.3 Form Template Versioning Tests

```python
class TestFormTemplateVersioning:

    def test_approving_new_version_supersedes_old(self, api_client, stats_admin):
        qism = QismFactory()
        v1 = FormTemplateFactory(qism=qism, status="approved", version=1)
        v2 = FormTemplateFactory(qism=qism, status="pending_approval", version=2)

        api_client.force_authenticate(stats_admin)
        api_client.post(f"/api/forms/templates/{v2.id}/approve/", data={
            "effective_from_week": 20,
            "effective_from_year": 2025
        })

        v1.refresh_from_db()
        v2.refresh_from_db()
        assert v1.status == "superseded"
        assert v2.status == "approved"

    def test_submission_links_to_template_version_at_time_of_submission(self):
        qism = QismFactory()
        v1 = FormTemplateFactory(qism=qism, status="approved", version=1)
        submission = WeeklySubmissionFactory(qism=qism, form_template=v1)

        # Now v2 gets approved — submission still references v1
        v2 = FormTemplateFactory(qism=qism, status="approved", version=2)
        submission.refresh_from_db()
        assert submission.form_template.version == 1
```

---

## 8. Frontend Tests

### 8.1 Tools

| Tool | Purpose |
|---|---|
| `Jest` + `React Testing Library` | Component tests |
| `MSW (Mock Service Worker)` | API mocking |
| `Playwright` | E2E tests |

### 8.2 Component Tests

```typescript
// components/StatusBadge.test.tsx
describe('StatusBadge', () => {
  it('renders Arabic label for approved status', () => {
    render(<StatusBadge status="approved" />);
    expect(screen.getByText('معتمد')).toBeInTheDocument();
  });

  it('renders Arabic label for late status', () => {
    render(<StatusBadge status="late" />);
    expect(screen.getByText('متأخر')).toBeInTheDocument();
  });

  it('applies correct color class for late status', () => {
    const { container } = render(<StatusBadge status="late" />);
    expect(container.firstChild).toHaveClass('text-red-600');
  });
});
```

### 8.3 E2E Tests (Playwright)

```typescript
// e2e/submission.spec.ts
test('section manager can submit weekly achievement', async ({ page }) => {
  await page.goto('/login');
  await page.fill('[name=username]', 'section_user');
  await page.fill('[name=password]', 'password');
  await page.click('button:has-text("تسجيل الدخول")');

  await page.goto('/submission');
  await expect(page.locator('h1')).toContainText('تقديم المنجز');

  // Fill numeric answer
  await page.fill('[data-testid="answer-1"]', '15');

  // Flag qualitative
  await page.check('[data-testid="qualitative-1"]');
  await page.fill('[data-testid="qualitative-details-1"]', 'تقرير السلامة المهنية السنوي');

  await page.click('button:has-text("إرسال المنجز للاعتماد")');
  await page.click('button:has-text("تأكيد")');  // Confirmation dialog

  await expect(page.locator('[data-testid="status-badge"]')).toContainText('مُرسل');
});
```

---

## 9. Critical Test Scenarios Checklist

Before any release, verify all these scenarios pass:

### Organization
- [ ] Daira cannot have parent
- [ ] Qism cannot be parent of another unit
- [ ] get_full_path() returns correct ancestor chain
- [ ] Independent mudiriya works correctly

### Form Templates
- [ ] Approval supersedes previous version
- [ ] New version takes effect from correct week
- [ ] Historical submissions reference old template version
- [ ] Rejection returns correct Arabic message

### Weekly Submissions
- [ ] Submission editable before deadline
- [ ] Submission not editable after deadline
- [ ] Extension grants editability past deadline
- [ ] Mandatory fields enforced on submit
- [ ] Qualitative details required when flagged

### Aggregation
- [ ] SUM accumulation correct
- [ ] AVERAGE accumulation correct
- [ ] LAST_VALUE returns most recent week
- [ ] Hierarchical aggregation (qism → mudiriya → daira)
- [ ] Missing target does not break calculation

### Permissions
- [ ] section_manager cannot access other sections
- [ ] planning_section cannot access other directorates
- [ ] section_manager cannot approve submissions
- [ ] Unauthenticated requests return 401

### Notifications
- [ ] Notification created on week open
- [ ] Notification created on submission approval
- [ ] Notification created on qualitative approved/rejected
- [ ] WebSocket delivers notification in real-time
