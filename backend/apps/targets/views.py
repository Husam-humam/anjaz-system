from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.organization.models import OrganizationUnit
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
    إدارة المستهدفات الهرمية.

    المستهدفات تُدار فقط من قبل مدير قسم الإحصاء (CRUD).
    المستخدمون الآخرون يرون المستهدفات ضمن نطاقهم (للقراءة فقط).
    """
    serializer_class = TargetSerializer
    permission_classes = [IsAuthenticated, IsStatisticsAdminOrReadOnly]
    filterset_fields = [
        'scope_unit', 'indicator', 'indicator__category', 'year',
    ]
    search_fields = [
        'scope_unit__name', 'scope_unit__code',
        'indicator__name', 'notes',
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
            'scope_unit', 'scope_unit__parent',
            'indicator', 'indicator__category',
            'set_by',
        ).order_by('-year', 'indicator__category__name', 'scope_unit__name')

        user = self.request.user

        # تصفية حسب الدور
        if user.role == 'statistics_admin':
            pass  # نطاق كامل
        elif user.role == 'planning_section':
            # يرى المستهدفات التي تتقاطع مع مديريته:
            # - مستهدفات المؤسسة (scope_unit = null) — يراها الجميع
            # - مستهدفات مديريته أو دائرة مديريته أو أقسامها
            if user.unit and user.unit.parent:
                directorate = user.unit.parent
                descendant_ids = list(
                    directorate.get_descendants(include_self=True)
                    .values_list('id', flat=True)
                )
                # أضف أيضاً أجداد المديرية (لو كانت داخل دائرة) ليراها المخطط
                ancestor_ids = list(
                    directorate.get_ancestors().values_list('id', flat=True)
                )
                visible_ids = set(descendant_ids) | set(ancestor_ids)
                from django.db.models import Q
                queryset = queryset.filter(
                    Q(scope_unit__isnull=True) |
                    Q(scope_unit_id__in=visible_ids)
                )
            else:
                queryset = queryset.filter(scope_unit__isnull=True)
        elif user.role == 'section_manager':
            # مدير القسم يرى:
            # - مستهدفات قسمه المباشرة
            # - مستهدفات أجداد قسمه (المديرية/الدائرة التي يتبعها)
            # - مستهدفات المؤسسة الكلية
            from django.db.models import Q
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

        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            target = TargetService.create_target(
                data=serializer.validated_data,
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
        try:
            target = TargetService.update_target(
                instance, serializer.validated_data, actor=request.user,
            )
        except (DjangoValidationError, DjangoPermissionDenied) as exc:
            return _service_error_response(exc)
        output = self.get_serializer(target)
        return Response(output.data)

    def destroy(self, request, *args, **kwargs):
        """حذف مستهدف — يُسجَّل في سجلّ التدقيق."""
        instance = self.get_object()
        try:
            TargetService.delete_target(instance, actor=request.user)
        except (DjangoValidationError, DjangoPermissionDenied) as exc:
            return _service_error_response(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['get'], url_path='progress')
    def progress(self, request, pk=None):
        """
        GET /api/targets/{id}/progress/
        يُرجع حساب التقدم لمستهدف واحد (القيمة التراكمية، النسبة، إلخ).
        """
        target = self.get_object()
        try:
            data = TargetService.compute_target_progress(target)
        except Exception as exc:
            return _service_error_response(
                DjangoValidationError(str(exc))
            )
        # أضف معلومات أساسية عن المستهدف للمساعدة في العرض
        data['target_id'] = target.id
        data['indicator_name'] = target.indicator.name
        data['indicator_accumulation_type'] = target.indicator.accumulation_type
        data['scope_unit_name'] = (
            target.scope_unit.name if target.scope_unit_id else 'المؤسسة كاملة'
        )
        data['scope_level'] = target.scope_level
        data['year'] = target.year
        return Response(data)

    @action(detail=True, methods=['get'], url_path='breakdown')
    def breakdown(self, request, pk=None):
        """
        GET /api/targets/{id}/breakdown/
        يُرجع تفصيل مساهمة الوحدات التنظيمية في تحقيق مستهدف هرمي،
        كشجرة قابلة للتوسيع:
        - مستهدف مؤسسة: جذور = دوائر + مديريات يتيمة
        - مستهدف دائرة: جذور = أبناء الدائرة المباشرة
        - مستهدف مديرية: جذور = أقسام المديرية
        - مستهدف قسم: قائمة فارغة (لا تفصيل).
        """
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
            'indicator_name': target.indicator.name,
            'scope_unit_name': (
                target.scope_unit.name if target.scope_unit_id else 'المؤسسة كاملة'
            ),
            'scope_level': target.scope_level,
            'year': target.year,
            'target_value': target.target_value,
            'cumulative_value': progress['cumulative_value'],
            'progress_percentage': progress['progress_percentage'],
            'qisms_in_scope': progress['qisms_in_scope'],
            'breakdown': tree,
            'breakdown_type': 'tree',
        })
