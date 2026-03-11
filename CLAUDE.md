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
│   │   ├── submissions/         # Weekly submissions
│   │   ├── reports/             # Report generation
│   │   └── notifications/       # In-app notifications
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
2. A `FormTemplate` becomes active on the `effective_from_week` — **never retroactively**.
3. Historical submissions are **always linked to the FormTemplate version used at submission time**.
4. Qualitative achievements require **two-step approval**: planning section → statistics admin.
5. Targets are **optional** — their absence must not break any calculation.
6. Report aggregation must respect `accumulation_type`: `sum`, `average`, or `last_value`.
7. The organization tree allows: Daira→Mudiriya→Qism, Daira→Qism, Mudiriya→Qism (independent).
8. A `Qism` can never be a parent of another unit.
9. Only `statistics_admin` can create users, open/close weeks, approve templates, set targets, grant extensions.
10. Notifications must be created automatically on every status change event.

---

## When Starting a New Task

1. Read the relevant `docs/` file first
2. Check existing models before creating new ones
3. Write the service layer before the view layer
4. Write tests alongside implementation (not after)
5. Ensure all new API endpoints have Arabic error messages
6. Run `python manage.py check` after model changes
