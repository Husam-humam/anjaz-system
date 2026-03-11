"""
مسارات URL لتطبيق المنجزات — الفترات الأسبوعية.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import WeeklyPeriodViewSet

router = DefaultRouter()
router.register('', WeeklyPeriodViewSet, basename='period')

urlpatterns = [
    path('', include(router.urls)),
]
