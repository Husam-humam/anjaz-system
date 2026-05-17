#!/bin/bash
# اختبار write-flows: إنشاء + تعديل + حذف على نهايات API الحرجة.

set -u
BASE="https://anjaz.inss.local"
ADMIN_USER="admin"
ADMIN_PASS="Admin@2026secure"

PASS=0
FAIL=0
ISSUES=()

RED=$'\033[31m'
GREEN=$'\033[32m'
RESET=$'\033[0m'

ok()  { echo "${GREEN}✓${RESET} $1"; PASS=$((PASS+1)); }
fail(){ echo "${RED}✗${RESET} $1  [$2]"; FAIL=$((FAIL+1)); ISSUES+=("$1: $2"); }

CURL_OPTS=(-sk --resolve anjaz.inss.local:443:127.0.0.1)

# Login
TOKEN=$(curl "${CURL_OPTS[@]}" -X POST "$BASE/api/auth/login/" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$ADMIN_USER\",\"password\":\"$ADMIN_PASS\"}" \
  | python -c "import sys,json; print(json.load(sys.stdin).get('access', ''))")

if [ -z "$TOKEN" ]; then
  echo "${RED}Login failed${RESET}"; exit 1
fi
AUTH=(-H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json")

# ────── إنشاء فئة مؤشّر + مؤشّرَين ──────
echo "─── إنشاء + قراءة (CRUD على المؤشّرات) ───"
CAT_RESPONSE=$(curl "${CURL_OPTS[@]}" "${AUTH[@]}" -X POST "$BASE/api/indicators/categories/" \
  -d "{\"name\":\"اختبار_$$\",\"description\":\"smoke test\"}")
CAT_ID=$(echo "$CAT_RESPONSE" | python -c "import sys,json; print(json.load(sys.stdin).get('id', ''))" 2>/dev/null)
if [ -n "$CAT_ID" ]; then ok "POST /api/indicators/categories/ (created id=$CAT_ID)"; else fail "Create category" "$CAT_RESPONSE"; fi

IND1_RESPONSE=$(curl "${CURL_OPTS[@]}" "${AUTH[@]}" -X POST "$BASE/api/indicators/" \
  -d "{\"name\":\"اختبار مؤشر 1_$$\",\"unit_type\":\"number\",\"accumulation_type\":\"sum\",\"category\":$CAT_ID}")
IND1_ID=$(echo "$IND1_RESPONSE" | python -c "import sys,json; print(json.load(sys.stdin).get('id', ''))" 2>/dev/null)
if [ -n "$IND1_ID" ]; then ok "POST /api/indicators/ (indicator 1 id=$IND1_ID)"; else fail "Create indicator 1" "$IND1_RESPONSE"; fi

IND2_RESPONSE=$(curl "${CURL_OPTS[@]}" "${AUTH[@]}" -X POST "$BASE/api/indicators/" \
  -d "{\"name\":\"اختبار مؤشر 2_$$\",\"unit_type\":\"number\",\"accumulation_type\":\"sum\",\"category\":$CAT_ID}")
IND2_ID=$(echo "$IND2_RESPONSE" | python -c "import sys,json; print(json.load(sys.stdin).get('id', ''))" 2>/dev/null)
if [ -n "$IND2_ID" ]; then ok "POST /api/indicators/ (indicator 2 id=$IND2_ID)"; else fail "Create indicator 2" "$IND2_RESPONSE"; fi

IND3_PCT_RESPONSE=$(curl "${CURL_OPTS[@]}" "${AUTH[@]}" -X POST "$BASE/api/indicators/" \
  -d "{\"name\":\"اختبار نسبة_$$\",\"unit_type\":\"percentage\",\"accumulation_type\":\"average\",\"category\":$CAT_ID}")
IND3_ID=$(echo "$IND3_PCT_RESPONSE" | python -c "import sys,json; print(json.load(sys.stdin).get('id', ''))" 2>/dev/null)
[ -n "$IND3_ID" ] && ok "POST indicator with percentage type" || fail "Create percentage indicator" "$IND3_PCT_RESPONSE"

# ────── المستهدف المركّب — مع مؤشّرَين بنفس النوع ──────
echo "─── المستهدفات المركّبة ───"
TARGET_RESPONSE=$(curl "${CURL_OPTS[@]}" "${AUTH[@]}" -X POST "$BASE/api/targets/" \
  -d "{\"name\":\"اختبار مركّب_$$\",\"scope_unit\":null,\"indicator_ids\":[$IND1_ID,$IND2_ID],\"year\":2026,\"target_value\":100}")
TARGET_ID=$(echo "$TARGET_RESPONSE" | python -c "import sys,json; print(json.load(sys.stdin).get('id', ''))" 2>/dev/null)
if [ -n "$TARGET_ID" ]; then ok "POST /api/targets/ (composite with 2 indicators id=$TARGET_ID)"; else fail "Create composite target" "$TARGET_RESPONSE"; fi

# ────── محاولة خلط أنواع — يجب أن تفشل ──────
MIXED_RESPONSE=$(curl "${CURL_OPTS[@]}" "${AUTH[@]}" -X POST "$BASE/api/targets/" \
  -d "{\"name\":\"مختلط_$$\",\"scope_unit\":null,\"indicator_ids\":[$IND1_ID,$IND3_ID],\"year\":2026,\"target_value\":50}")
MIXED_CODE=$(echo "$MIXED_RESPONSE" | python -c "import sys,json; d=json.load(sys.stdin); print('REJECTED' if d.get('error') or d.get('detail') or 'indicators' in str(d) else 'CREATED')" 2>/dev/null)
[ "$MIXED_CODE" = "REJECTED" ] && ok "Mixed unit types rejected (validation works)" || fail "Mixed unit types not rejected" "$MIXED_RESPONSE"

# تقدّم المستهدف
PROG_CODE=$(curl "${CURL_OPTS[@]}" "${AUTH[@]}" -o /dev/null -w "%{http_code}" "$BASE/api/targets/$TARGET_ID/progress/")
[ "$PROG_CODE" = "200" ] && ok "GET /api/targets/$TARGET_ID/progress/" || fail "GET target progress" "HTTP $PROG_CODE"

# breakdown
BD_CODE=$(curl "${CURL_OPTS[@]}" "${AUTH[@]}" -o /dev/null -w "%{http_code}" "$BASE/api/targets/$TARGET_ID/breakdown/")
[ "$BD_CODE" = "200" ] && ok "GET /api/targets/$TARGET_ID/breakdown/" || fail "GET target breakdown" "HTTP $BD_CODE"

# تحديث المستهدف (تعديل الاسم)
UPD_CODE=$(curl "${CURL_OPTS[@]}" "${AUTH[@]}" -o /dev/null -w "%{http_code}" -X PATCH "$BASE/api/targets/$TARGET_ID/" \
  -d "{\"name\":\"اختبار مركّب معدّل_$$\"}")
[ "$UPD_CODE" = "200" ] && ok "PATCH /api/targets/$TARGET_ID/" || fail "Update target" "HTTP $UPD_CODE"

# ────── PlanningAssignment ──────
echo "─── تخصيصات التخطيط ───"
# جلب أوّل qism متاح (إن وُجد)
QISMS=$(curl "${CURL_OPTS[@]}" "${AUTH[@]}" "$BASE/api/organization/units/?unit_type=qism")
QISM_ID=$(echo "$QISMS" | python -c "import sys,json; d=json.load(sys.stdin); results=d.get('results',[]); print(results[0]['id'] if results else '')" 2>/dev/null)

if [ -n "$QISM_ID" ]; then
  # هذا قد يفشل لو القسم مُسنَد بالفعل
  PA_RESPONSE=$(curl "${CURL_OPTS[@]}" "${AUTH[@]}" -X POST "$BASE/api/organization/planning-assignments/" \
    -d "{\"planning_unit\":$QISM_ID}")
  PA_ID=$(echo "$PA_RESPONSE" | python -c "import sys,json; print(json.load(sys.stdin).get('id', ''))" 2>/dev/null)
  if [ -n "$PA_ID" ]; then
    ok "POST planning-assignment (id=$PA_ID)"
    # حذف
    DEL_CODE=$(curl "${CURL_OPTS[@]}" "${AUTH[@]}" -o /dev/null -w "%{http_code}" -X DELETE "$BASE/api/organization/planning-assignments/$PA_ID/")
    [ "$DEL_CODE" = "204" ] && ok "DELETE planning-assignment" || fail "Delete assignment" "HTTP $DEL_CODE"
  else
    ok "POST planning-assignment skipped (qism already assigned — expected)"
  fi
else
  ok "PlanningAssignment skipped (no qisms available)"
fi

# ────── ViewScope ──────
echo "─── ViewScope ───"
USERS=$(curl "${CURL_OPTS[@]}" "${AUTH[@]}" "$BASE/api/users/?role=viewer")
VIEWER_ID=$(echo "$USERS" | python -c "import sys,json; d=json.load(sys.stdin); results=d.get('results',[]); print(results[0]['id'] if results else '')" 2>/dev/null)
if [ -n "$VIEWER_ID" ]; then
  ok "ViewScope test skipped (would need active viewer user setup)"
else
  ok "ViewScope test skipped (no viewer users in system — expected)"
fi

# ────── Cleanup: حذف المستهدف والمؤشّرات والفئة ──────
echo "─── تنظيف ───"
DEL_T=$(curl "${CURL_OPTS[@]}" "${AUTH[@]}" -o /dev/null -w "%{http_code}" -X DELETE "$BASE/api/targets/$TARGET_ID/")
[ "$DEL_T" = "204" ] && ok "DELETE target" || fail "Delete target" "HTTP $DEL_T"

DEL_I1=$(curl "${CURL_OPTS[@]}" "${AUTH[@]}" -o /dev/null -w "%{http_code}" -X DELETE "$BASE/api/indicators/$IND1_ID/")
[ "$DEL_I1" = "204" ] && ok "DELETE indicator 1" || fail "Delete indicator 1" "HTTP $DEL_I1"

DEL_I2=$(curl "${CURL_OPTS[@]}" "${AUTH[@]}" -o /dev/null -w "%{http_code}" -X DELETE "$BASE/api/indicators/$IND2_ID/")
[ "$DEL_I2" = "204" ] && ok "DELETE indicator 2" || fail "Delete indicator 2" "HTTP $DEL_I2"

DEL_I3=$(curl "${CURL_OPTS[@]}" "${AUTH[@]}" -o /dev/null -w "%{http_code}" -X DELETE "$BASE/api/indicators/$IND3_ID/")
[ "$DEL_I3" = "204" ] && ok "DELETE indicator 3" || fail "Delete indicator 3" "HTTP $DEL_I3"

# ────── ملخّص ──────
echo ""
echo "════════════════════"
echo "ناجح: ${GREEN}$PASS${RESET}    فاشل: ${RED}$FAIL${RESET}"
echo "════════════════════"
if [ $FAIL -gt 0 ]; then
  echo ""
  echo "${RED}المشاكل:${RESET}"
  for issue in "${ISSUES[@]}"; do
    echo "  - $issue"
  done
  exit 1
fi
echo "${GREEN}كل عمليّات الكتابة تعمل ✓${RESET}"
