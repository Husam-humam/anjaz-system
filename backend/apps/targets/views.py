from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.organization.permissions import IsStatisticsAdminOrReadOnly

from .models import Target
from .serializers import TargetSerializer
from .services import TargetService


def _service_error_response(exc):
    """تحويل أخطاء الخدمة إلى استجابات HTTP موحّدة."""
    if isinstance(exc, DjangoPermissionDenied):
        return Response(
            {'error': True, 'message': str(exc) or 'ليس لديك صلاحية.',
             'code': 'PERMISSION_DENIED', 'details': {}},
            status=status.HTTP_403_FORBIDDEN,
        )
    details = {}
    message = 'بيانات غير صالحة.'
    if hasattr(exc, 'message_dict'):
        details = exc.message_dict
        for key, value in details.items():
            if key == 'message':
                continue
            if isinstance(value, list) and value:
                message = str(value[0])
                break
            if isinstance(value, str):
                message = value
                break
    elif hasattr(exc, 'messages') and exc.messages:
        message = str(exc.messages[0])
    else:
        message = str(exc)
    return Response(
        {'error': True, 'message': message,
         'code': 'VALIDATION_ERROR', 'details': details},
        status=status.HTTP_400_BAD_REQUEST,
    )


class TargetViewSet(viewsets.ModelViewSet):
    """
    إدارة المستهدفات المركّبة الهرميّة.

    CRUD محصور بمدير قسم الإحصاء. باقي المستخدمين قراءة فقط ضمن نطاقهم.
    """
    serializer_class = TargetSerializer
    permission_classes = [IsAuthenticated, IsStatisticsAdminOrReadOnly]
    filterset_fields = [
        'scope_unit', 'indicators', 'indicators__category', 'year',
    ]
    search_fields = [
        'name', 'scope_unit__name', 'scope_unit__code',
        'indicators__name', 'notes',
    ]

    def get_serializer_context(self):
        """يُفعّل حقل progress عند تمرير ?with_progress=true"""
        context = super().get_serializer_context()
        with_progress = self.request.query_params.get(
            'with_progress', ''
        ).lower() in ('true', '1', 'yes')
        context['with_progress'] = with_progress
        return context

    def get_queryset(self):
        queryset = Target.objects.select_related(
            'scope_unit', 'scope_unit__parent', 'set_by',
        ).prefetch_related(
            'indicators', 'indicators__category',
        ).order_by('-year', 'scope_unit__name', 'name')

        user = self.request.user

        # تصفية حسب الدور
        if user.role == 'statistics_admin':
            pass  # نطاق كامل
        elif user.role == 'planning_section':
            if user.unit and user.unit.parent:
                directorate = user.unit.parent
                descendant_ids = list(
                    directorate.get_descendants(include_self=True)
                    .values_list('id', flat=True)
                )
                ancestor_ids = list(
                    directorate.get_ancestors().values_list('id', flat=True)
                )
                visible_ids = set(descendant_ids) | set(ancestor_ids)
                queryset = queryset.filter(
                    Q(scope_unit__isnull=True) |
                    Q(scope_unit_id__in=visible_ids)
                )
            else:
                queryset = queryset.filter(scope_unit__isnull=True)
        elif user.role == 'section_manager':
            if user.unit:
                ancestors_ids = list(
                    user.unit.get_ancestors(include_self=False)
                    .values_list('id', flat=True)
                )
                queryset = queryset.filter(
                    Q(scope_unit__isnull=True) |
                    Q(scope_unit=user.unit) |
                    Q(scope_unit_id__in=ancestors_ids)
                )
            else:
                queryset = queryset.filter(scope_unit__isnull=True)
        elif user.role == 'viewer':
            # viewer: من خلال ViewScope (تُفحَص في طبقة أخرى لو احتجنا)
            return queryset.none()
        else:
            return queryset.none()

        # فلتر إضافي: scope_level (institution/daira/mudiriya/qism)
        scope_level = self.request.query_params.get('scope_level')
        if scope_level == 'institution':
            queryset = queryset.filter(scope_unit__isnull=True)
        elif scope_level in ('daira', 'mudiriya', 'qism'):
            queryset = queryset.filter(
                scope_unit__isnull=False,
                scope_unit__unit_type=scope_level,
            )

        return queryset.distinct()  # distinct بسبب JOIN على indicators

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        # نفصل indicators عن باقي الحقول (الـ service يطلبها كقائمة منفصلة)
        indicators = data.pop('indicators', [])
        indicator_ids = [ind.id for ind in indicators]
        try:
            target = TargetService.create_target(
                data=data,
                indicator_ids=indicator_ids,
                set_by=request.user,
            )
        except (DjangoValidationError, DjangoPermissionDenied) as exc:
            return _service_error_response(exc)
        output = self.get_serializer(target)
        return Response(output.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=partial
        )
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        indicators = data.pop('indicators', None)
        indicator_ids = (
            [ind.id for ind in indicators] if indicators is not None else None
        )
        try:
            target = TargetService.update_target(
                instance,
                data,
                indicator_ids=indicator_ids,
                actor=request.user,
            )
        except (DjangoValidationError, DjangoPermissionDenied) as exc:
            return _service_error_response(exc)
        output = self.get_serializer(target)
        return Response(output.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            TargetService.delete_target(instance, actor=request.user)
        except (DjangoValidationError, DjangoPermissionDenied) as exc:
            return _service_error_response(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['get'], url_path='progress')
    def progress(self, request, pk=None):
        """تقدّم المستهدف المركّب + تفصيل كل مكوّن."""
        target = self.get_object()
        try:
            data = TargetService.compute_target_progress(target)
        except Exception as exc:
            return _service_error_response(
                DjangoValidationError(str(exc))
            )
        data['target_id'] = target.id
        data['target_name'] = target.name
        data['scope_unit_name'] = (
            target.scope_unit.name if target.scope_unit_id else 'المؤسسة كاملة'
        )
        data['scope_level'] = target.scope_level
        data['year'] = target.year
        return Response(data)

    @action(detail=True, methods=['get'], url_path='breakdown')
    def breakdown(self, request, pk=None):
        """تفصيل مساهمة الوحدات في تحقيق المستهدف (شجرة هرميّة)."""
        target = self.get_object()
        if target.scope_unit_id and target.scope_unit.unit_type == 'qism':
            return Response({
                'target_id': target.id,
                'message': 'لا يوجد تفصيل لمستهدف قسم مفرد',
                'breakdown': [],
                'breakdown_type': 'none',
            })
        try:
            tree = TargetService.compute_scope_breakdown_tree(target)
            progress = TargetService.compute_target_progress(target)
        except Exception as exc:
            return _service_error_response(
                DjangoValidationError(str(exc))
            )
        return Response({
            'target_id': target.id,
            'target_name': target.name,
            'scope_unit_name': (
                target.scope_unit.name if target.scope_unit_id else 'المؤسسة كاملة'
            ),
            'scope_level': target.scope_level,
            'year': target.year,
            'target_value': target.target_value,
            'cumulative_value': progress['cumulative_value'],
            'progress_percentage': progress['progress_percentage'],
            'qisms_in_scope': progress['qisms_in_scope'],
            'components': progress['components'],
            'breakdown': tree,
            'breakdown_type': 'tree',
        })
