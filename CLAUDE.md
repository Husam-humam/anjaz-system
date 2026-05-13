# CLAUDE.md — Anjaz System: Institutional Achievement Tracking System

## ⚠️ CRITICAL LANGUAGE CONSTRAINTS

1. **Always respond to the user in Arabic (العربية).**
2. **All UI text, labels, buttons, messages, and frontend content must be in Arabic.**
3. **Code, variable names, and technical identifiers remain in English.**
4. **Comments in code may be in Arabic for better clarity.**
5. **Database field names and API keys remain in English.**

---

## Project Overview

**Anjaz System** is an institutional achievement tracking platform built for a government organization. It digitizes the weekly reporting workflow where departments submit their accomplishments, planning sections review and approve them, and the Statistics Department aggregates data into periodic reports (weekly, monthly, quarterly, semi-annual, annual).

**Core Documentation:**
- `docs/PRD.md` — Full product requirements
- `docs/ARCHITECTURE.md` — Technical architecture & stack decisions
- `docs/DATABASE.md` — Complete database schema & business rules
- `docs/API.md` — All API endpoints with permissions
- `docs/FRONTEND.md` — UI structure, pages, and component map
- `docs/TESTING.md` — Testing strategy & test cases

**Always read the relevant doc before starting any task.**

---

## Tech Stack

### Backend
- **Python 3.12+** with **Django 5.x**
- **Django REST Framework (DRF)** for APIs
- **django-mptt** for hierarchical organization tree
- **PostgreSQL 16** as the database
- **Redis** for WebSocket channels
- **Django Channels** for real-time notifications
- **ReportLab** for PDF export
- **OpenPyXL** for Excel export
- **Simple JWT** for authentication

### Frontend
- **Next.js 15** (App Router)
- **TypeScript**
- **Tailwind CSS**
- **shadcn/ui** components
- **Recharts** for charts and statistics
- **React Query (TanStack Query)** for server state
- **Zustand** for client state
- **React Hook Form + Zod** for form validation

### Infrastructure
- **Docker + Docker Compose** for development environment
- **Nginx** as reverse proxy

---

## Project Structure

```
anjaz_system/
├── CLAUDE.md                    # ← You are here
├── docs/
│   ├── PRD.md
│   ├── ARCHITECTURE.md
│   ├── DATABASE.md
│   ├── API.md
│   ├── FRONTEND.md
│   └── TESTING.md
├── backend/
│   ├── config/                  # Django settings
│   │   ├── settings/
│   │   │   ├── base.py
│   │   │   ├── development.py
│   │   │   └── production.py
│   │   ├── urls.py
│   │   ├── wsgi.py
│   │   └── asgi.py
│   ├── apps/
│   │   ├── organization/        # Org tree (MPTT)
│   │   ├── accounts/            # Users & auth
│   │   ├── indicators/          # Indicators bank
│   │   ├── forms/               # Form templates
│   │   ├── targets/             # Annual targets
│   │   ├── submissions/         # Weekly submissions + admin review (Step 3)
│   │   ├── reports/             # Report generation
│   │   ├── notifications/       # In-app notifications + WebSocket
│   │   └── audit/               # System-wide audit log (append-only)
│   ├── requirements/
│   │   ├── base.txt
│   │   └── development.txt
│   └── manage.py
├── frontend/
│   ├── src/
│   │   ├── app/                 # Next.js App Router
│   │   ├── components/          # Reusable components
│   │   ├── lib/                 # Utilities & API client
│   │   ├── hooks/               # Custom React hooks
│   │   ├── stores/              # Zustand stores
│   │   └── types/               # TypeScript types
│   ├── public/
│   └── package.json
├── docker-compose.yml
└── .env.example
```

---

## Development Workflow

### 1. Setup
```bash
cp .env.example .env
docker-compose up -d
docker-compose exec backend python manage.py migrate
docker-compose exec backend python manage.py createsuperuser
docker-compose exec backend python manage.py seed_initial_data
```

### 2. Running Tests
```bash
# Backend
docker-compose exec backend pytest --cov

# Frontend
cd frontend && npm run test
```

### 3. Code Quality Standards

**Backend:**
- Follow Django best practices and Clean Code principles
- Use class-based views with DRF ViewSets
- All business logic in service classes (`services.py`), not in views
- All database queries in querysets (`querysets.py`)
- Validation in model `clean()` methods AND serializer `validate_*` methods
- Every model must have `__str__` method
- Every API endpoint must have permission class

**Frontend:**
- Use TypeScript strictly (no `any` types)
- Components in `PascalCase`, hooks in `camelCase` with `use` prefix
- All API calls through the centralized API client in `lib/api/`
- All Arabic text in translation files (`locales/ar/`)
- RTL layout required for all pages (Arabic UI)

---

## User Roles Summary

| Role | Arabic Name | Scope |
|---|---|---|
| `statistics_admin` | مدير قسم الإحصاء | Full system access |
| `planning_section` | قسم التخطيط | Own directorate only |
| `section_manager` | مدير قسم | Own section only |

---

## Key Business Rules (Always Enforce)

1. A `WeeklySubmission` is **editable** only if: the week is open AND deadline not passed, OR a valid `QismExtension` exists.
   - **Exception**: status `returned_by_admin` is editable always (even after deadline) because the delay was caused by admin review, not the section.
2. A `FormTemplate` becomes active on the `effective_from_week` — **never retroactively**. Approval is rejected if `(year, week) < (current_year, current_week)`.
3. Historical submissions are **always linked to the FormTemplate version used at submission time**.
4. Qualitative achievements require **two-step approval**: planning section → statistics admin.
5. **Three-step submission workflow for ALL submissions** (quantitative + qualitative):
   1. `section_manager` submits → status `submitted`.
   2. `planning_section` approves → status `approved` → **counts in statistics immediately**.
   3. `statistics_admin` reviews — one of three actions (one-shot, locked after):
      - **Approve** (no reason) — just confirms.
      - **Edit** (mandatory reason) — modify answer values, audit log records old→new for each field.
      - **Return** (mandatory reason) — status moves to `returned_by_admin`, **excluded from statistics** until planning re-approves.
6. Targets are **optional** — their absence must not break any calculation.
7. Report aggregation must respect `accumulation_type`: `sum`, `average`, or `last_value`. `last_value` queries must be **chronologically ordered** by `(year, week_number)`.
8. The organization tree allows: Daira→Mudiriya→Qism, Daira→Qism, Mudiriya→Qism (independent).
9. A `Qism` can never be a parent of another unit.
10. Authorization scope:
    - Only `statistics_admin` can create users, open/close weeks, set targets, grant extensions.
    - Template approval is allowed for both `statistics_admin` (full scope) and `planning_section` (within their `_planning_section_scope_qism_ids` scope).
    - Admin review (`admin-approve` / `admin-edit` / `admin-return`) is `statistics_admin` only.
    - Once one `statistics_admin` employee reviews a submission, **no other admin can review the same submission** — `admin_reviewed_at IS NULL` check + `select_for_update()`.
11. Notifications must be created automatically on every status change event. Form template events must go through `NotificationService` (not raw `Notification.objects.create`) so they propagate over WebSocket.
12. Indicator `unit_type` and `accumulation_type` are **locked once `SubmissionAnswer` rows exist** for them — changing them would break historical reports.
13. Target identity fields (`year`, `indicator`, `scope_unit`) are **locked once submissions exist** for the same year+indicator. Only `target_value` and `notes` remain mutable.
14. **Every state change writes to `AuditLog`** (apps/audit) via `AuditService.log_*`. The log is append-only — never UPDATE or DELETE.

---

## When Starting a New Task

1. Read the relevant `docs/` file first
2. Check existing models before creating new ones
3. Write the service layer before the view layer
4. Write tests alongside implementation (not after)
5. Ensure all new API endpoints have Arabic error messages
6. Run `python manage.py check` after model changes
