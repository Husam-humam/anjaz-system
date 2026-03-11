# نظام أنجز — منظومة تتبع المنجزات المؤسسية

<div dir="rtl" align="right">

## نظرة عامة

**نظام أنجز** هو منصة متكاملة لتتبع المنجزات المؤسسية، مصمم لرقمنة دورة التقارير الأسبوعية في المؤسسات الحكومية. يتيح النظام للأقسام تقديم منجزاتها، ولأقسام التخطيط مراجعتها واعتمادها، ولقسم الإحصاء تجميع البيانات في تقارير دورية (أسبوعية، شهرية، ربع سنوية، نصف سنوية، سنوية).

## المميزات الرئيسية

- **هيكل تنظيمي هرمي**: دائرة ← مديرية ← قسم (يدعم أنماط متعددة)
- **إدارة المؤشرات**: بنك مؤشرات مع دعم للمؤشرات الكمية والنوعية
- **قوالب الاستمارات**: نظام قوالب ديناميكي مع إصدارات ودورة اعتماد
- **المستهدفات السنوية**: تحديد ومتابعة الأهداف لكل قسم ومؤشر
- **المنجزات الأسبوعية**: تقديم واعتماد المنجزات مع نظام تمديد المواعيد
- **المنجزات النوعية**: اعتماد ثنائي المرحلة (تخطيط ← إحصاء)
- **التقارير**: تقارير دورية مع تصدير PDF و Excel
- **الإشعارات**: إشعارات فورية عبر WebSocket
- **واجهة عربية**: واجهة مستخدم كاملة بالعربية مع دعم RTL

## أدوار المستخدمين

| الدور | الوصف | الصلاحيات |
|-------|-------|-----------|
| مدير قسم الإحصاء | `statistics_admin` | صلاحيات كاملة على النظام |
| قسم التخطيط | `planning_section` | إدارة المديرية/الدائرة التابع لها |
| مدير قسم | `section_manager` | إدارة قسمه فقط |

## البنية التقنية

### الخلفية (Backend)
- **Python 3.12+** / **Django 5.x** / **Django REST Framework**
- **PostgreSQL 16** — قاعدة البيانات
- **Redis** — قنوات WebSocket
- **django-mptt** — الشجرة التنظيمية الهرمية
- **Simple JWT** — المصادقة
- **ReportLab** — تصدير PDF
- **OpenPyXL** — تصدير Excel

### الواجهة الأمامية (Frontend)
- **Next.js 15** (App Router) / **TypeScript**
- **Tailwind CSS** / **shadcn/ui**
- **React Query** — إدارة حالة الخادم
- **Zustand** — إدارة الحالة المحلية
- **Recharts** — الرسوم البيانية
- **React Hook Form + Zod** — التحقق من المدخلات

### البنية التحتية
- **Docker + Docker Compose** — بيئة التطوير
- **Nginx** — وكيل عكسي

## هيكل المشروع

```
anjaz_system/
├── backend/
│   ├── config/              # إعدادات Django
│   ├── apps/
│   │   ├── organization/    # الهيكل التنظيمي (MPTT)
│   │   ├── accounts/        # المستخدمين والمصادقة
│   │   ├── indicators/      # بنك المؤشرات
│   │   ├── forms/           # قوالب الاستمارات
│   │   ├── targets/         # المستهدفات السنوية
│   │   ├── submissions/     # المنجزات الأسبوعية
│   │   ├── reports/         # التقارير
│   │   └── notifications/   # الإشعارات
│   └── requirements/
├── frontend/
│   └── src/
│       ├── app/             # صفحات Next.js
│       ├── components/      # المكونات
│       ├── lib/             # المكتبات والأدوات
│       ├── hooks/           # React Hooks
│       ├── stores/          # Zustand Stores
│       └── types/           # أنواع TypeScript
├── docs/                    # التوثيق الكامل
├── nginx/                   # إعدادات Nginx
├── docker-compose.yml
└── .env.example
```

## التشغيل

### المتطلبات
- Docker و Docker Compose
- Git

### خطوات التشغيل

```bash
# 1. استنساخ المشروع
git clone https://github.com/Husam-humam/anjaz-system.git
cd anjaz-system

# 2. إعداد ملف البيئة
cp .env.example .env
# عدّل القيم في .env حسب بيئتك

# 3. تشغيل الحاويات
docker-compose up -d

# 4. تنفيذ الهجرات
docker-compose exec backend python manage.py migrate

# 5. إنشاء مستخدم مدير
docker-compose exec backend python manage.py createsuperuser

# 6. تحميل البيانات الأولية
docker-compose exec backend python manage.py seed_initial_data
```

### الوصول
- **الواجهة الأمامية**: http://localhost:3000
- **واجهة API**: http://localhost:8000/api/
- **لوحة الإدارة**: http://localhost:8000/admin/

## الاختبارات

```bash
# اختبارات الخلفية
docker-compose exec backend pytest --cov

# اختبارات الواجهة الأمامية
cd frontend && npm run test
```

## التوثيق

| الملف | المحتوى |
|-------|---------|
| [PRD.md](docs/PRD.md) | متطلبات المنتج الكاملة |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | البنية التقنية والقرارات المعمارية |
| [DATABASE.md](docs/DATABASE.md) | مخطط قاعدة البيانات وقواعد العمل |
| [API.md](docs/API.md) | جميع نقاط API مع الصلاحيات |
| [FRONTEND.md](docs/FRONTEND.md) | هيكل الواجهة والمكونات |
| [TESTING.md](docs/TESTING.md) | استراتيجية الاختبار وحالات الاختبار |

## الترخيص

هذا المشروع للاستخدام المؤسسي الداخلي.

</div>
