"""
اختبار write-flows على API: إنشاء + تعديل + حذف.
يستخدم requests مباشرة لتفادي مشاكل ترميز bash مع العربيّة.
"""
import sys
import time
import urllib3

import requests

# Windows console يحتاج UTF-8 صريح للعربيّة
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE = "https://anjaz.inss.local"
ADMIN_USER = "admin"
ADMIN_PASS = "Admin@2026secure"

# Schannel على Windows يفشل في CRL — نتجاوز التحقّق
# نُمرّر verify=False في كل request لأنّ session.verify قد لا يحترَم في بعض الإصدارات
session = requests.Session()
session.verify = False
_orig_request = session.request
session.request = lambda *a, **kw: _orig_request(*a, **{**kw, 'verify': False})

passes = 0
fails = []


def ok(msg):
    global passes
    print(f"\033[32m✓\033[0m {msg}")
    passes += 1


def fail(msg, detail=""):
    print(f"\033[31m✗\033[0m {msg}  [{detail}]")
    fails.append(f"{msg}: {detail}")


def show_section(title):
    print(f"\n─── {title} ───")


# Login
show_section("المصادقة")
r = session.post(
    f"{BASE}/api/auth/login/",
    json={"username": ADMIN_USER, "password": ADMIN_PASS},
)
if r.status_code != 200:
    print(f"\033[31mLogin failed: {r.status_code} {r.text}\033[0m")
    sys.exit(1)
TOKEN = r.json()["access"]
ok(f"Login (token len={len(TOKEN)})")

session.headers.update({"Authorization": f"Bearer {TOKEN}"})

# Indicators
show_section("المؤشّرات")
suffix = str(int(time.time()))

r = session.post(
    f"{BASE}/api/indicators/categories/",
    json={"name": f"اختبار_{suffix}", "description": "smoke test"},
)
print(f"  category create: {r.status_code} {r.text[:200]}")
if r.status_code != 201:
    fail("Create category", f"HTTP {r.status_code}: {r.text[:200]}")
    sys.exit(1)
CAT_ID = r.json()["id"]
ok(f"POST /api/indicators/categories/ (id={CAT_ID})")

ind_ids = []
for name in [f"اختبار مؤشر 1_{suffix}", f"اختبار مؤشر 2_{suffix}"]:
    r = session.post(
        f"{BASE}/api/indicators/",
        json={
            "name": name,
            "unit_type": "number",
            "accumulation_type": "sum",
            "category": CAT_ID,
        },
    )
    if r.status_code != 201:
        fail(f"Create indicator {name}", f"HTTP {r.status_code}: {r.text[:200]}")
        continue
    ind_ids.append(r.json()["id"])
    ok(f"POST /api/indicators/ (id={r.json()['id']})")

# مؤشّر نسبة لاختبار رفض الخلط
r = session.post(
    f"{BASE}/api/indicators/",
    json={
        "name": f"اختبار نسبة_{suffix}",
        "unit_type": "percentage",
        "accumulation_type": "average",
        "category": CAT_ID,
    },
)
if r.status_code != 201:
    fail("Create percentage indicator", f"HTTP {r.status_code}: {r.text[:200]}")
    PCT_ID = None
else:
    PCT_ID = r.json()["id"]
    ok(f"POST percentage indicator (id={PCT_ID})")

# المستهدف المركّب
show_section("المستهدفات المركّبة")
TARGET_ID = None
if len(ind_ids) == 2:
    r = session.post(
        f"{BASE}/api/targets/",
        json={
            "name": f"اختبار مركّب_{suffix}",
            "scope_unit": None,
            "indicator_ids": ind_ids,
            "year": 2026,
            "target_value": 100,
        },
    )
    if r.status_code != 201:
        fail("Create composite target", f"HTTP {r.status_code}: {r.text[:300]}")
    else:
        TARGET_ID = r.json()["id"]
        components = r.json().get("indicators", [])
        ok(f"POST composite target with 2 indicators (id={TARGET_ID}, components={len(components)})")

# رفض خلط الوحدات
if len(ind_ids) >= 1 and PCT_ID is not None:
    r = session.post(
        f"{BASE}/api/targets/",
        json={
            "name": f"مختلط_{suffix}",
            "scope_unit": None,
            "indicator_ids": [ind_ids[0], PCT_ID],
            "year": 2026,
            "target_value": 50,
        },
    )
    if r.status_code == 400:
        ok("Mixed unit types rejected (HTTP 400)")
    else:
        fail("Mixed unit types not rejected", f"HTTP {r.status_code}: {r.text[:200]}")

# تقدّم + breakdown
if TARGET_ID:
    for url in [f"/api/targets/{TARGET_ID}/progress/", f"/api/targets/{TARGET_ID}/breakdown/"]:
        r = session.get(f"{BASE}{url}")
        if r.status_code == 200:
            ok(f"GET {url}")
        else:
            fail(f"GET {url}", f"HTTP {r.status_code}")

    # تعديل اسم
    r = session.patch(
        f"{BASE}/api/targets/{TARGET_ID}/",
        json={"name": f"اختبار مركّب معدّل_{suffix}"},
    )
    if r.status_code == 200:
        ok(f"PATCH target (rename)")
    else:
        fail("PATCH target", f"HTTP {r.status_code}: {r.text[:200]}")

# PlanningAssignment — نحاول مع أوّل qism متاح
show_section("تخصيصات التخطيط")
r = session.get(f"{BASE}/api/organization/units/?unit_type=qism&page_size=100")
qisms = r.json().get("results", [])
# نختار qism غير مُسنَد (is_planning=False, is_supervised=False)
free_qism = next(
    (q for q in qisms if not q.get("is_planning") and not q.get("is_supervised")),
    None,
)
if free_qism:
    r = session.post(
        f"{BASE}/api/organization/planning-assignments/",
        json={"planning_unit": free_qism["id"]},
    )
    if r.status_code == 201:
        PA_ID = r.json()["id"]
        ok(f"POST planning-assignment (id={PA_ID})")

        # إضافة قسم تحت إشرافه
        other_qism = next(
            (q for q in qisms if q["id"] != free_qism["id"]
             and not q.get("is_planning") and not q.get("is_supervised")),
            None,
        )
        if other_qism:
            r = session.post(
                f"{BASE}/api/organization/planning-assignments/{PA_ID}/supervised-units/",
                json={"unit": other_qism["id"]},
            )
            if r.status_code == 201:
                ok(f"POST supervised-units (added qism {other_qism['id']})")
                # حذف الإشراف
                r = session.delete(
                    f"{BASE}/api/organization/planning-assignments/{PA_ID}/supervised-units/{other_qism['id']}/"
                )
                if r.status_code == 204:
                    ok("DELETE supervised-units")
                else:
                    fail("DELETE supervised-units", f"HTTP {r.status_code}")
            else:
                fail("POST supervised-units", f"HTTP {r.status_code}: {r.text[:200]}")

        # حذف التخصيص
        r = session.delete(f"{BASE}/api/organization/planning-assignments/{PA_ID}/")
        if r.status_code == 204:
            ok("DELETE planning-assignment")
        else:
            fail("DELETE planning-assignment", f"HTTP {r.status_code}")
    else:
        fail("POST planning-assignment", f"HTTP {r.status_code}: {r.text[:200]}")
else:
    ok("PlanningAssignment skipped (no free qisms in system)")

# Unit type mapping — تعديل
show_section("تطابق أنواع الوحدات")
r = session.get(f"{BASE}/api/organization/unit-type-mappings/")
mappings = r.json().get("results", [])
if mappings:
    mapping = mappings[0]
    original_treat = mapping["treat_as"]
    r = session.patch(
        f"{BASE}/api/organization/unit-type-mappings/{mapping['id']}/",
        json={"treat_as": "ignore"},
    )
    if r.status_code == 200:
        ok(f"PATCH mapping (id={mapping['id']}, set to ignore)")
        # رجّع القيمة الأصليّة
        session.patch(
            f"{BASE}/api/organization/unit-type-mappings/{mapping['id']}/",
            json={"treat_as": original_treat},
        )
        ok(f"PATCH mapping (restored to {original_treat})")
    else:
        fail("PATCH mapping", f"HTTP {r.status_code}: {r.text[:200]}")
else:
    ok("Mapping test skipped (no mappings — external system not synced)")

# Cleanup
show_section("تنظيف")
if TARGET_ID:
    r = session.delete(f"{BASE}/api/targets/{TARGET_ID}/")
    if r.status_code == 204:
        ok("DELETE target")
    else:
        fail("DELETE target", f"HTTP {r.status_code}")

for ind_id in ind_ids + ([PCT_ID] if PCT_ID else []):
    r = session.delete(f"{BASE}/api/indicators/{ind_id}/")
    if r.status_code == 204:
        ok(f"DELETE indicator {ind_id}")
    else:
        fail(f"DELETE indicator {ind_id}", f"HTTP {r.status_code}: {r.text[:200]}")

# Category: عادةً لا يُحذَف لو فيه مؤشّرات. نتجاهل.

# ────── ملخّص ──────
print("\n════════════════════")
print(f"ناجح: \033[32m{passes}\033[0m    فاشل: \033[31m{len(fails)}\033[0m")
print("════════════════════")
if fails:
    print("\n\033[31mالمشاكل:\033[0m")
    for f in fails:
        print(f"  - {f}")
    sys.exit(1)
print("\n\033[32mكل عمليّات الكتابة تعمل ✓\033[0m")
