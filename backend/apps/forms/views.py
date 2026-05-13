from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response

from .models import FormTemplate
from .permissions import FormTemplatePermission, IsStatisticsAdmin, IsPlanningSection
from .serializers import (
    FormTemplateSerializer,
    FormTemplateCreateSerializer,
    FormTemplateUpdateSerializer,
    FormTemplateApproveSerializer,
    FormTemplateRejectSerializer,
)
from .services import FormTemplateService


class FormTemplateViewSet(viewsets.ModelViewSet):
    """واجهة برمجية لإدارة قوالب الاستمارات"""
    permission_classes = [FormTemplatePermission]
    filterset_fields = ['qism', 'status', 'version', 'qism__parent']
    search_fields = ['qism__name', 'qism__code', 'notes']
    ordering_fields = ['created_at', 'version', 'qism__name', 'status']

    def get_serializer_class(self):
        if self.action == 'create':
            return FormTemplateCreateSerializer
        if self.action in ('update', 'partial_update'):
            return FormTemplateUpdateSerializer
        if self.action == 'approve':
            return FormTemplateApproveSerializer
        if self.action == 'reject':
            return FormTemplateRejectSerializer
        return FormTemplateSerializer

    def get_queryset(self):
        queryset = FormTemplate.objects.select_related(
            'qism', 'qism__parent', 'created_by', 'approved_by', 'rejected_by'
        ).prefetch_related(
            'items__indicator'
        ).order_by('-created_at')

        # تصفية حسب صلاحيات المستخدم — نستخدم المنطق الموحّد
        # لدعم المخطط على مستوى المديرية أو الدائرة أو المخطط المركزي
        user = self.request.user
        if user.role == 'statistics_admin':
            pass  # نطاق كامل
        elif user.role == 'planning_section':
            from apps.submissions.services import (
                _planning_section_scope_qism_ids,
            )
            scope_ids = _planning_section_scope_qism_ids(user)
            if scope_ids is None:
                pass  # مخطط مركزي — كل القوالب
            elif not scope_ids:
                return queryset.none()
            else:
                queryset = queryset.filter(qism_id__in=scope_ids)
        elif user.role == 'section_manager':
            queryset = queryset.filter(qism=user.unit)
        else:
            return queryset.none()

        # ─── فلاتر هرمية إضافية ───
        # فلتر بالمديرية (parent مباشر للقسم)
        mudiriya_id = self.request.query_params.get('mudiriya_id')
        if mudiriya_id:
            try:
                queryset = queryset.filter(qism__parent_id=int(mudiriya_id))
            except (ValueError, TypeError):
                pass

        # فلتر بالدائرة (يشمل أقسام الدائرة المباشرة وأقسام مديرياتها)
        daira_id = self.request.query_params.get('daira_id')
        if daira_id:
            try:
                from apps.organization.models import OrganizationUnit
                daira = OrganizationUnit.objects.filter(
                    pk=int(daira_id), unit_type='daira'
                ).first()
                if daira:
                    descendant_ids = list(
                        daira.get_descendants(include_self=False)
                        .filter(unit_type='qism')
                        .values_list('id', flat=True)
                    )
                    queryset = queryset.filter(qism_id__in=descendant_ids)
                else:
                    queryset = queryset.none()
            except (ValueError, TypeError):
                pass

        # فلتر "الإصدار الأخير فقط" لكل قسم
        latest_only = self.request.query_params.get('latest_only')
        if latest_only and latest_only.lower() in ('true', '1'):
            from django.db.models import Max, OuterRef, Subquery
            latest_versions = (
                FormTemplate.objects.filter(qism=OuterRef('qism'))
                .order_by('-version')
                .values('version')[:1]
            )
            queryset = queryset.annotate(
                _max_version=Subquery(latest_versions)
            ).filter(version=models.F('_max_version'))

        return queryset

    def create(self, request, *args, **kwargs):
        """إنشاء قالب استمارة جديد"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = {
            'qism': serializer.validated_data['qism'],
            'notes': serializer.validated_data.get('notes', ''),
        }
        items_data = serializer.validated_data['items']

        try:
            template = FormTemplateService.create_template(
                data=data,
                items_data=items_data,
                created_by=request.user,
            )
        except DjangoValidationError as e:
            raise DRFValidationError(
                e.message_dict if hasattr(e, 'message_dict') else {'detail': e.messages}
            )

        output_serializer = FormTemplateSerializer(template)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        """تحديث قالب استمارة (في حالة المسودة فقط)"""
        template = self.get_object()
        serializer = self.get_serializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        data = {}
        if 'notes' in serializer.validated_data:
            data['notes'] = serializer.validated_data['notes']

        items_data = serializer.validated_data.get('items', None)

        try:
            template = FormTemplateService.update_template(
                template=template,
                data=data,
                items_data=items_data,
                actor=request.user,
            )
        except DjangoValidationError as e:
            raise DRFValidationError(
                e.message_dict if hasattr(e, 'message_dict') else {'detail': e.messages}
            )

        output_serializer = FormTemplateSerializer(template)
        return Response(output_serializer.data)

    def partial_update(self, request, *args, **kwargs):
        """تحديث جزئي لقالب الاستمارة"""
        return self.update(request, *args, **kwargs)

    @action(detail=True, methods=['post'], url_path='submit')
    def submit(self, request, pk=None):
        """
        تقديم القالب للاعتماد: مسودة → بانتظار الاعتماد
        مسموح لقسم التخطيط ومدير قسم الإحصاء
        """
        # التحقق من الصلاحيات
        if request.user.role not in ('planning_section', 'statistics_admin'):
            return Response(
                {'detail': 'ليس لديك صلاحية للقيام بهذا الإجراء'},
                status=status.HTTP_403_FORBIDDEN,
            )

        template = self.get_object()

        try:
            template = FormTemplateService.submit_for_approval(
                template, actor=request.user
            )
        except DjangoValidationError as e:
            raise DRFValidationError(
                e.message_dict if hasattr(e, 'message_dict') else {'detail': e.messages}
            )

        serializer = FormTemplateSerializer(template)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, pk=None):
        """
        اعتماد القالب: بانتظار الاعتماد → معتمد
        مسموح لمدير قسم الإحصاء فقط
        """
        # التحقق من الصلاحيات
        if request.user.role not in ('statistics_admin', 'planning_section'):
            return Response(
                {'detail': 'ليس لديك صلاحية للقيام بهذا الإجراء'},
                status=status.HTTP_403_FORBIDDEN,
            )

        template = self.get_object()

        # التحقق من نطاق الصلاحية لقسم التخطيط (يدعم مخطط مديرية/دائرة/مركزي)
        if request.user.role == 'planning_section':
            from apps.submissions.services import (
                _planning_section_scope_qism_ids,
            )
            scope_ids = _planning_section_scope_qism_ids(request.user)
            # scope_ids = None يعني مخطط مركزي (نطاق كامل)
            if scope_ids is not None and template.qism_id not in scope_ids:
                return Response(
                    {'detail': 'لا تملك صلاحية اعتماد هذه الاستمارة'},
                    status=status.HTTP_403_FORBIDDEN,
                )

        serializer = FormTemplateApproveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            template = FormTemplateService.approve_template(
                template=template,
                approved_by=request.user,
                effective_from_week=serializer.validated_data['effective_from_week'],
                effective_from_year=serializer.validated_data['effective_from_year'],
            )
        except DjangoValidationError as e:
            raise DRFValidationError(
                e.message_dict if hasattr(e, 'message_dict') else {'detail': e.messages}
            )

        output_serializer = FormTemplateSerializer(template)
        return Response(output_serializer.data)

    @action(detail=True, methods=['post'], url_path='reject')
    def reject(self, request, pk=None):
        """
        رفض القالب: بانتظار الاعتماد → مرفوض
        مسموح لمدير قسم الإحصاء فقط
        """
        # التحقق من الصلاحيات
        if request.user.role not in ('statistics_admin', 'planning_section'):
            return Response(
                {'detail': 'ليس لديك صلاحية للقيام بهذا الإجراء'},
                status=status.HTTP_403_FORBIDDEN,
            )

        template = self.get_object()

        # التحقق من نطاق الصلاحية لقسم التخطيط (يدعم مخطط مديرية/دائرة/مركزي)
        if request.user.role == 'planning_section':
            from apps.submissions.services import (
                _planning_section_scope_qism_ids,
            )
            scope_ids = _planning_section_scope_qism_ids(request.user)
            if scope_ids is not None and template.qism_id not in scope_ids:
                return Response(
                    {'detail': 'لا تملك صلاحية رفض هذه الاستمارة'},
                    status=status.HTTP_403_FORBIDDEN,
                )

        serializer = FormTemplateRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            template = FormTemplateService.reject_template(
                template=template,
                rejected_by=request.user,
                reason=serializer.validated_data['rejection_reason'],
            )
        except DjangoValidationError as e:
            raise DRFValidationError(
                e.message_dict if hasattr(e, 'message_dict') else {'detail': e.messages}
            )

        output_serializer = FormTemplateSerializer(template)
        return Response(output_serializer.data)

    @action(detail=True, methods=['post'], url_path='new-version')
    def new_version(self, request, pk=None):
        """
        إنشاء إصدار جديد (مسودة) بناءً على قالب موجود.
        - يُستخدم لتعديل قالب معتمد دون كسر الربط التاريخي.
        - مسموح لقسم التخطيط ومدير قسم الإحصاء.
        """
        if request.user.role not in ('planning_section', 'statistics_admin'):
            return Response(
                {'detail': 'ليس لديك صلاحية للقيام بهذا الإجراء'},
                status=status.HTTP_403_FORBIDDEN,
            )

        source_template = self.get_object()

        try:
            new_template = FormTemplateService.create_new_version(
                source_template=source_template,
                created_by=request.user,
            )
        except DjangoValidationError as e:
            raise DRFValidationError(
                e.message_dict if hasattr(e, 'message_dict') else {'detail': e.messages}
            )

        output_serializer = FormTemplateSerializer(new_template)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='pending-count')
    def pending_count(self, request):
        """
        GET /api/forms/templates/pending-count/
        يُرجع عدد القوالب بانتظار الاعتماد ضمن نطاق المستخدم الحالي.
        يُستخدم لعرض badge في الـ sidebar.
        """
        queryset = self.get_queryset().filter(
            status=FormTemplate.Status.PENDING_APPROVAL
        )
        return Response({'count': queryset.count()})

    @action(detail=False, methods=['get'], url_path='active')
    def active(self, request):
        """
        الحصول على القالب النشط لقسم معين.
        معاملات الاستعلام: qism_id (مطلوب)، year، week_number
        """
        qism_id = request.query_params.get('qism_id')
        if not qism_id:
            return Response(
                {'detail': 'يجب تحديد معرف القسم (qism_id)'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        year = request.query_params.get('year')
        week_number = request.query_params.get('week_number')

        # تحويل المعاملات إلى أرقام
        try:
            qism_id = int(qism_id)
        except (ValueError, TypeError):
            return Response(
                {'detail': 'معرف القسم يجب أن يكون رقماً صحيحاً'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            year = int(year) if year else None
            week_number = int(week_number) if week_number else None
        except (ValueError, TypeError):
            return Response(
                {'detail': 'السنة ورقم الأسبوع يجب أن يكونا أرقاماً صحيحة'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            template = FormTemplateService.get_active_template(
                qism_id=qism_id,
                year=year,
                week_number=week_number,
            )
        except DjangoValidationError as e:
            raise DRFValidationError(
                e.message_dict if hasattr(e, 'message_dict') else {'detail': e.messages}
            )

        serializer = FormTemplateSerializer(template)
        return Response(serializer.data)
