from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import OrganizationUnit
from .permissions import IsStatisticsAdminOrReadOnly
from .serializers import OrganizationUnitSerializer, OrganizationTreeSerializer
from .services import OrganizationService


class OrganizationUnitViewSet(viewsets.ModelViewSet):
    serializer_class = OrganizationUnitSerializer
    permission_classes = [IsStatisticsAdminOrReadOnly]
    filterset_fields = ['unit_type', 'qism_role', 'parent', 'is_active']
    search_fields = ['name', 'code']

    def get_queryset(self):
        queryset = OrganizationUnit.objects.select_related('parent')
        if self.request.user.role != 'statistics_admin':
            queryset = queryset.for_user_scope(self.request.user)
        return queryset

    def perform_create(self, serializer):
        OrganizationService.create_unit(serializer.validated_data)

    def perform_destroy(self, instance):
        OrganizationService.deactivate_unit(instance)

    @action(detail=False, methods=['get'], url_path='tree')
    def tree(self, request):
        """الحصول على شجرة الهيكل التنظيمي"""
        root_units = OrganizationService.get_tree(request.user)
        serializer = OrganizationTreeSerializer(root_units, many=True)
        return Response(serializer.data)
