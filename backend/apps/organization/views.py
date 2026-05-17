from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    ExternalUnitTypeMapping,
    OrganizationUnit,
    PlanningAssignment,
    SupervisedUnit,
    ViewScope,
)
from .permissions import IsStatisticsAdmin, IsStatisticsAdminOrReadOnly
from .serializers import (
    ExternalUnitTypeMappingSerializer,
    OrganizationUnitSerializer,
    OrganizationTreeSerializer,
    PlanningAssignmentSerializer,
    PlanningAssignmentWriteSerializer,
    ViewScopeSerializer,
    ViewScopeWriteSerializer,
)
from .services import OrganizationService
from .sync_service import OrganizationSyncService


class OrganizationUnitViewSet(viewsets.ModelViewSet):
    serializer_class = OrganizationUnitSerializer
    permission_classes = [IsStatisticsAdminOrReadOnly]
    filterset_fields = ['unit_type', 'parent', 'is_active']
    search_fields = ['name', 'code']

    def get_queryset(self):
        queryset = OrganizationUnit.objects.select_related('parent')
        if self.request.user.role != 'statistics_admin':
            queryset = queryset.for_user_scope(self.request.user)
        return queryset

    def perform_create(self, serializer):
        serializer.instance = OrganizationService.create_unit(
            serializer.validated_data
        )

    def perform_destroy(self, instance):
        OrganizationService.deactivate_unit(instance)

    @action(detail=False, methods=['get'], url_path='tree')
    def tree(self, request):
        """الحصول على شجرة الهيكل التنظيمي"""
        root_units = OrganizationService.get_tree(request.user)
        serializer = OrganizationTreeSerializer(root_units, many=True)
        return Response(serializer.data)

    @action(
        detail=False,
        methods=['post'],
        url_path='sync',
        permission_classes=[IsStatisticsAdmin],
    )
    def sync_from_external(self, request):
        """
        مزامنة الهيكل التنظيمي من النظام الخارجي.
        يُستدعى تلقائياً عند فتح صفحة التشكيلات + يدوياً عبر زر «مزامنة».
        """
        dry_run = str(request.query_params.get('dry_run', '')).lower() in ('1', 'true', 'yes')
        try:
            report = OrganizationSyncService().sync(dry_run=dry_run)
        except Exception as exc:  # noqa: BLE001
            return Response(
                {'detail': f'فشل الاتصال بالنظام الخارجي: {exc}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response({
            'created': report.created,
            'updated': report.updated,
            'deactivated': report.deactivated,
            'skipped_unknown_type': report.skipped_unknown_type,
            'errors': report.errors,
            'summary': report.summary(),
            'started_at': report.started_at,
            'finished_at': report.finished_at,
            'dry_run': report.dry_run,
        })


class PlanningAssignmentViewSet(viewsets.ModelViewSet):
    """
    إدارة تخصيصات أقسام التخطيط — للأدمن فقط.
    """
    permission_classes = [IsStatisticsAdmin]
    queryset = PlanningAssignment.objects.select_related(
        'planning_unit', 'context_parent',
    ).prefetch_related('supervised_units__unit')

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return PlanningAssignmentWriteSerializer
        return PlanningAssignmentSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def create(self, request, *args, **kwargs):
        """نُرجع البيانات الكاملة (Read serializer) بعد الإنشاء — وليس فقط حقول
        الكتابة (وإلّا الفرونت لن يحصل على id ولا اسم الوحدة، إلخ)."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        read_serializer = PlanningAssignmentSerializer(serializer.instance)
        headers = self.get_success_headers(read_serializer.data)
        return Response(
            read_serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=partial,
        )
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        read_serializer = PlanningAssignmentSerializer(serializer.instance)
        return Response(read_serializer.data)

    @action(detail=True, methods=['post'], url_path='supervised-units')
    def add_supervised_unit(self, request, pk=None):
        """إضافة قسم تحت إشراف تخصيص التخطيط."""
        assignment = self.get_object()
        unit_id = request.data.get('unit')
        if not unit_id:
            return Response(
                {'unit': 'الوحدة مطلوبة.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            unit = OrganizationUnit.objects.get(pk=unit_id)
        except OrganizationUnit.DoesNotExist:
            return Response(
                {'unit': 'الوحدة غير موجودة.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        # SupervisedUnit.unit هو OneToOne — نمنع التكرار بصمت
        if hasattr(unit, 'supervisor_link'):
            return Response(
                {'unit': 'هذه الوحدة مُشرَف عليها بالفعل من قِبَل تخصيص آخر.'},
                status=status.HTTP_409_CONFLICT,
            )
        link = SupervisedUnit(assignment=assignment, unit=unit)
        link.full_clean()
        link.save()
        return Response(
            {
                'id': link.id,
                'unit': unit.id,
                'unit_name': unit.name,
                'unit_code': unit.code,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=['delete'],
        url_path='supervised-units/(?P<unit_id>[^/.]+)',
    )
    def remove_supervised_unit(self, request, pk=None, unit_id=None):
        """إزالة قسم من إشراف تخصيص التخطيط."""
        assignment = self.get_object()
        try:
            link = SupervisedUnit.objects.get(
                assignment=assignment, unit_id=unit_id,
            )
        except SupervisedUnit.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        link.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ViewScopeViewSet(viewsets.ModelViewSet):
    """
    إدارة نطاقات الاطّلاع للمستخدمين (viewer أو planner موسَّع) — للأدمن فقط.
    """
    permission_classes = [IsStatisticsAdmin]
    queryset = ViewScope.objects.select_related('user').prefetch_related('viewable_units')

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return ViewScopeWriteSerializer
        return ViewScopeSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def create(self, request, *args, **kwargs):
        """نُرجع Read serializer بعد الإنشاء (يتضمّن id + viewable_units_detail)."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        read_serializer = ViewScopeSerializer(serializer.instance)
        headers = self.get_success_headers(read_serializer.data)
        return Response(
            read_serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=partial,
        )
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        read_serializer = ViewScopeSerializer(serializer.instance)
        return Response(read_serializer.data)


class ExternalUnitTypeMappingViewSet(viewsets.ModelViewSet):
    """
    إدارة تطابق أنواع الوحدات الخارجيّة → داخليّة.
    يسمح بالـ list / patch فقط — لا create/delete (الجدول يُملأ آلياً عبر
    `refresh` action).
    """
    permission_classes = [IsStatisticsAdmin]
    queryset = ExternalUnitTypeMapping.objects.all().order_by('external_type_name')
    serializer_class = ExternalUnitTypeMappingSerializer
    http_method_names = ['get', 'patch', 'post', 'head', 'options']

    @action(
        detail=False,
        methods=['post'],
        url_path='refresh',
    )
    def refresh_from_external(self, request):
        """
        يجلب أنواع الوحدات من النظام الخارجي ويُنشئ سطراً جديداً في الجدول
        لكل نوع غير معروف. يُرجع الحقول كاملة + التقرير.
        """
        from .sync_service import OrganizationSyncService
        try:
            report = OrganizationSyncService().refresh_unit_type_mappings()
        except Exception as exc:  # noqa: BLE001
            return Response(
                {'detail': f'فشل جلب أنواع الوحدات: {exc}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response({
            **report,
            'mappings': ExternalUnitTypeMappingSerializer(
                ExternalUnitTypeMapping.objects.all().order_by('external_type_name'),
                many=True,
            ).data,
        })
