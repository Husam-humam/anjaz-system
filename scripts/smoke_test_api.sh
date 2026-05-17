#!/bin/bash
# Smoke test كل نهايات API الرئيسة على HTTPS عبر nginx.
# يُستدعى من root الـ repo: bash scripts/smoke_test_api.sh

set -u
BASE="https://anjaz.inss.local"
ADMIN_USER="admin"
ADMIN_PASS="Admin@2026secure"

PASS=0
FAIL=0
ISSUES=()

# لون أحمر/أخضر
RED=$'\033[31m'
GREEN=$'\033[32m'
YELLOW=$'\033[33m'
RESET=$'\033[0m'

ok()  { echo "${GREEN}✓${RESET} $1"; PASS=$((PASS+1)); }
fail(){ echo "${RED}✗${RESET} $1  [$2]"; FAIL=$((FAIL+1)); ISSUES+=("$1: $2"); }

# يتعامل مع certs الـ private CA (curl Schannel يفشل في CRL)
CURL_OPTS=(-sk --resolve anjaz.inss.local:443:127.0.0.1)

# ────── Login + احصل على token ──────
echo "─── المصادقة ───"
LOGIN_RESPONSE=$(curl "${CURL_OPTS[@]}" -X POST "$BASE/api/auth/login/" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$ADMIN_USER\",\"password\":\"$ADMIN_PASS\"}")
TOKEN=$(echo "$LOGIN_RESPONSE" | python -c "import sys,json; print(json.load(sys.stdin).get('access', ''))" 2>/dev/null)
REFRESH=$(echo "$LOGIN_RESPONSE" | python -c "import sys,json; print(json.load(sys.stdin).get('refresh', ''))" 2>/dev/null)

if [ -z "$TOKEN" ]; then
  echo "${RED}فشل تسجيل الدخول. الرد:${RESET} $LOGIN_RESPONSE"
  exit 1
fi
ok "Login (POST /api/auth/login/)"

AUTH=(-H "Authorization: Bearer $TOKEN")

# اختبار refresh token — يُلغي الـ refresh الأصلي ويُعطينا واحداً جديداً
# (rotation سياسة). نحتفظ بالجديد لاستخدامه في logout لاحقاً.
REFRESH_RESPONSE=$(curl "${CURL_OPTS[@]}" -X POST "$BASE/api/auth/token/refresh/" \
  -H "Content-Type: application/json" -d "{\"refresh\":\"$REFRESH\"}")
NEW_REFRESH=$(echo "$REFRESH_RESPONSE" | python -c "import sys,json; print(json.load(sys.stdin).get('refresh', ''))" 2>/dev/null)
if [ -n "$NEW_REFRESH" ]; then
  ok "Refresh token (POST /api/auth/token/refresh/)"
  REFRESH="$NEW_REFRESH"  # نستخدم الجديد في logout
else
  fail "Refresh token" "no new refresh in response"
fi

# Profile (me)
ME_CODE=$(curl "${CURL_OPTS[@]}" "${AUTH[@]}" -o /dev/null -w "%{http_code}" "$BASE/api/auth/me/")
[ "$ME_CODE" = "200" ] && ok "Get current user (GET /api/auth/me/)" || fail "GET me" "HTTP $ME_CODE"

# ────── Users ──────
echo "─── المستخدمون ───"
for endpoint in "users/"; do
  CODE=$(curl "${CURL_OPTS[@]}" "${AUTH[@]}" -o /dev/null -w "%{http_code}" "$BASE/api/$endpoint")
  [ "$CODE" = "200" ] && ok "GET /api/$endpoint" || fail "GET /api/$endpoint" "HTTP $CODE"
done

# ────── Organization ──────
echo "─── الهيكل التنظيمي ───"
for endpoint in "organization/units/" "organization/units/tree/" "organization/planning-assignments/" "organization/view-scopes/" "organization/unit-type-mappings/"; do
  CODE=$(curl "${CURL_OPTS[@]}" "${AUTH[@]}" -o /dev/null -w "%{http_code}" "$BASE/api/$endpoint")
  [ "$CODE" = "200" ] && ok "GET /api/$endpoint" || fail "GET /api/$endpoint" "HTTP $CODE"
done

# Sync endpoint
SYNC_CODE=$(curl "${CURL_OPTS[@]}" "${AUTH[@]}" -o /dev/null -w "%{http_code}" -X POST "$BASE/api/organization/units/sync/")
[ "$SYNC_CODE" = "200" ] && ok "POST /api/organization/units/sync/" || fail "POST sync" "HTTP $SYNC_CODE"

# Mapping refresh
REFRESH_MAP_CODE=$(curl "${CURL_OPTS[@]}" "${AUTH[@]}" -o /dev/null -w "%{http_code}" -X POST "$BASE/api/organization/unit-type-mappings/refresh/")
[ "$REFRESH_MAP_CODE" = "200" ] && ok "POST unit-type-mappings/refresh/" || fail "POST refresh mappings" "HTTP $REFRESH_MAP_CODE"

# ────── Indicators ──────
echo "─── المؤشّرات ───"
for endpoint in "indicators/categories/" "indicators/"; do
  CODE=$(curl "${CURL_OPTS[@]}" "${AUTH[@]}" -o /dev/null -w "%{http_code}" "$BASE/api/$endpoint")
  [ "$CODE" = "200" ] && ok "GET /api/$endpoint" || fail "GET /api/$endpoint" "HTTP $CODE"
done

# ────── Forms ──────
echo "─── قوالب الاستمارات ───"
CODE=$(curl "${CURL_OPTS[@]}" "${AUTH[@]}" -o /dev/null -w "%{http_code}" "$BASE/api/forms/templates/")
[ "$CODE" = "200" ] && ok "GET /api/forms/templates/" || fail "GET forms/templates" "HTTP $CODE"

# ────── Targets (composite) ──────
echo "─── المستهدفات المركّبة ───"
CODE=$(curl "${CURL_OPTS[@]}" "${AUTH[@]}" -o /dev/null -w "%{http_code}" "$BASE/api/targets/")
[ "$CODE" = "200" ] && ok "GET /api/targets/" || fail "GET targets" "HTTP $CODE"

# ────── Periods ──────
echo "─── الأسابيع ───"
CODE=$(curl "${CURL_OPTS[@]}" "${AUTH[@]}" -o /dev/null -w "%{http_code}" "$BASE/api/periods/")
[ "$CODE" = "200" ] && ok "GET /api/periods/" || fail "GET periods" "HTTP $CODE"

# ────── Submissions ──────
echo "─── المنجزات ───"
for endpoint in "submissions/" "qualitative/"; do
  CODE=$(curl "${CURL_OPTS[@]}" "${AUTH[@]}" -o /dev/null -w "%{http_code}" "$BASE/api/$endpoint")
  [ "$CODE" = "200" ] && ok "GET /api/$endpoint" || fail "GET /api/$endpoint" "HTTP $CODE"
done

# ────── Reports ──────
echo "─── التقارير ───"
YEAR=$(date +%Y)
for endpoint in "reports/summary/?year=$YEAR" "reports/periodic/?period_type=weekly&year=$YEAR" "reports/compliance/?year=$YEAR" "reports/qualitative/?year=$YEAR"; do
  CODE=$(curl "${CURL_OPTS[@]}" "${AUTH[@]}" -o /dev/null -w "%{http_code}" "$BASE/api/$endpoint")
  [ "$CODE" = "200" ] && ok "GET /api/$endpoint" || fail "GET /api/$endpoint" "HTTP $CODE"
done

# ────── Notifications ──────
echo "─── الإشعارات ───"
for endpoint in "notifications/" "notifications/unread_count/"; do
  CODE=$(curl "${CURL_OPTS[@]}" "${AUTH[@]}" -o /dev/null -w "%{http_code}" "$BASE/api/$endpoint")
  [ "$CODE" = "200" ] && ok "GET /api/$endpoint" || fail "GET /api/$endpoint" "HTTP $CODE"
done

# ────── Logout ──────
LOGOUT_CODE=$(curl "${CURL_OPTS[@]}" "${AUTH[@]}" -o /dev/null -w "%{http_code}" -X POST "$BASE/api/auth/logout/" \
  -H "Content-Type: application/json" -d "{\"refresh\":\"$REFRESH\"}")
[ "$LOGOUT_CODE" = "200" ] || [ "$LOGOUT_CODE" = "204" ] && ok "Logout (POST /api/auth/logout/)" || fail "Logout" "HTTP $LOGOUT_CODE"

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
echo "${GREEN}كل نهايات API تعمل بنجاح ✓${RESET}"
