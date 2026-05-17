from rest_framework import viewsets

from .models import Indicator, IndicatorCategory
from .permissions import IsStatisticsAdminOrReadOnly
from .serializers import IndicatorCategorySerializer, IndicatorSerializer
from .services import IndicatorCategoryService, IndicatorService


class IndicatorCategoryViewSet(viewsets.ModelViewSet):
    """واجهة برمجية لإدارة تصنيفات المؤشرات"""
    serializer_class = IndicatorCategorySerializer
    permission_classes = [IsStatisticsAdminOrReadOnly]
    filterset_fields = ['is_active']
    search_fields = ['name']

    def get_queryset(self):
        return IndicatorCategory.objects.all().order_by('name')

    def perform_create(self, serializer):
        # نُعيد ربط الـ instance المُنشأ بالـ serializer ليُعاد في الرد
        # (وإلّا DRF يرسل request data فقط بدون الـ id).
        serializer.instance = IndicatorCategoryService.create_category(
            serializer.validated_data
        )

    def perform_update(self, serializer):
        serializer.instance = IndicatorCategoryService.update_category(
            self.get_object(), serializer.validated_data
        )

    def perform_destroy(self, instance):
        IndicatorCategoryService.deactivate_category(instance)


class IndicatorViewSet(viewsets.ModelViewSet):
    """واجهة برمجية لإدارة المؤشرات"""
    serializer_class = IndicatorSerializer
    permission_classes = [IsStatisticsAdminOrReadOnly]
    filterset_fields = ['category', 'unit_type', 'is_active']
    search_fields = ['name', 'description']

    def get_queryset(self):
        return Indicator.objects.select_related(
            'category', 'created_by'
        ).order_by('-created_at')

    def perform_create(self, serializer):
        serializer.instance = IndicatorService.create_indicator(
            serializer.validated_data, created_by=self.request.user,
        )

    def perform_update(self, serializer):
        serializer.instance = IndicatorService.update_indicator(
            self.get_object(), serializer.validated_data, actor=self.request.user,
        )

    def perform_destroy(self, instance):
        IndicatorService.deactivate_indicator(instance, actor=self.request.user)
