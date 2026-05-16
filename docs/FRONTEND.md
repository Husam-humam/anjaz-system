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
| `/organization` | الهيكل التنظيمي | Read-only tree view from external system + **auto-sync on every page open** + **click any qism to manage its assignment role** (planning / supervised / unassigned) in an inline dialog |
| `/indicators` | بنك المؤشرات | List + manage indicators (+ categories tab) |
| `/users` | إدارة المستخدمين | List + create + edit users |
| `/periods` | الأسابيع | List weeks, open/close, compliance + extensions |
| `/targets` | المستهدفات | Manage hierarchical annual targets |
| `/forms` | قوالب الاستمارات | List + create + approve/reject form templates (merged page — replaces old `/approvals/forms`). Shows sidebar badge for pending templates |
| `/achievements` | المنجزات | **NEW**: admin review page — list approved submissions, filter by week/dairas/mudiriyas/qisms/review-status, open `AdminReviewModal` for approve/edit/return. Sidebar badge shows pending-review count |
| `/approvals` | المنجزات النوعية بانتظار الاعتماد | Pending qualitative items (Step 3 of qualitative flow) |
| `/reports` | التقارير | Full institutional reports (PDF/Excel exports carry generation timestamp) |

### Planning Section
| Route | Page | Description |
|---|---|---|
| `/forms` | قوالب الاستمارات | Create + submit + approve form templates (scoped) |
| `/approvals` | المنجزات بانتظار الاعتماد | Weekly submissions to approve. Also surfaces submissions returned by admin (status `returned_by_admin`) — planner can edit answers and re-approve, or reject back to section_manager |
| `/reports` | تقارير المديرية | Scoped to own directorate |

### Section Manager
| Route | Page | Description |
|---|---|---|
| `/submission` | تقديم المنجز الأسبوعي | Current week's form. `returned_by_admin` is editable always (deadline bypass) |
| `/history` | سجل المنجزات | Past submissions + charts + audit log per submission |
| `/reports` | تقارير قسمي | Own section analytics |

### Viewer (Phase G+)
دور قراءة فقط — كل أزرار الإجراءات مُخفيّة عبر `usePermissions().canAct()`، والـ backend يفرض ذلك بصلاحيّة `IsNotViewer`.

| Route | Page | Description |
|---|---|---|
| `/dashboard` | لوحة التحكم | Read-only summary stats |
| `/reports` | التقارير | Reports scoped to `ViewScope.viewable_units` |
| `/notifications` | الإشعارات | Personal notifications |

---

## 3. Key Page Designs

### 3.1 Login Page (`/login`)

```
┌─────────────────────────────────────┐
│            شعار المؤسسة             │
│      نظام ج33 - قسم الاحصاء       │
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

**Read-only tree view** — source of truth is the external organization system.

- **Auto-sync on mount**: on every page visit (admin only), the page automatically `POST /api/organization/units/sync/` and updates the tree in-place. A status banner shows the result (created/updated/deactivated counts) or any error.
- Manual **"مزامنة الآن"** button retriggers sync on demand.
- Admin sees a **"إدارة تخصيصات التخطيط"** button linking to `/organization/assignments` (Phase G).
- No edit/add/deactivate buttons — units are owned by the external system.
- Qism badges are derived from explicit assignments (Phase F+):
  - `is_planning=true` → orange badge "تخطيط"
  - `is_supervised=true` → teal badge "مُشرَف عليه"
  - neither → gray badge "غير مُسنَد"

```
🏛 دائرة الشؤون الإدارية (ADMIN)
  ├─ 🏢 مديرية الموارد البشرية (HR)
  │    ├─ 👥 قسم التوظيف (EMP)        [مُشرَف عليه]
  │    ├─ 📋 قسم التخطيط (PLAN)        [تخطيط]
  │    └─ 👥 قسم التدريب (TRAIN)       [مُشرَف عليه]
  └─ 👥 قسم الأرشيف (ARCH)            [غير مُسنَد]
```

### 3.4.b Qism Assignment Dialog (in-tree)

Admin clicks any active qism in the tree → modal opens with three modes based on the unit's current role:

1. **Unassigned** — single button "تخصيصه كقسم تخطيط" that creates a `PlanningAssignment`.
2. **Supervised** — read-only info card showing which planning unit supervises it, with a hint to manage the link from that planning unit's dialog instead.
3. **Planning** — full management panel:
   - Dropdown of available qisms (auto-excludes already-planning and already-supervised units) + "إضافة" button to add a `SupervisedUnit`.
   - Scrollable list of supervised units, each with a delete (✕) button.
   - "إلغاء دور التخطيط لهذا القسم" button at the bottom (with confirm prompt) deletes the whole `PlanningAssignment`.

All actions update the tree (badges) and the dialog (lists) without closing the modal.

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
│  [تصدير PDF]  [تصدير Excel]   (Both carry a          │
│   generation timestamp in the footer/header)         │
└──────────────────────────────────────────────────────┘
```

---

### 3.7 Achievements / Admin Review (`/achievements`)  **[statistics_admin]**

```
┌──────────────────────────────────────────────────────┐
│  المنجزات                                            │
│  [بانتظار: 12]   [إجمالي النتائج: 87]               │
├──────────────────────────────────────────────────────┤
│  🔍 بحث  |  سنة ▾  |  أسبوع  |                       │
│  دائرة ▾  |  مديرية ▾  |  قسم ▾                       │
│  حالة المراجعة: ( بانتظار ) ( تمّت ) ( الكل )       │
├──────────────────────────────────────────────────────┤
│  جدول: القسم | المديرية | الأسبوع | اعتماد التخطيط   │
│         | حالة المراجعة | إجراء                       │
└──────────────────────────────────────────────────────┘
```

Clicking a row opens **`AdminReviewModal`** with two tabs (الإجابات / سجلّ التدقيق)
and three action buttons (اعتماد / تعديل / إرجاع):
- **اعتماد**: confirmation chip in the modal, no reason. Locks submission.
- **تعديل**: switches the answers table to editable inputs (numeric/text per indicator unit type). Qualitative answers are read-only (handled by `/approvals` flow). Highlights changed rows. Requires a mandatory reason. On save, writes audit log with old→new diffs.
- **إرجاع للتخطيط**: requires a mandatory reason. Status moves to `returned_by_admin`, submission is excluded from statistics until planning re-approves.

Once any admin acts on a submission, the modal shows a purple lock banner with the reviewer's name and timestamp; action buttons are hidden. Sidebar badge auto-refreshes via React Query `invalidateQueries`.

---

## 4. Reusable Components

### `StatusBadge`
Displays submission/form status with color coding:
- `draft` → رمادي: مسودة
- `submitted` → أزرق: مُرسل
- `approved` → أخضر: معتمد
- `returned` → كهرماني: مُرجَع للتصحيح
- `returned_by_admin` → بنفسجي: مُرجَع من الإحصاء
- `late` → أحمر: متأخر
- `extended` → برتقالي: مُمدَّد
- `pending_approval` → أصفر: بانتظار الاعتماد
- `rejected` → أحمر: مرفوض

### `AdminReviewModal`  (`app/(dashboard)/achievements/AdminReviewModal.tsx`)
Self-contained 3-mode modal (view/edit/return) for the achievements page.
Props: `{ submissionId: number | null; open: boolean; onClose: () => void }`.
Fetches fresh submission via `getSubmission(id)`, computes editable drafts per answer, calls `adminApproveSubmission` / `adminEditSubmission` / `adminReturnSubmission`. Invalidates `pending-admin-review`, sidebar badge, and audit-log queries on success.

### `AuditLogPanel`  (`app/(dashboard)/achievements/AuditLogPanel.tsx`)
Timeline view of all actions on a submission. Each entry shows action type chip, actor + role, timestamp, reason (if any), and per-field diff cards (old → new) for edit actions. Used inside `AdminReviewModal` and reusable elsewhere.

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

**Viewer sidebar (Phase G+):**
```
📊 لوحة التحكم
📈 التقارير
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
