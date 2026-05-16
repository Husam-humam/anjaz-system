from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ExternalUnitTypeMappingViewSet,
    OrganizationUnitViewSet,
    PlanningAssignmentViewSet,
    ViewScopeViewSet,
)

router = DefaultRouter()
router.register('units', OrganizationUnitViewSet, basename='organization-unit')
router.register(
    'planning-assignments',
    PlanningAssignmentViewSet,
    basename='planning-assignment',
)
router.register('view-scopes', ViewScopeViewSet, basename='view-scope')
router.register(
    'unit-type-mappings',
    ExternalUnitTypeMappingViewSet,
    basename='unit-type-mapping',
)

urlpatterns = [
    path('', include(router.urls)),
]
