"""
عميل النظام الخارجي للهيكل التنظيمي.

يُستخدم لجلب شجرة الوحدات التنظيمية من النظام المركزي (مصدر الحقيقة)
عبر API key authentication. ترجع البيانات في صورة dicts مطابقة للعقد
كما يصفها EXTERNAL_API_DOCUMENTATION.md.

التصميم:
- thin wrapper حول `requests` مع timeout وretry محدودَين
- يرفع استثناءات داخل النوع `ExternalOrgError` لتسهيل المعالجة
- لا يُعدِّل أي بيانات DB — مهمّته جلب فقط
- لا يحتفظ بحالة بين الاستدعاءات (stateless) — آمن للاستخدام المتعدّد
"""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urljoin

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class ExternalOrgError(Exception):
    """خطأ عامّ من النظام الخارجي للهيكل التنظيمي."""


class ExternalOrgNotConfigured(ExternalOrgError):
    """عنوان النظام الخارجي أو الـ API key غير مُهيَّأ في الإعدادات."""


class ExternalOrgUnavailable(ExternalOrgError):
    """النظام الخارجي لم يُجِب أو أعاد خطأ HTTP."""


class ExternalOrgClient:
    """
    عميل بسيط للوصول إلى نظام الهيكل التنظيمي الخارجي.

    الاستخدام:
        client = ExternalOrgClient()
        tree = client.get_units_tree()

    يقرأ الإعدادات تلقائياً من Django settings:
    - settings.EXTERNAL_ORG_API_URL  (مثلاً: http://host/api/external/)
    - settings.EXTERNAL_ORG_API_KEY
    - settings.EXTERNAL_ORG_API_TIMEOUT  (بالثواني)
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: int | None = None,
    ):
        # نفرّق بين None (افتراضي = استخدم settings) و '' (صريح = override)
        if base_url is None:
            base_url = getattr(settings, 'EXTERNAL_ORG_API_URL', '') or ''
        if api_key is None:
            api_key = getattr(settings, 'EXTERNAL_ORG_API_KEY', '') or ''
        if timeout is None:
            timeout = getattr(settings, 'EXTERNAL_ORG_API_TIMEOUT', 15)

        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout

        if self.base_url and not self.base_url.endswith('/'):
            # نضمن انتهاء base_url بـ / حتى يعمل urljoin بشكل صحيح
            self.base_url = self.base_url + '/'

    # ─── الفحوصات الأساسيّة ──────────────────────

    def is_configured(self) -> bool:
        """يفحص اكتمال الإعدادات قبل أي استدعاء."""
        return bool(self.base_url) and bool(self.api_key)

    def assert_configured(self) -> None:
        if not self.is_configured():
            raise ExternalOrgNotConfigured(
                'لم يتم تهيئة عنوان النظام الخارجي (EXTERNAL_ORG_API_URL) '
                'أو مفتاح API (EXTERNAL_ORG_API_KEY). يرجى إكمال الإعدادات '
                'في ملف .env قبل تشغيل المزامنة.'
            )

    # ─── الاستدعاءات ────────────────────────────

    def get_status(self) -> dict[str, Any]:
        """
        GET /status/ — صحّة النظام الخارجي.
        مفيد لاختبار الاتصال قبل المزامنة الفعليّة.
        """
        return self._get('status/')

    def get_unit_types(self) -> list[dict[str, Any]]:
        """
        GET /reference/unit-types/ — أنواع الوحدات (دائرة/مديرية/قسم/...).
        نستخدمها لبناء الخريطة من external unit_type → unit_type المحلي.
        """
        data = self._get('reference/unit-types/')
        # الاستجابة بشكل {"results": [...], "count": N}
        if isinstance(data, dict):
            return data.get('results', [])
        return data or []

    def get_units_tree(
        self, max_depth: int = 10, active_only: bool = False
    ) -> list[dict[str, Any]]:
        """
        GET /units/tree/ — الشجرة الكاملة في طلب واحد.

        ترجع قائمة عقد جذريّة، كل عقدة لها `children`. كل عقدة تحتوي
        على الأقلّ: id, name, code, is_main_unit, level, children_count, children.

        ملاحظة مهمّة عن `is_active`:
        - `is_active=true` → نشطة فقط
        - `is_active=false` → معطّلة فقط (تصفية مُعكوسة!)
        - عدم تمريره → كل الوحدات (نشطة ومعطّلة)
        افتراضياً نستدعيه بدون فلتر لجلب الكل.
        """
        params: dict[str, Any] = {'max_depth': max_depth}
        if active_only:
            params['is_active'] = 'true'
        # وإلا: لا نُمرّر is_active لجلب الكل (المنطق الصحيح للمزامنة)

        data = self._get('units/tree/', params=params)
        if isinstance(data, dict):
            return data.get('tree', [])
        return data or []

    def get_unit_detail(self, unit_id: int) -> dict[str, Any]:
        """
        GET /units/{id}/ — تفاصيل وحدة واحدة (detail=full).
        يحتوي على unit_type_id, unit_type_name, parent_id, parent_name وغيرها.
        """
        return self._get(f'units/{int(unit_id)}/')

    def get_units_list(
        self, detail: str = 'full', page: int = 1, page_size: int = 100
    ) -> dict[str, Any]:
        """
        GET /units/?detail=full — قائمة مُسطَّحة بالوحدات (مُرقّمة).
        نستخدمها لجلب `unit_type_name` لكل وحدة (الـ tree endpoint
        لا يُرجع unit_type_name). ترجع dict كامل بـ results/count/page.
        """
        return self._get(
            'units/',
            params={'detail': detail, 'page': page, 'page_size': page_size},
        )

    # ─── طبقة HTTP منخفضة المستوى ─────────────────

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """
        طلب GET مُغلَّف مع headers و authentication و timeout.
        يحوّل أخطاء الشبكة إلى ExternalOrgUnavailable برسالة عربية.
        """
        self.assert_configured()
        url = urljoin(self.base_url, path.lstrip('/'))
        headers = {
            'Authorization': f'ApiKey {self.api_key}',
            'Accept': 'application/json',
        }
        # دعم Host header مخصّص عند الحاجة (مثلاً النظام الخارجي يقيد ALLOWED_HOSTS
        # على localhost لكنّ docker يصل عبر host.docker.internal).
        host_override = getattr(settings, 'EXTERNAL_ORG_HOST_HEADER', '') or ''
        if host_override:
            headers['Host'] = host_override
        try:
            response = requests.get(
                url, headers=headers, params=params, timeout=self.timeout
            )
        except requests.Timeout as exc:
            raise ExternalOrgUnavailable(
                f'انتهت مهلة الاتصال بالنظام الخارجي ({self.timeout} ثانية).'
            ) from exc
        except requests.ConnectionError as exc:
            raise ExternalOrgUnavailable(
                f'تعذّر الاتصال بالنظام الخارجي على العنوان {self.base_url}'
            ) from exc
        except requests.RequestException as exc:
            raise ExternalOrgUnavailable(
                f'خطأ في طلب النظام الخارجي: {exc}'
            ) from exc

        if response.status_code == 401:
            raise ExternalOrgUnavailable(
                'مفتاح API غير صالح للنظام الخارجي (401 Unauthorized).'
            )
        if response.status_code == 403:
            raise ExternalOrgUnavailable(
                'الوصول مرفوض من النظام الخارجي (403). تحقّق من صلاحيات الـ API key أو الـ IP المسموح.'
            )
        if response.status_code == 429:
            raise ExternalOrgUnavailable(
                'تم تجاوز الحدّ الأقصى لطلبات النظام الخارجي (429). يرجى المحاولة لاحقاً.'
            )
        if response.status_code >= 500:
            raise ExternalOrgUnavailable(
                f'النظام الخارجي أعاد خطأ خادم ({response.status_code}). يُرجى المحاولة لاحقاً.'
            )
        if not response.ok:
            raise ExternalOrgUnavailable(
                f'النظام الخارجي أعاد استجابة غير ناجحة ({response.status_code}): '
                f'{response.text[:200]}'
            )

        try:
            return response.json()
        except ValueError as exc:
            raise ExternalOrgUnavailable(
                'استجابة النظام الخارجي ليست JSON صالحاً.'
            ) from exc
