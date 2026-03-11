# PRD — Product Requirements Document
# Anjaz System: Institutional Achievement Tracking System

**Version:** 1.0  
**Language Constraint:** UI must be fully in Arabic (RTL layout)

---

## 1. Problem Statement

A government institution's planning and follow-up directorate manually collects achievement reports from all departments weekly. The current process suffers from:

- **Redundant data entry:** Sections re-enter the same data weekly, monthly, quarterly, and annually instead of building on cumulative weekly data.
- **Inconsistent templates:** Each section uses its own report format, making cross-section comparison impossible.
- **Shared achievement conflicts:** Tasks involving multiple sections get counted multiple times with no clear ownership boundary.
- **No automated aggregation:** Monthly/quarterly/annual reports are manually compiled.
- **No compliance tracking:** No automated way to identify sections that missed their submission deadlines.

---

## 2. Solution

A web-based system with three user tiers that digitizes the entire weekly reporting cycle:

1. **Statistics Admin** — Builds the indicators bank, manages users, controls the weekly cycle, sets targets, approves everything.
2. **Planning Sections** — Build section-specific forms from the indicators bank, approve weekly submissions from their directorate's sections.
3. **Section Managers** — Fill their weekly achievement form; optionally flag notable achievements as "qualitative."

The system auto-aggregates weekly data into all periodic reports, eliminating redundant data entry entirely.

---

## 3. User Stories

### Statistics Admin (مدير قسم الإحصاء)

| ID | Story |
|---|---|
| SA-01 | As a statistics admin, I can create and manage indicator categories (administrative, financial, technical, etc.) |
| SA-02 | As a statistics admin, I can add indicators to the bank with name, unit type, and accumulation method |
| SA-03 | As a statistics admin, I can create user accounts and assign them to their organizational unit |
| SA-04 | As a statistics admin, I can open a new weekly period and set its submission deadline |
| SA-05 | As a statistics admin, I can close a weekly period manually |
| SA-06 | As a statistics admin, I can grant a specific section an extended deadline for a given week |
| SA-07 | As a statistics admin, I can review and approve/reject form templates submitted by planning sections |
| SA-08 | As a statistics admin, I can set annual targets for specific indicators for specific sections |
| SA-09 | As a statistics admin, I can approve or reject qualitative achievements (second and final approval step) |
| SA-10 | As a statistics admin, I can view a full institutional dashboard showing all sections' compliance and progress |
| SA-11 | As a statistics admin, I can export any report as PDF or Excel |
| SA-12 | As a statistics admin, I can build and manage the organizational hierarchy (dairas, mudiriyas, qisms) |

### Planning Section (قسم التخطيط)

| ID | Story |
|---|---|
| PS-01 | As a planning section user, I can create a form template for each section under my directorate by selecting indicators from the bank |
| PS-02 | As a planning section user, I can set indicator order and mark some as mandatory in the form |
| PS-03 | As a planning section user, I can submit a form template for approval to the statistics admin |
| PS-04 | As a planning section user, I can request a form template modification (creates a new version pending approval) |
| PS-05 | As a planning section user, I can view all pending weekly submissions from my directorate's sections |
| PS-06 | As a planning section user, I can approve a section's weekly submission |
| PS-07 | As a planning section user, I can approve qualitative achievements (first approval step) |
| PS-08 | As a planning section user, I can view analytics and reports for all sections under my directorate |
| PS-09 | As a planning section user, I can see which sections have not submitted their weekly report |

### Section Manager (مدير قسم)

| ID | Story |
|---|---|
| SM-01 | As a section manager, I can fill my section's weekly achievement form |
| SM-02 | As a section manager, I can save the form as a draft and complete it later |
| SM-03 | As a section manager, I can flag any answered indicator as a qualitative achievement and add details |
| SM-04 | As a section manager, I can submit the form before the deadline |
| SM-05 | As a section manager, I can view my section's previous submissions (forms and charts) |
| SM-06 | As a section manager, I can track my section's progress toward annual targets |
| SM-07 | As a section manager, I receive in-app notifications for deadlines and approvals |

---

## 4. Functional Requirements

### 4.1 Organizational Structure Management
- Support a variable-depth hierarchy: Daira → Mudiriya → Qism, Daira → Qism, or Mudiriya → Qism (independent).
- Each unit has a unique code and name.
- Units can be deactivated (soft delete).
- Three special qism roles: `regular` (submits data), `planning` (reviews), `statistics` (admin).

### 4.2 Indicators Bank
- Indicators have: name, description, unit type (number/percentage/text/hours/days), unit label, accumulation type (sum/average/last_value), and category.
- Text-type indicators cannot have numeric targets and must use `last_value` accumulation.
- Indicators can be deactivated; deactivated indicators remain in historical forms.

### 4.3 Form Template Management
- Planning sections create templates by selecting indicators from the bank.
- Each indicator in the form can be marked mandatory or optional.
- Display order is configurable.
- Templates go through: `draft → pending_approval → approved`.
- Modifications create a new version; the previous approved version gets status `superseded`.
- New versions take effect from the specified week onward.
- Historical submissions always reference the template version used at submission time.

### 4.4 Weekly Cycle
- Statistics admin opens a weekly period (year, week number, start/end dates, deadline).
- Once opened, all active sections with approved templates receive a notification.
- Sections can submit, save drafts, and resubmit until the deadline.
- Late status is automatically assigned after the deadline to sections that have not submitted.
- Statistics admin can grant per-section extensions with a new deadline.
- Statistics admin closes the period manually.

### 4.5 Achievement Submission
- Each section fills one submission per week based on their current approved template.
- Each form item (indicator) accepts: numeric value, text value, or both depending on indicator type.
- Any answered item can be flagged as a qualitative achievement with mandatory detail text.
- Qualitative achievements follow a two-step approval process.
- The planning section approves the full weekly submission (all regular data).
- Qualitative achievements require additional approval from statistics admin.

### 4.6 Targets & Progress Tracking
- Statistics admin sets annual targets per section per indicator.
- Target presence is optional — its absence does not affect regular reporting.
- When a target exists, the system shows a cumulative progress bar and percentage.
- Progress calculation uses the indicator's `accumulation_type`.
- Targets are set at the section level; aggregation to directorate/daira levels is calculated.

### 4.7 Reports & Analytics
- **Weekly Report:** All sections' submissions for a given week.
- **Monthly Report:** Aggregated from 4-5 weeks.
- **Quarterly / Semi-Annual / Annual Reports:** Auto-aggregated from approved weekly data.
- **Compliance Report:** Which sections submitted on time, late, or not at all.
- **Progress Report:** Progress toward targets per section, directorate, daira, and institution.
- **Qualitative Achievements Report:** All approved qualitative achievements with filters.
- Export formats: PDF and Excel.

### 4.8 Notifications
- In-app only (no email).
- Triggered automatically on: week opened, deadline approaching (configurable days before), deadline passed without submission, submission approved, form approved/rejected, qualitative achievement approved/rejected, extension granted.

---

## 5. Non-Functional Requirements

| Category | Requirement |
|---|---|
| **Language** | Full RTL Arabic UI; code and APIs in English |
| **Performance** | Page load < 2s; report generation < 5s |
| **Security** | JWT authentication; role-based access control; no cross-role data leakage |
| **Data Integrity** | Historical submissions immutable after approval; template versioning preserved |
| **Usability** | Simple forms; mobile-responsive; clear status indicators |
| **Auditability** | All approval actions log user + timestamp |

---

## 6. Out of Scope (v1.0)

- Email notifications
- Mobile native application
- Multi-language support beyond Arabic
- Integration with external HR or ERP systems
- Automated week creation (manual only in v1.0)
