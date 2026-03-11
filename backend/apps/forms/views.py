from django.core.exceptions import ValidationError as DjangoValidationError
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
    filterset_fields = ['qism', 'status', 'version']
    search_fields = ['qism__name', 'notes']

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
            'qism', 'created_by', 'approved_by', 'rejected_by'
        ).prefetch_related(
            'items__indicator'
        ).order_by('-created_at')

        # تصفية حسب صلاحيات المستخدم
        user = self.request.user
        if user.role == 'statistics_admin':
            return queryset
        elif user.role == 'planning_section':
            # قسم التخطيط يرى قوالب أقسام مديريته فقط
            if user.unit and user.unit.parent:
                return queryset.filter(
                    qism__parent=user.unit.parent,
                    qism__unit_type='qism',
                    qism__qism_role='regular',
                )
            return queryset.none()
        elif user.role == 'section_manager':
            # مدير القسم يرى قوالب قسمه فقط
            return queryset.filter(qism=user.unit)
        return queryset.none()

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
        مسموح لقسم التخطيط فقط
        """
        # التحقق من الصلاحيات
        if request.user.role != 'planning_section':
            return Response(
                {'detail': 'ليس لديك صلاحية للقيام بهذا الإجراء'},
                status=status.HTTP_403_FORBIDDEN,
            )

        template = self.get_object()

        try:
            template = FormTemplateService.submit_for_approval(template)
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
        if request.user.role != 'statistics_admin':
            return Response(
                {'detail': 'ليس لديك صلاحية للقيام بهذا الإجراء'},
                status=status.HTTP_403_FORBIDDEN,
            )

        template = self.get_object()

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
        if request.user.role != 'statistics_admin':
            return Response(
                {'detail': 'ليس لديك صلاحية للقيام بهذا الإجراء'},
                status=status.HTTP_403_FORBIDDEN,
            )

        template = self.get_object()

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
