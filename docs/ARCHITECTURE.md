# ARCHITECTURE.md — Technical Architecture

---

## 1. System Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Client Browser                        │
│                    Next.js 15 (RTL Arabic)                   │
└────────────────────────────┬────────────────────────────────┘
                             │ HTTPS
                    ┌────────▼────────┐
                    │     Nginx        │
                    │  Reverse Proxy   │
                    └────┬───────┬────┘
                         │       │ WebSocket
              ┌──────────▼──┐  ┌─▼──────────────┐
              │  Django REST │  │ Django Channels │
              │  Framework   │  │  (WebSocket)    │
              └──────┬───────┘  └────────┬────────┘
                     │                   │
              ┌──────▼───────────────────▼────────┐
              │           Django Application        │
              │  organization │ accounts │ forms   │
              │  indicators   │ targets  │ reports │
              │  submissions  │ notifications       │
              └──────┬──────────────────┬──────────┘
                     │                  │
              ┌──────▼──────┐   ┌───────▼──────┐
              │  PostgreSQL  │   │    Redis      │
              │  (Primary DB)│   │  (Channels)   │
              └─────────────┘   └──────────────┘
```

---

## 2. Backend Architecture

### 2.1 App Structure Pattern

Each Django app follows this internal structure:

```
apps/example_app/
├── __init__.py
├── admin.py          # Django admin registration
├── apps.py           # App config
├── models.py         # Data models with validation
├── serializers.py    # DRF serializers (input/output)
├── views.py          # ViewSets (thin — calls services)
├── services.py       # Business logic layer
├── querysets.py      # Custom QuerySet methods
├── permissions.py    # Custom DRF permissions
├── signals.py        # Django signals (for notifications)
├── urls.py           # URL patterns
└── tests/
    ├── test_models.py
    ├── test_services.py
    ├── test_api.py
    └── factories.py  # factory_boy factories
```

### 2.2 Layered Architecture

```
HTTP Request
    ↓
[Permission Check]     ← permissions.py
    ↓
[View / ViewSet]       ← views.py       (thin: validate input, call service)
    ↓
[Serializer]           ← serializers.py (validate & transform data)
    ↓
[Service Layer]        ← services.py    (all business logic lives here)
    ↓
[QuerySet Layer]       ← querysets.py   (all DB queries live here)
    ↓
[Model]                ← models.py      (schema + model-level validation)
    ↓
PostgreSQL
```

**Rule:** Views never contain business logic. Services never import from views. Models never import from services.

### 2.3 Service Layer Example Pattern

```python
# services.py
class SubmissionService:

    @staticmethod
    def submit_weekly(submission: WeeklySubmission, user: User) -> WeeklySubmission:
        """Handles the transition from draft to submitted state."""
        if not submission.is_editable():
            raise ValidationError("لا يمكن تعديل هذا التقديم بعد انقضاء الموعد")
        
        submission.status = WeeklySubmission.Status.SUBMITTED
        submission.submitted_at = timezone.now()
        submission.save()
        
        NotificationService.notify_planning_section(submission)
        return submission
```

### 2.4 Settings Structure

```python
config/settings/
├── base.py          # All common settings
├── development.py   # DEBUG=True, local DB, console email
└── production.py    # Security headers, env vars only
```

Use `python-decouple` or `django-environ` for environment variables. Never hardcode secrets.

---

## 3. Frontend Architecture

### 3.1 Next.js App Router Structure

```
src/
├── app/
│   ├── layout.tsx              # Root layout (RTL, Arabic font)
│   ├── page.tsx                # Redirect to /login or /dashboard
│   ├── (auth)/
│   │   └── login/
│   │       └── page.tsx
│   ├── (dashboard)/
│   │   ├── layout.tsx          # Dashboard shell (sidebar + header)
│   │   ├── dashboard/
│   │   │   └── page.tsx        # Role-aware dashboard
│   │   ├── organization/       # [statistics_admin only]
│   │   ├── indicators/         # [statistics_admin only]
│   │   ├── users/              # [statistics_admin only]
│   │   ├── periods/            # [statistics_admin only]
│   │   ├── targets/            # [statistics_admin only]
│   │   ├── forms/              # [planning_section]
│   │   ├── submissions/        # [all roles, scoped]
│   │   ├── reports/            # [all roles, scoped]
│   │   └── notifications/      # [all roles]
│   └── api/                    # Next.js route handlers (if needed)
├── components/
│   ├── ui/                     # shadcn/ui re-exports
│   ├── layout/                 # Sidebar, Header, Breadcrumb
│   ├── forms/                  # Reusable form components
│   ├── charts/                 # Recharts wrappers
│   ├── tables/                 # Data table components
│   └── shared/                 # StatusBadge, LoadingSpinner, etc.
├── lib/
│   ├── api/
│   │   ├── client.ts           # Axios instance with interceptors
│   │   ├── organization.ts     # Organization API functions
│   │   ├── indicators.ts
│   │   ├── forms.ts
│   │   ├── submissions.ts
│   │   ├── reports.ts
│   │   └── notifications.ts
│   ├── utils.ts                # General utilities
│   └── constants.ts            # App-wide constants
├── hooks/
│   ├── useAuth.ts
│   ├── useNotifications.ts     # WebSocket connection
│   └── usePermissions.ts
├── stores/
│   ├── authStore.ts            # Zustand: user + token
│   └── notificationStore.ts   # Zustand: unread count
└── types/
    ├── organization.ts
    ├── indicators.ts
    ├── submissions.ts
    └── api.ts                  # Generic API response types
```

### 3.2 RTL Configuration

All pages must be RTL. Configure in root layout:

```tsx
// app/layout.tsx
export default function RootLayout({ children }) {
  return (
    <html lang="ar" dir="rtl">
      <body className="font-arabic">
        {children}
      </body>
    </html>
  )
}
```

Tailwind RTL classes: use `rtl:` prefix where directional logic differs.  
Font: **Noto Sans Arabic** or **Cairo** from Google Fonts.

### 3.3 API Client Pattern

```typescript
// lib/api/client.ts
const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL,
});

// Auto-attach JWT token
apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Handle 401 → redirect to login
apiClient.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().logout();
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);
```

---

## 4. Authentication Flow

```
POST /api/auth/login/
  → Returns: { access_token, refresh_token, user }
  → Store: access in memory (Zustand), refresh in httpOnly cookie

Refresh: POST /api/auth/token/refresh/
  → Called automatically by interceptor on 401

Logout: POST /api/auth/logout/
  → Blacklist refresh token (Simple JWT blacklist)
  → Clear Zustand store
```

---

## 5. Real-Time Notifications

Using **Django Channels** with **Redis** as the channel layer:

```
Frontend (WebSocket)
    ↔ Django Channels Consumer
        ↔ Redis Channel Layer
            ← Django Signals (on model save/status change)
```

Each user connects to their personal channel group: `notifications_user_{user_id}`

Notification payload structure:
```json
{
  "type": "notification",
  "data": {
    "id": 42,
    "notification_type": "submission_approved",
    "title": "تم اعتماد المنجز الأسبوعي",
    "message": "...",
    "is_read": false,
    "created_at": "2025-01-15T10:30:00Z",
    "related_model": "WeeklySubmission",
    "related_id": 99
  }
}
```

---

## 6. Report Generation Architecture

```
Request: GET /api/reports/export/?type=monthly&month=3&year=2025&format=pdf

ReportService.generate(params)
    ↓
AggregationEngine.aggregate(submissions, period)
    → Respects accumulation_type per indicator
    → Applies hierarchy: Qism → Mudiriya → Daira → Institution
    ↓
PDFRenderer (ReportLab) OR ExcelRenderer (OpenPyXL)
    ↓
FileResponse (download)
```

---

## 7. Docker Compose (Development)

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: anjaz_db
      POSTGRES_USER: anjaz_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}

  redis:
    image: redis:7-alpine

  backend:
    build: ./backend
    command: python manage.py runserver 0.0.0.0:8000
    volumes:
      - ./backend:/app
    depends_on: [db, redis]
    env_file: .env

  frontend:
    build: ./frontend
    command: npm run dev
    volumes:
      - ./frontend:/app
    ports:
      - "3000:3000"
```

---

## 8. Environment Variables

```bash
# .env.example

# Django
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DB_NAME=anjaz_db
DB_USER=anjaz_user
DB_PASSWORD=your-db-password
DB_HOST=db
DB_PORT=5432

# Redis
REDIS_URL=redis://redis:6379/0

# JWT
JWT_ACCESS_TOKEN_LIFETIME_MINUTES=60
JWT_REFRESH_TOKEN_LIFETIME_DAYS=7

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000/api
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws
```
