from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import IndicatorCategoryViewSet, IndicatorViewSet

router = DefaultRouter()
router.register('categories', IndicatorCategoryViewSet, basename='indicator-category')
router.register('', IndicatorViewSet, basename='indicator')

urlpatterns = [
    path('', include(router.urls)),
]
