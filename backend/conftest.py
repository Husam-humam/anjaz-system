"""
Global pytest configuration for Anjaz System.
"""
import pytest
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def clear_throttle_cache():
    """
    تنظيف عدّاد throttle بين الاختبارات (يُستدعى صراحة عند الحاجة).

    DRF يستخدم Django cache لتتبّع عداد rate-limit لكل IP. في الاختبارات
    كل الطلبات تأتي من 127.0.0.1. لا نجعلها autouse لأنّ ذلك يمسح
    أيضاً أعلاماً حسّاسة (مثل PeriodAutoCheckMiddleware) ويُسبّب
    آثاراً جانبيّة. الاختبارات التي تحتاج عداداً نظيفاً تُضيفها كـ fixture.
    """
    from django.core.cache import cache
    # نمسح فقط مفاتيح throttle لتجنّب التأثير على middleware caches
    throttle_keys = [
        k for k in (getattr(cache, '_cache', {}) or {}).keys()
        if isinstance(k, str) and 'throttle_' in k
    ]
    for k in throttle_keys:
        cache.delete(k)
    yield
    for k in throttle_keys:
        cache.delete(k)
