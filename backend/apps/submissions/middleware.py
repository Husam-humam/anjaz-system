"""
Middleware للفحص اليومي التلقائي للأسابيع.
يستدعي PeriodAutoService.ensure_current_period مرة واحدة في اليوم
بغضّ النظر عن عدد الطلبات — باستخدام cache بسيط.
"""
import logging

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

# مفتاح الـ cache يتغيّر يومياً (بحيث يُنفَّذ الفحص مرة واحدة كل يوم)
CACHE_KEY_PREFIX = 'period_auto_checked'
CACHE_TIMEOUT = 60 * 60 * 25  # 25 ساعة (هامش أمان)


class PeriodAutoCheckMiddleware:
    """
    Middleware خفيف يتحقّق من وجود الأسبوع الحالي مرة واحدة يومياً.
    - يعمل على أول طلب مصادق عليه في اليوم
    - يستخدم cache لتجنّب التنفيذ المتكرّر (أول طلب فقط في اليوم يُنفّذ الفحص)
    - لا يعطّل الطلب أبداً — يلتقط كل الأخطاء ويُسجّلها
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        self._maybe_ensure_period()
        return self.get_response(request)

    def _maybe_ensure_period(self):
        try:
            today = timezone.localdate()
            cache_key = f'{CACHE_KEY_PREFIX}:{today.isoformat()}'
            if cache.get(cache_key):
                return  # تمّ الفحص اليوم — لا حاجة لإعادته

            # نضع العلامة أولاً لتجنّب الطلبات المتسابقة
            cache.set(cache_key, True, CACHE_TIMEOUT)

            from .services import PeriodAutoService
            result = PeriodAutoService.ensure_current_period()

            if result.get('created'):
                logger.info(
                    f"[PeriodAutoCheck] تم إنشاء الأسبوع الحالي تلقائياً: "
                    f"{result['created'].week_number}/{result['created'].year}"
                )
            if result.get('closed'):
                logger.info(
                    f"[PeriodAutoCheck] تم إغلاق {len(result['closed'])} فترة منتهية"
                )
        except Exception:
            logger.warning("[PeriodAutoCheck] فشل الفحص اليومي", exc_info=True)
