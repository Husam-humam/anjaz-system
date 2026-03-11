"""
مسارات URL لتطبيق المنجزات — المنجزات النوعية.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import QualitativeViewSet

router = DefaultRouter()
router.register('', QualitativeViewSet, basename='qualitative')

urlpatterns = [
    path('', include(router.urls)),
]
