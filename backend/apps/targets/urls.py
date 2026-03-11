from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import TargetViewSet

router = DefaultRouter()
router.register('', TargetViewSet, basename='target')

urlpatterns = [
    path('', include(router.urls)),
]
