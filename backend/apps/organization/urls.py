from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import OrganizationUnitViewSet

router = DefaultRouter()
router.register('units', OrganizationUnitViewSet, basename='organization-unit')

urlpatterns = [
    path('', include(router.urls)),
]
