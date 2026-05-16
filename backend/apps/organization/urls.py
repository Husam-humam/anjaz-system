from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
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

urlpatterns = [
    path('', include(router.urls)),
]
