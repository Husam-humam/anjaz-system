# DATABASE.md — Database Design & Business Rules

---

## 1. Technology

- **PostgreSQL 16**
- **django-mptt** for the organizational hierarchy (Modified Preorder Tree Traversal)
- All tables prefixed by app name (configured via `Meta.db_table`)

---

## 2. Entity Relationship Overview

```
OrganizationUnit (MPTT Tree)
│   unit_type: daira | mudiriya | qism
│   parent → self (nullable)
│   external_id, external_synced_at, employees_count  (sourced from external system)
│
├── PlanningAssignment (planning_unit OneToOne → OrganizationUnit)
│       └── SupervisedUnit (assignment FK, unit OneToOne → OrganizationUnit)
│
├── ViewScope (user OneToOne → User, viewable_units M2M → OrganizationUnit)
│
├── ExternalUnitTypeMapping (external_type_name → treat_as)
│
├── User (unit_id FK)
│
├── FormTemplate (qism_id FK)
│       └── FormTemplateItem (form_template_id FK)
│               └── Indicator (indicator_id FK)
│                       └── IndicatorCategory
│
├── Target (scope_unit_id + indicator_id + year)
│
└── WeeklySubmission (qism_id + weekly_period_id)
        └── SubmissionAnswer (submission_id + form_item_id)
                (numeric_value + qualitative fields)

WeeklyPeriod ──────────────── WeeklySubmission
                               QismExtension (qism + weekly_period)

Notification (recipient_id → User)
```

---

## 3. Tables

### 3.1 `organization_units`

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | SERIAL | PK | |
| name | VARCHAR(200) | NOT NULL | Unit name |
| code | VARCHAR(20) | UNIQUE, NOT NULL | Short identifier |
| unit_type | VARCHAR(20) | NOT NULL | `daira` / `mudiriya` / `qism` |
| parent_id | INT | FK → self, NULL | Parent unit (NULL = root) |
| is_active | BOOLEAN | DEFAULT TRUE | Soft delete |
| external_id | INT | UNIQUE, NULL | ID of this unit in the external org system (NULL for manually-created units) |
| external_synced_at | TIMESTAMPTZ | NULL | Last successful sync with the external system |
| employees_count | INT | NOT NULL, DEFAULT 0 | Headcount, refreshed from the external system on every sync |
| created_at | TIMESTAMPTZ | auto | |
| updated_at | TIMESTAMPTZ | auto | |
| lft | INT | MPTT auto | |
| rght | INT | MPTT auto | |
| tree_id | INT | MPTT auto | |
| level | INT | MPTT auto | |

**Validation Rules:**
- `daira` → parent must be NULL
- `mudiriya` → parent must be `daira` or NULL (independent)
- `qism` → parent must be `mudiriya` or `daira`
- `qism` cannot be a parent of any other unit
- The role of a qism (planning vs. regular) is **not** stored on this table — see `planning_assignments` / `supervised_units` below.

---

### 3.1a `planning_assignments`

Declares which organization unit acts as a planning section. A unit becomes a "planning qism" by virtue of having a row here — there is no `qism_role` flag on `organization_units`.

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | SERIAL | PK | |
| planning_unit_id | INT | FK → organization_units, **UNIQUE** (OneToOne), ON DELETE PROTECT | The unit acting as planning section |
| context_parent_id | INT | FK → organization_units, NULL, ON DELETE SET NULL | Mudiriya / Daira shown in reports as the planner's organizational context — does **not** constrain supervised scope |
| notes | TEXT | | |
| created_by_id | INT | FK → users, NULL | Statistics admin who created the assignment |
| created_at | TIMESTAMPTZ | auto | |
| updated_at | TIMESTAMPTZ | auto | |

**Rules:**
- A unit can have at most one `PlanningAssignment` (OneToOne on `planning_unit`).
- The set of supervised qisms is given by `supervised_units` rows, not by MPTT descendants.

---

### 3.1b `supervised_units`

Maps an "ordinary" qism to the planning assignment that supervises it. Every qism that can submit a `WeeklySubmission` must have a row here — there is no implicit MPTT fallback.

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | SERIAL | PK | |
| assignment_id | INT | FK → planning_assignments, ON DELETE CASCADE | The supervising planning assignment |
| unit_id | INT | FK → organization_units, **UNIQUE** (OneToOne), ON DELETE PROTECT | The supervised qism |
| created_at | TIMESTAMPTZ | auto | |

**Rules:**
- `unit` is OneToOne — each qism is supervised by exactly one planning assignment.
- `unit` cannot equal `assignment.planning_unit` (a planning qism cannot supervise itself; enforced in `clean()`).

---

### 3.1c `view_scopes`

Read-only scope for a user. Used by the `viewer` role to express "this user can see exactly these units" without granting any management rights. May also extend the visibility of a `planning_section` user beyond their managed scope.

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | SERIAL | PK | |
| user_id | INT | FK → users, **UNIQUE** (OneToOne), ON DELETE CASCADE | |
| notes | TEXT | | |
| created_by_id | INT | FK → users, NULL | Statistics admin who created the scope |
| created_at | TIMESTAMPTZ | auto | |
| updated_at | TIMESTAMPTZ | auto | |

Plus the M2M table `view_scopes_viewable_units` (`view_scope_id`, `organizationunit_id`) linking to `organization_units`.

**Rules:**
- Resolution of "which qism ids this user may see" happens in `_user_view_scope_qism_ids(user)` — it merges `SupervisedUnit` + `ViewScope` + own-unit, depending on role.

---

### 3.1d `external_unit_type_mappings`

Admin-configurable mapping from the external system's unit type names to one of Anjaz's three types (or `ignore`). Read by the org-sync service to decide how to import each external unit.

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | SERIAL | PK | |
| external_type_name | VARCHAR(100) | UNIQUE, NOT NULL | e.g. value returned by `unit_type_name` from `/reference/unit-types/` |
| external_type_id | INT | NULL | Optional external ID — informational, not used for matching |
| treat_as | VARCHAR(20) | NULL | `daira` / `mudiriya` / `qism` / `ignore` (NULL = "undecided", treated as skip) |
| notes | TEXT | | |
| created_at | TIMESTAMPTZ | auto | |
| updated_at | TIMESTAMPTZ | auto | |

**Sync semantics:**
- `treat_as` set to one of the three Anjaz types → unit is imported with that type.
- `treat_as = 'ignore'` → unit is skipped deliberately.
- `treat_as = NULL` → unit is skipped and counted under `skipped_unknown_type` for admin review.

---

### 3.2 `users`

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | SERIAL | PK | |
| username | VARCHAR(150) | UNIQUE, NOT NULL | Login username |
| password | VARCHAR(255) | NOT NULL | Hashed |
| full_name | VARCHAR(200) | NOT NULL | |
| role | VARCHAR(30) | NOT NULL | `statistics_admin` / `planning_section` / `section_manager` / `viewer` |
| unit_id | INT | FK → organization_units, NULL | Linked organizational unit |
| is_active | BOOLEAN | DEFAULT TRUE | |
| created_by_id | INT | FK → users, NULL | Who created this user |
| created_at | TIMESTAMPTZ | auto | |
| updated_at | TIMESTAMPTZ | auto | |

**Role ↔ Unit Mapping:** (enforced in `User.clean()`; the "kind" of a qism is derived from the assignment tables, not a column)
- `statistics_admin` → `unit` is **optional**; scope is implicit (full system).
- `planning_section` → `unit` is **required** and must be a qism that has a row in `planning_assignments`. Managed scope = supervised units of that assignment.
- `section_manager` → `unit` is **required** and must be a qism that has a row in `supervised_units` (i.e. is supervised by some planning assignment).
- `viewer` → `unit` is **optional**; read-only scope is given by `view_scopes.viewable_units`.

---

### 3.3 `indicator_categories`

| Column | Type | Description |
|---|---|---|
| id | SERIAL PK | |
| name | VARCHAR(100) UNIQUE | e.g., إداري, مالي, فني |
| is_active | BOOLEAN | |

---

### 3.4 `indicators`

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | SERIAL | PK | |
| name | VARCHAR(300) | NOT NULL | Indicator name |
| description | TEXT | | Optional description |
| unit_type | VARCHAR(20) | NOT NULL | `number` / `percentage` / `text` / `hours` / `days` |
| unit_label | VARCHAR(50) | | e.g., جهاز, معاملة, تقرير |
| accumulation_type | VARCHAR(20) | NOT NULL | `sum` / `average` / `last_value` |
| category_id | INT | FK, NULL | |
| is_active | BOOLEAN | DEFAULT TRUE | |
| created_by_id | INT | FK → users | |
| created_at | TIMESTAMPTZ | | |
| updated_at | TIMESTAMPTZ | | |

**Validation Rules:**
- `unit_type = text` → `accumulation_type` must be `last_value`
- `unit_type = percentage` → values must be between 0 and 100

---

### 3.5 `form_templates`

| Column | Type | Description |
|---|---|---|
| id | SERIAL PK | |
| qism_id | FK → organization_units | Must be a qism with a `SupervisedUnit` row (i.e. an ordinary, supervised qism — not a planning qism) |
| version | INT NOT NULL | Auto-incremented per qism |
| status | VARCHAR(20) | `draft` / `pending_approval` / `approved` / `superseded` / `rejected` |
| effective_from_week | INT NULL | Week number this version takes effect |
| effective_from_year | INT NULL | Year this version takes effect |
| created_by_id | FK → users | Planning section user |
| approved_by_id | FK → users NULL | Statistics admin |
| rejected_by_id | FK → users NULL | |
| rejection_reason | TEXT | |
| notes | TEXT | |
| created_at | TIMESTAMPTZ | |
| approved_at | TIMESTAMPTZ NULL | |

**UNIQUE:**
- `(qism_id, version)` — version is sequential per qism.
- **`(qism_id, effective_from_year, effective_from_week) WHERE status = 'approved'`** — partial unique constraint (`uniq_approved_effective_per_qism`) ensures at most one approved template starts on a given week for a given qism.

**Status Flow:**
```
draft → pending_approval → approved
                        ↘ rejected → (must create new version via "new_version")
approved → superseded
   (set automatically when a new template is approved for the same qism with
    effective_from_(year, week) >= the existing one)
```

**Approval invariants:**
- `effective_from` cannot be in the past (`(year, week) >= current_(year, week)`).
- Approving template T_new for qism Q supersedes any approved template T_old for Q where `T_old.effective_from >= T_new.effective_from` — the older "currently active" template that starts BEFORE the new one remains `approved` and is picked by `get_active_template(qism, week)` until the new template's effective week arrives.

---

### 3.6 `form_template_items`

| Column | Type | Description |
|---|---|---|
| id | SERIAL PK | |
| form_template_id | FK | |
| indicator_id | FK | |
| is_mandatory | BOOLEAN DEFAULT FALSE | |
| display_order | INT DEFAULT 0 | |

**UNIQUE:** `(form_template_id, indicator_id)`

---

### 3.7 `targets`

| Column | Type | Description |
|---|---|---|
| id | SERIAL PK | |
| scope_unit_id | FK → organization_units, **NULL** | Daira / mudiriya / qism. NULL = institution-wide target |
| indicator_id | FK → indicators | |
| year | INT | |
| target_value | FLOAT | Must be > 0 |
| set_by_id | FK → users | Must be statistics_admin |
| notes | TEXT | |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

**UNIQUE:** `(scope_unit_id, indicator_id, year)` — note that PostgreSQL treats NULLs as distinct, so the model's `clean()` enforces uniqueness manually for institution-wide rows (`scope_unit IS NULL`).

**Validation Rules:**
- `scope_unit` may be a daira, mudiriya, or qism (or NULL for institution-wide).
- If `scope_unit` is a qism, it must be a supervised qism (has a `SupervisedUnit` row) — planning qisms cannot have targets.
- Text indicators cannot have a target.
- `last_value` indicators may only have qism-level targets (no hierarchical aggregation defined for `last_value`).

**Note:** Targets are optional. If no target exists for an indicator, the system displays the raw value only (no progress bar).

---

### 3.8 `weekly_periods`

| Column | Type | Description |
|---|---|---|
| id | SERIAL PK | |
| year | INT | |
| week_number | INT | 1–53 |
| start_date | DATE | |
| end_date | DATE | |
| deadline | TIMESTAMPTZ | Submission deadline |
| status | VARCHAR(10) | `open` / `closed` |
| created_by_id | FK → users | Must be statistics_admin |
| created_at | TIMESTAMPTZ | |

**UNIQUE:** `(year, week_number)`

---

### 3.9 `weekly_submissions`

| Column | Type | Description |
|---|---|---|
| id | SERIAL PK | |
| qism_id | FK | Must be a qism with a `SupervisedUnit` row (an ordinary, supervised qism) |
| weekly_period_id | FK | |
| form_template_id | FK | Snapshot of template version used |
| status | VARCHAR(20) | `draft` / `submitted` / `approved` / `returned` / `late` / `extended` / `returned_by_admin` |
| submitted_at | TIMESTAMPTZ NULL | |
| planning_approved_by_id | FK → users NULL | |
| planning_approved_at | TIMESTAMPTZ NULL | |
| admin_reviewed_at | TIMESTAMPTZ NULL | When admin (statistics) reviewed. NULL = pending admin review |
| admin_reviewed_by_id | FK → users NULL | Which admin employee reviewed |
| admin_review_action | VARCHAR(20) | `approved` / `edited` / `returned` (empty if not yet reviewed) |
| notes | TEXT | |

**UNIQUE:** `(qism_id, weekly_period_id)`

**Status Flow (three-step workflow):**
```
draft / returned / extended / returned_by_admin
   ↓ section_manager submits
submitted
   ↓ planning approves            ↘ planning rejects
approved (counts in statistics)     returned (back to section_manager)
   ↓ admin reviews (one-shot)
   ├─ approve  → stays approved (counted, admin_reviewed_at set)
   ├─ edit     → stays approved (admin modifies values, audit log records diff)
   └─ return   → returned_by_admin (excluded from statistics)
                    ↓ planning re-approves or returns
                  approved / returned
```

**Editability Logic:**
```python
def is_editable(self):
    # Exception: returned_by_admin is editable always (delay caused by admin review)
    if self.status == 'returned_by_admin':
        return True
    now = timezone.now()
    extension = QismExtension.objects.filter(
        qism=self.qism, weekly_period=self.weekly_period
    ).first()
    if extension and now <= extension.new_deadline:
        return True
    return (
        self.weekly_period.status == 'open'
        and now <= self.weekly_period.deadline
    )
```

**Admin Review Lock (one-shot):**
```python
# Once admin_reviewed_at is set, no other admin can act on this submission.
# Enforced in SubmissionAdminService._assert_reviewable() with select_for_update().
```

---

### 3.10 `submission_answers`

| Column | Type | Description |
|---|---|---|
| id | SERIAL PK | |
| submission_id | FK | |
| form_item_id | FK | |
| numeric_value | FLOAT NULL | For number/percentage/hours/days |
| text_value | TEXT | For text type |
| is_qualitative | BOOLEAN DEFAULT FALSE | Qualitative flag |
| qualitative_details | TEXT | Required if is_qualitative=True |
| qualitative_status | VARCHAR(25) | `none` / `pending_planning` / `pending_statistics` / `approved` / `rejected` |
| qualitative_approved_by_id | FK → users NULL | Statistics admin who approved |
| qualitative_approved_at | TIMESTAMPTZ NULL | |
| rejection_reason | TEXT | |

**UNIQUE:** `(submission_id, form_item_id)`

**Qualitative Status Flow:**
```
(user sets is_qualitative=True on submission)
→ pending_planning
→ planning approves → pending_statistics
→ statistics admin approves → approved
                           ↘ rejects → rejected (with reason)
```

---

### 3.11 `qism_extensions`

| Column | Type | Description |
|---|---|---|
| id | SERIAL PK | |
| qism_id | FK | |
| weekly_period_id | FK | |
| new_deadline | TIMESTAMPTZ | Must be after original deadline |
| reason | TEXT | |
| granted_by_id | FK → users | Must be statistics_admin |
| created_at | TIMESTAMPTZ | |

**UNIQUE:** `(qism_id, weekly_period_id)`

---

### 3.12 `notifications`

| Column | Type | Description |
|---|---|---|
| id | SERIAL PK | |
| recipient_id | FK → users | |
| notification_type | VARCHAR(30) | See types below |
| title | VARCHAR(200) | Arabic text |
| message | TEXT | Arabic text |
| is_read | BOOLEAN DEFAULT FALSE | |
| related_model | VARCHAR(50) | e.g., `WeeklySubmission` |
| related_id | INT NULL | PK of related record |
| created_at | TIMESTAMPTZ | |

**Notification Types:**
- `period_opened` — New week opened
- `submission_due` — Deadline approaching
- `submission_late` — Missed deadline
- `extension_granted` — Extension given
- `form_pending_approval` — Form template awaiting review
- `form_approved` / `form_rejected`
- `submission_received` — Planning section received a submission
- `submission_approved`
- `qualitative_pending` — Qualitative achievement awaiting approval
- `qualitative_approved` / `qualitative_rejected`

---

### 3.13 `audit_log` (app `audit`)

System-wide **append-only** audit trail. Every business action writes one row via `AuditService.log(...)`.

| Column | Type | Description |
|---|---|---|
| id | BIGSERIAL PK | |
| action_type | VARCHAR(50) | See action types below |
| actor_id | FK → users NULL | The user who performed the action (NULL = system / auto) |
| actor_role | VARCHAR(30) | Role of actor at time of action (frozen — not affected by later role changes) |
| target_model | VARCHAR(50) | `WeeklySubmission`, `FormTemplate`, `Target`, `SubmissionAnswer`, `QismExtension`, `WeeklyPeriod` |
| target_id | BIGINT NULL | PK of the target object |
| target_repr | VARCHAR(255) | `str(target)` snapshot at time of action |
| qism_id | FK → organization_units NULL | For fast filtering by qism scope |
| field_changes | JSONB NULL | List of `{field, old, new, ...}` dicts for edit actions |
| reason | TEXT | Mandatory for return/edit; empty for approve actions |
| metadata | JSONB NULL | Flexible context (previous_status, effective_from_week, etc.) |
| created_at | TIMESTAMPTZ DEFAULT now() | When the action occurred |

**Constraints:**
- **No UPDATE, no DELETE** from application layer (enforced via Django admin overrides and convention).
- All writes go through `apps.audit.services.AuditService` — never raw `AuditLog.objects.create()` from outside the service.

**Action Types (`ActionType` enum):**

| Domain | Action types |
|---|---|
| Submission | `submission_created`, `submission_saved`, `submission_submitted`, `submission_planning_approved`, `submission_planning_returned`, `submission_admin_approved`, `submission_admin_edited`, `submission_admin_returned` |
| Qualitative | `qualitative_planning_approved`, `qualitative_planning_rejected`, `qualitative_admin_approved`, `qualitative_admin_rejected` |
| Form templates | `template_created`, `template_updated`, `template_submitted`, `template_approved`, `template_rejected`, `template_new_version` |
| Targets | `target_created`, `target_updated`, `target_deleted` |
| Other | `extension_granted`, `period_opened`, `period_closed` |

**Indexes:**
- `(target_model, target_id)` — fast lookup of a specific entity's history
- `action_type`, `actor_id`, `(qism_id, -created_at)`, `-created_at`

**Visibility (`GET /api/submissions/{id}/audit-log/`):**
- `section_manager`: their own qism's submissions only
- `planning_section`: submissions within their scope (resolved by `_user_view_scope_qism_ids` — union of `SupervisedUnit` rows attached to the planner's `PlanningAssignment` plus any extra units from their `ViewScope`)
- `viewer`: read-only — submissions whose qism is in their `ViewScope.viewable_units` (also resolved via `_user_view_scope_qism_ids`)
- `statistics_admin`: full scope

---

## 4. Aggregation Logic

### 4.1 Periodic Aggregation (Weekly → Monthly → Annual)

Given an indicator with `accumulation_type`:

| Type | Aggregation |
|---|---|
| `sum` | `SUM(weekly_values)` for the period |
| `average` | `AVG(weekly_values)` for the period |
| `last_value` | Value from the latest week in the period |

### 4.2 Hierarchical Aggregation

For the same indicator at higher levels:
- **Qism level:** Direct weekly submission values
- **Mudiriya level:** Aggregate values of all qisms under the mudiriya (using `accumulation_type`)
- **Daira level:** Aggregate values of all mudiriyas + direct qisms under the daira
- **Institution level:** Aggregate all dairas + independent mudiriyas

**Important:** Only aggregate numeric indicators (`number`, `percentage`, `hours`, `days`). Text indicators are not aggregated.

### 4.3 Target Progress Calculation

```python
# For a given section and indicator:
cumulative_value = aggregate(weekly_submissions, start_of_year, today)
target_value = Target.objects.get(scope_unit=qism, indicator=indicator, year=year).target_value
progress_percentage = (cumulative_value / target_value) * 100
```

---

## 5. Indexes (Recommended)

```sql
-- Frequently filtered columns
CREATE INDEX idx_org_units_type ON organization_units(unit_type);
CREATE INDEX idx_org_units_parent ON organization_units(parent_id);
CREATE INDEX idx_submissions_period ON weekly_submissions(weekly_period_id);
CREATE INDEX idx_submissions_qism ON weekly_submissions(qism_id);
CREATE INDEX idx_submissions_status ON weekly_submissions(status);
CREATE INDEX idx_answers_submission ON submission_answers(submission_id);
CREATE INDEX idx_notifications_recipient ON notifications(recipient_id, is_read);
CREATE INDEX idx_targets_lookup ON targets(scope_unit_id, indicator_id, year);
```

---

## 6. Initial Data (Seed)

Run `python manage.py seed_initial_data` to create:
1. Default indicator categories: إداري, مالي, فني, أمني, رقابي
2. One statistics admin user (credentials from env vars)
3. Sample organization structure (optional, for development)
