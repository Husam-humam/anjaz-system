# API.md — REST API Endpoints

**Base URL:** `/api/`  
**Authentication:** Bearer JWT token in `Authorization` header  
**Response Language:** Arabic for all user-facing messages  
**Format:** JSON

---

## Permissions Matrix

| Endpoint Group | statistics_admin | planning_section | section_manager |
|---|:---:|:---:|:---:|
| Auth | ✅ | ✅ | ✅ |
| Organization | ✅ CRUD | 👁 Read | 👁 Read (own) |
| Users | ✅ CRUD | ❌ | ❌ |
| Indicators | ✅ CRUD | 👁 Read | 👁 Read |
| Form Templates | ✅ Approve | ✅ CRUD | 👁 Read (own) |
| Targets | ✅ CRUD | 👁 Read | 👁 Read (own) |
| Weekly Periods | ✅ CRUD | 👁 Read | 👁 Read |
| Submissions | 👁 Read All | ✅ Approve (own) | ✅ CRUD (own) |
| Reports | ✅ All | ✅ Own directorate | ✅ Own section |
| Notifications | ✅ | ✅ | ✅ |

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
**Query params:** `unit_type`, `qism_role`, `parent_id`, `is_active`, `search`

### POST `/api/organization/units/`
Create a unit. **Permission:** `statistics_admin` only.

**Request:**
```json
{
  "name": "قسم التوظيف",
  "code": "EMP",
  "unit_type": "qism",
  "qism_role": "regular",
  "parent": 2
}
```

### GET `/api/organization/units/{id}/`
### PATCH `/api/organization/units/{id}/`
### DELETE `/api/organization/units/{id}/`
Soft delete (sets `is_active=False`). **Permission:** `statistics_admin` only.

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
Transitions `draft → submitted`. Validates mandatory fields.

### POST `/api/submissions/{id}/approve/`  **[planning_section]**
Transitions `submitted → approved`.  
Also transitions qualitative answers to `pending_statistics`.

### GET `/api/submissions/{id}/history/`  **[section_manager, planning_section]**
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
