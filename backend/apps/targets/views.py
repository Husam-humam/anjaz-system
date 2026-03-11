from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.organization.permissions import IsStatisticsAdminOrReadOnly
from .models import Target
from .serializers import TargetSerializer
from .services import TargetService


class TargetViewSet(viewsets.ModelViewSet):
    serializer_class = TargetSerializer
    permission_classes = [IsAuthenticated, IsStatisticsAdminOrReadOnly]
    filterset_fields = ['qism', 'indicator', 'year']

    def get_queryset(self):
        queryset = Target.objects.select_related('qism', 'indicator', 'set_by')
        user = self.request.user
        if user.role == 'statistics_admin':
            return queryset
        elif user.role == 'planning_section':
            # يرى مستهدفات أقسام مديريته
            parent = user.unit.parent
            if parent:
                descendant_ids = parent.get_descendants().values_list('id', flat=True)
                return queryset.filter(qism_id__in=descendant_ids)
            return queryset.none()
        else:
            # مدير القسم يرى مستهدفات قسمه فقط
            return queryset.filter(qism=user.unit)

    def perform_create(self, serializer):
        TargetService.create_target(serializer.validated_data, self.request.user)

    def perform_update(self, serializer):
        TargetService.update_target(self.get_object(), serializer.validated_data)
