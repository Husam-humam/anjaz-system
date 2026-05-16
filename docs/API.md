# API.md — REST API Endpoints

**Base URL:** `/api/`  
**Authentication:** Bearer JWT token in `Authorization` header  
**Response Language:** Arabic for all user-facing messages  
**Format:** JSON

---

## Permissions Matrix

| Endpoint Group | statistics_admin | planning_section | section_manager | viewer |
|---|:---:|:---:|:---:|:---:|
| Auth | ✅ | ✅ | ✅ | ✅ |
| Organization | ✅ CRUD + Sync | 👁 Read | 👁 Read (own) | 👁 Read (ViewScope) |
| Planning Assignments | ✅ CRUD | ❌ | ❌ | ❌ |
| View Scopes | ✅ CRUD | ❌ | ❌ | ❌ |
| Users | ✅ CRUD | ❌ | ❌ | ❌ |
| Indicators | ✅ CRUD | 👁 Read | 👁 Read | 👁 Read |
| Form Templates | ✅ Approve | ✅ CRUD + Approve (scope) | 👁 Read (own) | 👁 Read (ViewScope) |
| Targets | ✅ CRUD | 👁 Read | 👁 Read (own) | 👁 Read (ViewScope) |
| Weekly Periods | ✅ CRUD | 👁 Read | 👁 Read | 👁 Read |
| Submissions | ✅ Admin Review (all) | ✅ Approve (scope) | ✅ CRUD (own) | 👁 Read (ViewScope) |
| Admin Review (`admin-*`) | ✅ | ❌ | ❌ | ❌ |
| Audit Log | ✅ All | 👁 Read (scope) | 👁 Read (own) | 👁 Read (ViewScope) |
| Reports | ✅ All | ✅ Own directorate | ✅ Own section | 👁 (ViewScope) |
| Notifications | ✅ | ✅ | ✅ | ✅ |

**ملاحظة الأدوار (Phase F+):**
- مفهوم `qism_role` أُلغي. التمييز الآن يأتي من **التخصيصات الصريحة**:
  - `PlanningAssignment` يُعرّف أنّ وحدة تعمل كقسم تخطيط.
  - `SupervisedUnit` يربط قسماً عاديّاً بقسم تخطيط معيّن (OneToOne).
  - `ViewScope` يمنح المستخدم رؤية وحدات إضافيّة (لا تحكّم).
- دور **`viewer`** = قراءة فقط — يُحظر أي إجراء كتابة عبر `IsNotViewer` permission.
- نطاق رؤية `planning_section` = الأقسام في `assignment.supervised_units` ∪ `ViewScope.viewable_units` (إن وُجد).
- نطاق رؤية `viewer` = `ViewScope.viewable_units` فقط.

---

## 1. Authentication

### POST `/api/auth/login/`
Login and receive tokens.

**Request:**
```json
{ "username": "admin", "password": "password123" }
```

**Response 200:**
```json
{
  "access": "eyJ...",
  "refresh": "eyJ...",
  "user": {
    "id": 1,
    "username": "admin",
    "full_name": "أحمد محمد",
    "role": "statistics_admin",
    "unit": { "id": 5, "name": "قسم الإحصاء", "code": "STAT" }
  }
}
```

### POST `/api/auth/token/refresh/`
**Request:** `{ "refresh": "eyJ..." }`  
**Response:** `{ "access": "eyJ..." }`

### POST `/api/auth/logout/`
Blacklists the refresh token.  
**Request:** `{ "refresh": "eyJ..." }`

### GET `/api/auth/me/`
Returns current user profile.

---

## 2. Organization

### GET `/api/organization/tree/`
Returns the full organization tree.  
**Permission:** All roles (scoped by role)

**Response:**
```json
[
  {
    "id": 1,
    "name": "دائرة الشؤون الإدارية",
    "code": "ADMIN",
    "unit_type": "daira",
    "qism_role": "regular",
    "children": [
      {
        "id": 2,
        "name": "مديرية الموارد البشرية",
        "unit_type": "mudiriya",
        "children": [
          { "id": 3, "name": "قسم التوظيف", "unit_type": "qism", ... }
        ]
      }
    ]
  }
]
```

### GET `/api/organization/units/`
Flat list with filters.  
**Query params:** `unit_type`, `parent_id`, `is_active`, `search`

> ملاحظة: حقل `qism_role` أُلغي. التمييز بين «قسم تخطيط» / «قسم مُشرَف عليه» / «غير مُسنَد» يأتي الآن من الحقول المُشتقّة `is_planning` و `is_supervised` في الاستجابة.

### POST `/api/organization/units/`
Create a unit. **Permission:** `statistics_admin` only.  
> الوحدات تُدار عادةً عبر المزامنة من النظام الخارجي. الإنشاء اليدوي محصور بالحالات الاستثنائيّة.

```json
{
  "name": "قسم التوظيف",
  "code": "EMP",
  "unit_type": "qism",
  "parent": 2
}
```

### GET `/api/organization/units/{id}/`
### PATCH `/api/organization/units/{id}/`
### DELETE `/api/organization/units/{id}/`
Soft delete (sets `is_active=False`). **Permission:** `statistics_admin` only.

### POST `/api/organization/units/sync/`
مزامنة الهيكل التنظيمي من النظام الخارجي. **Permission:** `statistics_admin` only.  
يُستدعى تلقائياً عند فتح صفحة «الهيكل التنظيمي» في الـ frontend + يدوياً عبر زر «مزامنة الآن».

**Query params:**  
- `dry_run=1` — يُحاكي العمليّة ويُرجع التقرير دون أي كتابة.

**Response (200):**
```json
{
  "created": 0,
  "updated": 5,
  "deactivated": 0,
  "skipped_unknown_type": 0,
  "errors": [],
  "summary": "تمّت إضافة 0 / تحديث 5 / تعطيل 0",
  "started_at": "2026-05-16T08:00:00Z",
  "finished_at": "2026-05-16T08:00:03Z",
  "dry_run": false
}
```

**Response (502):**
```json
{ "detail": "فشل الاتصال بالنظام الخارجي: ..." }
```

---

## 2.b Planning Assignments — تخصيصات أقسام التخطيط

**Permission:** `statistics_admin` only.

### GET `/api/organization/planning-assignments/`
يُرجع كل التخصيصات مع الأقسام المُشرَف عليها.

### POST `/api/organization/planning-assignments/`
إنشاء تخصيص جديد.

```json
{
  "planning_unit": 12,
  "context_parent": 3,
  "notes": ""
}
```

### PATCH `/api/organization/planning-assignments/{id}/`
تعديل (لا يسمح بتغيير `planning_unit` — إنشاء تخصيص جديد بدلاً منه).

### DELETE `/api/organization/planning-assignments/{id}/`
حذف التخصيص. يلغي دور التخطيط لذلك القسم.

### POST `/api/organization/planning-assignments/{id}/supervised-units/`
إضافة قسم تحت إشراف التخصيص.

```json
{ "unit": 25 }
```

**Responses:**
- `201`: نجح الربط — `{ id, unit, unit_name, unit_code }`
- `409`: الوحدة مُشرَف عليها بالفعل من قِبَل تخصيص آخر

### DELETE `/api/organization/planning-assignments/{id}/supervised-units/{unit_id}/`
إزالة قسم من إشراف التخصيص.

---

## 2.c View Scopes — نطاقات الاطّلاع

**Permission:** `statistics_admin` only.  
تمنح المستخدم (viewer أو planning_section موسَّع) رؤية وحدات إضافيّة دون التحكّم بها.

### GET `/api/organization/view-scopes/`
**Query params:** `user`

### POST `/api/organization/view-scopes/`
```json
{
  "user": 8,
  "viewable_units": [10, 12, 15],
  "notes": ""
}
```

### PATCH `/api/organization/view-scopes/{id}/`
تعديل قائمة `viewable_units`.

### DELETE `/api/organization/view-scopes/{id}/`

---

## 3. Users

**Permission:** `statistics_admin` only for all operations.

### GET `/api/users/`
**Query params:** `role`, `unit_id`, `is_active`, `search`

### POST `/api/users/`
```json
{
  "username": "user1",
  "password": "SecurePass123",
  "full_name": "محمد علي",
  "role": "section_manager",
  "unit": 3
}
```

### GET `/api/users/{id}/`
### PATCH `/api/users/{id}/`
### POST `/api/users/{id}/reset_password/`
```json
{ "new_password": "NewPass456" }
```

---

## 4. Indicators

### GET `/api/indicators/categories/`
### POST `/api/indicators/categories/`  **[statistics_admin]**
### PATCH `/api/indicators/categories/{id}/`  **[statistics_admin]**

### GET `/api/indicators/`
**Query params:** `category_id`, `unit_type`, `is_active`, `search`

### POST `/api/indicators/`  **[statistics_admin]**
```json
{
  "name": "عدد الحاسبات المُصلَّحة",
  "unit_type": "number",
  "unit_label": "جهاز",
  "accumulation_type": "sum",
  "category": 3
}
```

### GET `/api/indicators/{id}/`
### PATCH `/api/indicators/{id}/`  **[statistics_admin]**

---

## 5. Form Templates

### GET `/api/forms/templates/`
**Query params:** `qism_id`, `status`, `version`  
**Scoped:** planning_section sees only their directorate's sections; section_manager sees own.

### POST `/api/forms/templates/`  **[planning_section]**
```json
{
  "qism": 3,
  "items": [
    { "indicator": 5, "is_mandatory": true, "display_order": 1 },
    { "indicator": 8, "is_mandatory": false, "display_order": 2 }
  ],
  "notes": ""
}
```

### GET `/api/forms/templates/{id}/`
### PATCH `/api/forms/templates/{id}/`  **[planning_section]**
Only allowed when status is `draft`.

### POST `/api/forms/templates/{id}/submit/`  **[planning_section]**
Transitions `draft → pending_approval`.

### POST `/api/forms/templates/{id}/approve/`  **[statistics_admin]**
```json
{ "effective_from_week": 15, "effective_from_year": 2025 }
```
Transitions `pending_approval → approved` and supersedes previous version.

### POST `/api/forms/templates/{id}/reject/`  **[statistics_admin]**
```json
{ "rejection_reason": "يرجى مراجعة البنود..." }
```

### GET `/api/forms/templates/active/?qism_id={id}`
Returns the currently active template for a qism.

---

## 6. Targets

### GET `/api/targets/`
**Query params:** `qism_id`, `indicator_id`, `year`  
**Scoped by role.**

### POST `/api/targets/`  **[statistics_admin]**
```json
{
  "qism": 3,
  "indicator": 5,
  "year": 2025,
  "target_value": 240,
  "notes": ""
}
```

### PATCH `/api/targets/{id}/`  **[statistics_admin]**
### DELETE `/api/targets/{id}/`  **[statistics_admin]**

---

## 7. Weekly Periods

### GET `/api/periods/`
**Query params:** `year`, `status`

### POST `/api/periods/`  **[statistics_admin]**
```json
{
  "year": 2025,
  "week_number": 15,
  "start_date": "2025-04-07",
  "end_date": "2025-04-13",
  "deadline": "2025-04-14T23:59:00Z"
}
```

### GET `/api/periods/{id}/`
### POST `/api/periods/{id}/close/`  **[statistics_admin]**
Closes the period. Auto-marks non-submitted sections as `late`.

### GET `/api/periods/{id}/compliance/`  **[statistics_admin, planning_section]**
Returns submission status for every section in scope.

```json
{
  "total_sections": 20,
  "submitted": 15,
  "late": 3,
  "draft": 2,
  "sections": [
    { "qism_id": 3, "qism_name": "قسم التوظيف", "status": "approved" },
    ...
  ]
}
```

### POST `/api/periods/{id}/extensions/`  **[statistics_admin]**
```json
{
  "qism": 3,
  "new_deadline": "2025-04-16T23:59:00Z",
  "reason": "ظروف طارئة"
}
```

---

## 8. Submissions

### GET `/api/submissions/`
**Query params:** `weekly_period_id`, `qism_id`, `status`  
**Scoped:** statistics_admin = all; planning_section = own directorate; section_manager = own section.

### POST `/api/submissions/`  **[section_manager]**
Creates or retrieves the submission for the current week (idempotent).
```json
{ "weekly_period": 10 }
```

### GET `/api/submissions/{id}/`
### PATCH `/api/submissions/{id}/`  **[section_manager]**
Save answers (partial update allowed for drafts).

```json
{
  "answers": [
    {
      "form_item": 15,
      "numeric_value": 5,
      "is_qualitative": true,
      "qualitative_details": "تقرير السلامة المهنية السنوي..."
    },
    {
      "form_item": 16,
      "numeric_value": 120,
      "is_qualitative": false
    }
  ],
  "notes": ""
}
```

### POST `/api/submissions/{id}/submit/`  **[section_manager]**
Transitions `draft / returned / extended / returned_by_admin → submitted`. Validates mandatory fields.
Note: `returned_by_admin` is accepted even after the weekly deadline has passed.

### POST `/api/submissions/{id}/approve/`  **[planning_section]**
Transitions `submitted | returned_by_admin → approved`.
Resets `admin_reviewed_*` fields so the admin must re-review the (possibly modified) submission.
Also transitions qualitative answers to `pending_statistics`.

### POST `/api/submissions/{id}/reject/`  **[planning_section]**
Transitions `submitted | returned_by_admin → returned`.
Body: `{ "reason": "سبب الإرجاع" }` (required).

### POST `/api/submissions/{id}/admin-approve/`  **[statistics_admin]**
Admin (statistics) reviews and approves the submission. No body required, no reason needed.
Stays as `approved` — only marks `admin_reviewed_at`, `admin_reviewed_by`, `admin_review_action='approved'`.
Fails with 400 if `admin_reviewed_at` is already set (one-shot review).

### POST `/api/submissions/{id}/admin-edit/`  **[statistics_admin]**
Admin edits answer values with a mandatory reason. Audit log records old→new per field.
```json
{
  "reason": "تصحيح خطأ إدخال — الرقم 250 وليس 100",
  "answer_edits": [
    {"answer_id": 42, "numeric_value": 250},
    {"answer_id": 43, "text_value": "نص مُحدَّث"}
  ]
}
```
Returns 400 if reason is empty, if no actual values changed, or if already reviewed.

### POST `/api/submissions/{id}/admin-return/`  **[statistics_admin]**
Admin returns the submission to planning with a mandatory reason. Status transitions `approved → returned_by_admin` (excluded from statistics until re-approved).
```json
{ "reason": "أرقام تحتاج إعادة تحقّق من المصدر" }
```

### GET `/api/submissions/{id}/audit-log/`  **[section_manager(own), planning_section(scope), statistics_admin]**
Returns the full timeline of actions for this submission.
```json
{
  "results": [
    {
      "id": 17,
      "action_type": "submission_admin_edited",
      "action_label": "تعديل منجز من الإحصاء",
      "actor_id": 5,
      "actor_name": "أحمد علي",
      "actor_role": "statistics_admin",
      "field_changes": [
        {
          "field": "numeric_value",
          "answer_id": 42,
          "indicator_id": 7,
          "indicator_name": "عدد الزيارات",
          "old": "100",
          "new": "250"
        }
      ],
      "reason": "تصحيح خطأ إدخال",
      "metadata": null,
      "created_at": "2026-05-14T10:30:00Z"
    }
  ]
}
```

### GET `/api/submissions/pending-admin-review/`  **[statistics_admin]**
Paginated list of submissions awaiting admin review (approved by planning, not yet reviewed by admin).
**Query params:**
- `reviewed`: `"true"` (only reviewed) / `"false"` (only pending) / omit (all)
- `year`, `week` — period filters
- `daira_id`, `mudiriya_id`, `qism_id` — organizational filters (cascading)
- `page`, `page_size` — pagination

Used by the `/achievements` admin page. Also used (with `page_size=1`) for the sidebar badge counter.

### GET `/api/submissions/{id}/history/`  **[section_manager, planning_section, statistics_admin]**
Returns past submissions for a section.

---

## 9. Qualitative Achievements

### GET `/api/qualitative/`
List qualitative answers pending or approved.  
**Query params:** `qualitative_status`, `qism_id`, `weekly_period_id`

### POST `/api/qualitative/{answer_id}/approve/`  **[statistics_admin]**
Final approval. Transitions `pending_statistics → approved`.

### POST `/api/qualitative/{answer_id}/reject/`  **[statistics_admin]**
```json
{ "rejection_reason": "يرجى توضيح الإنجاز بشكل أدق" }
```

---

## 10. Reports

### GET `/api/reports/summary/`
Dashboard summary statistics.  
**Query params:** `unit_id` (optional, scoped), `year`, `week_number`

**Response:**
```json
{
  "period": { "year": 2025, "week_number": 15 },
  "compliance_rate": 87.5,
  "total_submissions": 20,
  "approved_submissions": 16,
  "pending_qualitative": 3,
  "target_progress": [
    {
      "indicator_name": "عدد المعاملات المنجزة",
      "cumulative_value": 1240,
      "target_value": 2400,
      "progress_percentage": 51.7
    }
  ]
}
```

### GET `/api/reports/periodic/`
Aggregated report for a period.  
**Query params:** `period_type` (weekly/monthly/quarterly/semi_annual/annual), `year`, `period_number`, `unit_id`

### GET `/api/reports/export/`
Download report as file.  
**Query params:** `format` (pdf/excel), `period_type`, `year`, `period_number`, `unit_id`  
**Response:** File download (`Content-Disposition: attachment`)

### GET `/api/reports/compliance/`
Submission compliance across periods.  
**Query params:** `year`, `unit_id`

### GET `/api/reports/qualitative/`
All approved qualitative achievements.  
**Query params:** `year`, `unit_id`, `from_week`, `to_week`

---

## 11. Notifications

### GET `/api/notifications/`
**Query params:** `is_read`, `notification_type`  
**Response:** Paginated list of user's notifications.

### POST `/api/notifications/{id}/read/`
Marks a notification as read.

### POST `/api/notifications/read_all/`
Marks all notifications as read.

### GET `/api/notifications/unread_count/`
```json
{ "count": 5 }
```

---

## 12. Error Response Format

All errors follow this structure:

```json
{
  "error": true,
  "message": "رسالة خطأ واضحة للمستخدم",
  "code": "VALIDATION_ERROR",
  "details": {
    "field_name": ["رسالة خطأ الحقل"]
  }
}
```

**Common HTTP Status Codes:**
- `200` — Success
- `201` — Created
- `400` — Validation error
- `401` — Not authenticated
- `403` — Permission denied (رسالة: "ليس لديك صلاحية للقيام بهذا الإجراء")
- `404` — Not found (رسالة: "العنصر المطلوب غير موجود")
- `409` — Conflict (e.g., duplicate submission)
- `422` — Business rule violation

---

## 13. Pagination

All list endpoints are paginated:

```json
{
  "count": 150,
  "next": "/api/submissions/?page=2",
  "previous": null,
  "results": [...]
}
```

Default page size: 20. Configurable via `?page_size=50` (max 100).

---

## 14. WebSocket Endpoint

**URL:** `ws://host/ws/notifications/`  
**Auth:** Pass token as query param: `?token=eyJ...`

**Incoming message format:**
```json
{
  "type": "notification",
  "data": {
    "id": 42,
    "notification_type": "submission_approved",
    "title": "تم اعتماد المنجز الأسبوعي",
    "message": "تم اعتماد منجز الأسبوع 15 بواسطة قسم التخطيط",
    "is_read": false,
    "created_at": "2025-04-14T10:30:00Z"
  }
}
```
