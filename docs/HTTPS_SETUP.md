# إعداد HTTPS في بيئة التطوير

النظام يستخدم شهادة SSL داخليّة (wildcard لـ `*.inss.local`) صادرة من `Win-CA` (شهادة الـ root الخاصّة بـ AD CS داخل النطاق `fin.local`).

## الملفات في `ssl/`

| الملفّ | الوصف |
|---|---|
| `wd.cer` | شهادة wildcard لـ `*.inss.local` (سارية حتى 2027-09-29) |
| `aw.key` | المفتاح الخاصّ (PEM PKCS#8) |
| `ca-wd.cer` | شهادة الـ root CA المُصدِرة (`Win-CA`، سارية حتى 2028) |

> ⚠️ **مهمّ**: `ssl/` يحتوي مفاتيح خاصّة — يجب إضافته إلى `.gitignore` قبل أي push. التحقّق لاحقاً.

## على جهاز التطوير (Windows) — خطوة لمرّة واحدة

### 1) إضافة الـ root CA إلى متجر الشهادات الموثوقة

افتح **PowerShell كمسؤول (Administrator)** ونفّذ:

```powershell
cd "d:\prog\inss\Achievement Tracking System"
Import-Certificate -FilePath ssl\ca-wd.cer -CertStoreLocation Cert:\LocalMachine\Root
```

بعدها كل المتصفّحات (Chrome / Edge / Firefox) ستثق في `*.inss.local`.

**للتحقّق**:
```powershell
Get-ChildItem Cert:\LocalMachine\Root | Where-Object Subject -like "*Win-CA*"
```
يجب أن تظهر السطر الذي ينتهي بـ `CN=Win-CA`.

### 2) إضافة سطر إلى ملفّ `hosts`

افتح PowerShell كمسؤول وأضف:

```powershell
Add-Content -Path C:\Windows\System32\drivers\etc\hosts -Value "`n127.0.0.1`tanjaz.inss.local"
```

أو يدوياً: حرّر `C:\Windows\System32\drivers\etc\hosts` بأي محرّر يعمل كـ admin، وأضف:
```
127.0.0.1    anjaz.inss.local
```

### 3) تشغيل النظام

```powershell
docker-compose up -d
```

وستجد:
- **الموقع**: <https://anjaz.inss.local>
- HTTP يُعاد توجيهه آلياً إلى HTTPS
- المتصفّح يعرض القفل الأخضر بدون تحذيرات (بعد الخطوة 1)

## للتراجع عن الخطوة 1 (إن أردت)

```powershell
Get-ChildItem Cert:\LocalMachine\Root | Where-Object Subject -like "*Win-CA*" | Remove-Item
```

## ملاحظات معماريّة

- **مفتاح PEM**: nginx يقرأ `aw.key` مباشرةً من volume mount. لا حاجة لتحويل صيغة.
- **TLS 1.2 + 1.3** فقط مع ciphers قويّة (راجع `nginx/nginx.conf`).
- **HSTS** مُفعَّل (`Strict-Transport-Security: max-age=31536000`) — حال تثبيت CA، المتصفّح يرفض HTTP لمدّة سنة.
- **خلف proxy**: Django يحترم `X-Forwarded-Proto` فيُعامل الطلب كـ HTTPS (cookies آمنة، JWT صحيح).

## للإنتاج

نفس الإعدادات تعمل كما هي — فقط تأكّد من:
1. الـ CA مُثبَّت على كل أجهزة المستخدمين (يُمكن نشره عبر Group Policy في النطاق `fin.local`)
2. الـ DNS يحلّ `anjaz.inss.local` إلى IP السيرفر (ليس 127.0.0.1)
3. غيّر `ALLOWED_HOSTS` و `CORS_ALLOWED_ORIGINS` و `CSRF_TRUSTED_ORIGINS` في `.env` لتشمل الـ FQDN الصحيح
