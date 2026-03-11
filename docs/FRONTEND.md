# FRONTEND.md — Frontend UI Structure

**Framework:** Next.js 15 (App Router)  
**Language:** Arabic (RTL) — All UI text must be in Arabic  
**Styling:** Tailwind CSS + shadcn/ui  
**Direction:** `dir="rtl"` on `<html>` element

---

## 1. Global Layout Requirements

- **RTL layout** everywhere — all flexbox/grid directions reversed
- **Font:** Cairo or Noto Sans Arabic (loaded via `next/font/google`)
- **Colors:**
  - Primary: Blue `#1d4ed8`
  - Success: Green `#16a34a`
  - Warning: Amber `#d97706`
  - Danger: Red `#dc2626`
  - Background: Gray `#f9fafb`
- **Sidebar** on the right side (RTL convention)
- All dates displayed in Arabic locale (`ar-IQ`)
- Numbers in Arabic-Eastern numerals is optional — Western numerals acceptable

---

## 2. Page Map

### Public Pages
| Route | Page | Description |
|---|---|---|
| `/login` | صفحة تسجيل الدخول | Username + password form |

### Shared (All Roles)
| Route | Page | Description |
|---|---|---|
| `/dashboard` | لوحة التحكم | Role-aware dashboard |
| `/notifications` | الإشعارات | All notifications with read/unread |
| `/profile` | الملف الشخصي | View profile, change password |

### Statistics Admin Only
| Route | Page | Description |
|---|---|---|
| `/organization` | الهيكل التنظيمي | Interactive tree view |
| `/organization/new` | إضافة كيان | Add daira/mudiriya/qism |
| `/indicators` | بنك المؤشرات | List + manage indicators |
| `/indicators/categories` | تصنيفات المؤشرات | Manage categories |
| `/users` | إدارة المستخدمين | List + create + edit users |
| `/periods` | الأسابيع | List weeks, open/close |
| `/periods/new` | فتح أسبوع جديد | Create weekly period |
| `/periods/{id}` | تفاصيل الأسبوع | Compliance view + extensions |
| `/targets` | المستهدفات | Manage annual targets |
| `/approvals/forms` | اعتماد الاستمارات | Pending form templates |
| `/approvals/qualitative` | اعتماد المنجز النوعي | Pending qualitative items |
| `/reports` | التقارير | Full institutional reports |

### Planning Section
| Route | Page | Description |
|---|---|---|
| `/forms` | استمارات الأقسام | List sections' form templates |
| `/forms/new` | إنشاء استمارة | Build form from indicators bank |
| `/forms/{id}` | تفاصيل الاستمارة | View/edit form template |
| `/approvals` | المنجزات بانتظار الاعتماد | Weekly submissions to approve |
| `/reports` | تقارير المديرية | Scoped to own directorate |

### Section Manager
| Route | Page | Description |
|---|---|---|
| `/submission` | تقديم المنجز الأسبوعي | Current week's form |
| `/history` | سجل المنجزات | Past submissions + charts |
| `/reports` | تقارير قسمي | Own section analytics |

---

## 3. Key Page Designs

### 3.1 Login Page (`/login`)

```
┌─────────────────────────────────────┐
│            شعار المؤسسة             │
│      نظام حصر المنجزات الإداري      │
│                                     │
│  ┌─────────────────────────────┐    │
│  │     اسم المستخدم            │    │
│  └─────────────────────────────┘    │
│  ┌─────────────────────────────┐    │
│  │     كلمة المرور             │    │
│  └─────────────────────────────┘    │
│  [         تسجيل الدخول        ]    │
└─────────────────────────────────────┘
```

**Components:** Input, Button, Form (React Hook Form + Zod)  
**Validation messages in Arabic**  
**On success:** Redirect to `/dashboard`

---

### 3.2 Dashboard (`/dashboard`)

**Statistics Admin view:**
```
┌──────────────────────────────────────────────────────┐
│  الأسبوع الحالي: الأسبوع 15 / 2025   [مفتوح] ●      │
│  الموعد النهائي: الاثنين 14 أبريل 2025               │
├────────┬────────┬────────┬────────────────────────────┤
│  20    │  16    │   3    │         1                   │
│ قسم    │ معتمد  │متأخر   │   بانتظار اعتماد           │
├────────┴────────┴────────┴────────────────────────────┤
│  [مخطط دائري: نسبة الامتثال]                          │
├───────────────────────────────────────────────────────┤
│  المنجزات النوعية بانتظار الاعتماد (3)               │
│  [جدول: القسم | الأسبوع | العنوان | الإجراء]          │
└───────────────────────────────────────────────────────┘
```

**Section Manager view:**
```
┌──────────────────────────────────────────────────────┐
│  الأسبوع 15 / 2025 — الموعد: 14 أبريل               │
│  حالة تقديمك: ● مسودة  [استكمال التقديم]            │
├───────────────────────────────────────────────────────┤
│  المستهدفات السنوية                                   │
│  ████████░░░░░░  عدد المعاملات: 1,240 / 2,400 (51%) │
│  ██████████████  التقارير: 45 / 50 (90%)             │
├───────────────────────────────────────────────────────┤
│  [مخطط خطي: المنجز الأسبوعي — آخر 8 أسابيع]         │
└───────────────────────────────────────────────────────┘
```

---

### 3.3 Weekly Submission Form (`/submission`)

```
┌──────────────────────────────────────────────────────┐
│  تقديم المنجز — الأسبوع 15 / 2025                   │
│  الموعد النهائي: الاثنين 14 أبريل 2025 الساعة 11:59  │
├───────────────────────────────────────────────────────┤
│  1. عدد الحاسبات المُصلَّحة *              [____] جهاز │
│     ☐ منجز نوعي                                      │
│                                                       │
│  2. عدد التقارير المُعدَّة                  [____] تقرير│
│     ☐ منجز نوعي                                      │
│                                                       │
│  3. ملاحظات إضافية                                   │
│     [________________________________]                │
│                                                       │
├───────────────────────────────────────────────────────┤
│  [حفظ كمسودة]              [إرسال المنجز للاعتماد]   │
└──────────────────────────────────────────────────────┘
```

**When "منجز نوعي" checkbox is checked:**
```
  ✅ منجز نوعي
  ┌─────────────────────────────────────────────────┐
  │ تفاصيل المنجز النوعي *                          │
  │ [                                               ]│
  │ [                                               ]│
  └─────────────────────────────────────────────────┘
```

**UX Rules:**
- Show deadline countdown timer if < 48 hours remaining
- Auto-save draft every 2 minutes
- Mandatory fields highlighted in red if submitted without value
- Confirmation dialog before final submission

---

### 3.4 Organization Tree (`/organization`)

Interactive tree with expand/collapse. Each node shows:
- Icon (building/office/person based on type)
- Name + code
- Active/inactive badge
- Quick actions (edit, add child, deactivate)

```
🏛 دائرة الشؤون الإدارية (ADMIN)          [+ إضافة] [✏]
  ├─ 🏢 مديرية الموارد البشرية (HR)        [+ إضافة] [✏]
  │    ├─ 👥 قسم التوظيف (EMP)                       [✏]
  │    ├─ 📋 قسم التخطيط (PLAN) [تخطيط]              [✏]
  │    └─ 👥 قسم التدريب (TRAIN)                      [✏]
  └─ 👥 قسم الأرشيف (ARCH)                           [✏]
🏢 مديرية التخطيط والمتابعة (PLANNING) [مستقلة]
  ├─ 📊 قسم الإحصاء (STAT) [إحصاء]                  [✏]
  └─ 👥 قسم المتابعة (FOLLOW)                        [✏]
```

---

### 3.5 Indicators Bank (`/indicators`)

Table view with filters:

| اسم المؤشر | التصنيف | وحدة القياس | طريقة التجميع | الحالة |
|---|---|---|---|---|
| عدد الحاسبات المُصلَّحة | فني | جهاز (رقم) | مجموع | ✅ نشط |
| معدل الإنجاز | إداري | % | متوسط | ✅ نشط |

Filters: category, unit_type, is_active, search  
Action buttons: إضافة مؤشر, تعديل, تعطيل

---

### 3.6 Reports Page (`/reports`)

```
┌──────────────────────────────────────────────────────┐
│  نوع التقرير: [أسبوعي ▾]  السنة: [2025 ▾]           │
│  الوحدة: [المؤسسة كاملة ▾]   [توليد التقرير]        │
├───────────────────────────────────────────────────────┤
│  جدول: الكيان | المؤشر | القيمة | المستهدف | النسبة  │
├───────────────────────────────────────────────────────┤
│  [تصدير PDF]  [تصدير Excel]                          │
└──────────────────────────────────────────────────────┘
```

---

## 4. Reusable Components

### `StatusBadge`
Displays submission/form status with color coding:
- `draft` → رمادي: مسودة
- `submitted` → أزرق: مُرسل
- `approved` → أخضر: معتمد
- `late` → أحمر: متأخر
- `extended` → برتقالي: مُمدَّد
- `pending_approval` → أصفر: بانتظار الاعتماد
- `rejected` → أحمر: مرفوض

### `ProgressBar`
Shows target achievement:
```tsx
<ProgressBar
  value={1240}
  target={2400}
  label="عدد المعاملات المنجزة"
  unit="معاملة"
/>
// Renders: ████████░░░░ 1,240 / 2,400 (51.7%)
```

### `ComplianceChart`
Pie/donut chart: معتمد / متأخر / مسودة / لم يُسلَّم

### `WeeklyTrendChart`
Line chart showing weekly values for an indicator over time.

### `NotificationBell`
Bell icon in header with unread count badge. Opens dropdown with latest notifications. WebSocket-powered real-time updates.

### `ConfirmDialog`
Reusable confirmation modal for destructive/important actions.
- Always shows Arabic confirmation message
- Two buttons: تأكيد / إلغاء

---

## 5. Form Validation (Arabic Messages)

Use **Zod** for schema validation. All messages in Arabic:

```typescript
const loginSchema = z.object({
  username: z.string().min(1, "اسم المستخدم مطلوب"),
  password: z.string().min(6, "كلمة المرور يجب أن تكون 6 أحرف على الأقل"),
});

const submissionAnswerSchema = z.object({
  numeric_value: z.number().nullable().optional(),
  qualitative_details: z.string().optional(),
  is_qualitative: z.boolean(),
}).refine(
  (data) => !data.is_qualitative || (data.qualitative_details?.trim().length ?? 0) > 0,
  { message: "يجب إدخال تفاصيل المنجز النوعي", path: ["qualitative_details"] }
);
```

---

## 6. Loading & Error States

Every data-fetching component must handle three states:
1. **Loading:** Use `Skeleton` component from shadcn/ui
2. **Error:** Show Arabic error message + retry button
3. **Empty:** Show Arabic empty state message with helpful hint

```tsx
// Pattern for every list page
if (isLoading) return <TableSkeleton rows={5} />;
if (error) return <ErrorState message="حدث خطأ في تحميل البيانات" onRetry={refetch} />;
if (data.length === 0) return <EmptyState message="لا توجد بيانات للعرض" />;
return <DataTable data={data} />;
```

---

## 7. Navigation & Sidebar

Sidebar items are role-filtered. Active item highlighted.

**Statistics Admin sidebar:**
```
📊 لوحة التحكم
🏛 الهيكل التنظيمي
📋 بنك المؤشرات
👤 المستخدمون
📅 الأسابيع
🎯 المستهدفات
✅ طلبات الاعتماد  (badge: pending count)
📈 التقارير
🔔 الإشعارات      (badge: unread count)
```

**Section Manager sidebar:**
```
📊 لوحة التحكم
📝 تقديم المنجز   (badge: if deadline near)
📁 سجل المنجزات
📈 تقارير قسمي
🔔 الإشعارات
```

---

## 8. Responsive Breakpoints

| Breakpoint | Behavior |
|---|---|
| Mobile (< 768px) | Sidebar collapses to bottom nav or hamburger menu |
| Tablet (768–1024px) | Sidebar icon-only (collapsed) |
| Desktop (> 1024px) | Full sidebar with labels |

---

## 9. Key UX Decisions

1. **Deadline countdown:** Show prominent timer on submission page when deadline < 48h
2. **Auto-save:** Submission drafts auto-saved every 2 minutes with visual indicator
3. **Optimistic updates:** Mark notification as read instantly, revert on error
4. **Confirm before submit:** Modal confirmation before final submission (irreversible action)
5. **Version history:** Form template history accessible with side-by-side diff view
6. **Print-friendly:** Reports pages have print stylesheet
