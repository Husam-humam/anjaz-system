"""
طبقة العرض (Views) لتطبيق المنجزات — نقاط نهاية الفترات والمنجزات والمنجزات النوعية.
"""
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.forms.models import FormTemplate
from apps.organization.models import OrganizationUnit
from apps.organization.permissions import (
    IsStatisticsAdmin,
    IsStatisticsAdminOrPlanningSection,
    IsStatisticsAdminOrReadOnly,
)

from .models import (
    QismExtension,
    SubmissionAnswer,
    WeeklyPeriod,
    WeeklySubmission,
)
from .permissions import CanEditSubmission, CanViewSubmission
from .serializers import (
    ComplianceSerializer,
    QismExtensionSerializer,
    QualitativeAnswerSerializer,
    QualitativeRejectSerializer,
    SubmissionAnswerSerializer,
    WeeklyPeriodSerializer,
    WeeklySubmissionSerializer,
    WeeklySubmissionUpdateSerializer,
)


# ══════════════════════════════════════════════
# الفترات الأسبوعية
# ══════════════════════════════════════════════

class WeeklyPeriodViewSet(viewsets.ModelViewSet):
    """
    إدارة الفترات الأسبوعية.
    GET    /api/periods/              — قائمة الفترات
    POST   /api/periods/              — إنشاء فترة [statistics_admin]
    GET    /api/periods/{id}/         — تفاصيل فترة
    POST   /api/periods/{id}/close/   — إغلاق الفترة [statistics_admin]
    GET    /api/periods/{id}/compliance/ — تقرير الالتزام
    POST   /api/periods/{id}/extensions/ — منح تمديد [statistics_admin]
    """
    serializer_class = WeeklyPeriodSerializer
    permission_classes = [permissions.IsAuthenticated, IsStatisticsAdminOrReadOnly]
    filterset_fields = ['year', 'status']
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        return WeeklyPeriod.objects.select_related('created_by').all()

    def perform_create(self, serializer):
        """إنشاء فترة أسبوعية جديدة"""
        serializer.save(created_by=self.request.user)

    # ─── إغلاق الفترة ────────────────────────
    @action(detail=True, methods=['post'], url_path='close',
            permission_classes=[permissions.IsAuthenticated, IsStatisticsAdmin])
    def close(self, request, pk=None):
        """
        إغلاق الفترة الأسبوعية — POST /api/periods/{id}/close/
        يغلق الفترة ويُعلّم الأقسام التي لم تقدّم بأنها متأخرة.
        """
        period = self.get_object()

        if period.status == WeeklyPeriod.Status.CLOSED:
            return Response(
                {
                    'error': True,
                    'message': 'هذه الفترة مغلقة بالفعل.',
                    'code': 'BUSINESS_RULE_VIOLATION',
                    'details': {},
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # إغلاق الفترة
        period.status = WeeklyPeriod.Status.CLOSED
        period.save(update_fields=['status'])

        # تعليم المنجزات المسودة بأنها متأخرة
        WeeklySubmission.objects.filter(
            weekly_period=period,
            status=WeeklySubmission.Status.DRAFT,
        ).update(status=WeeklySubmission.Status.LATE)

        # إنشاء منجزات متأخرة للأقسام التي لم تقدم
        submitted_qism_ids = WeeklySubmission.objects.filter(
            weekly_period=period
        ).values_list('qism_id', flat=True)

        # جميع الأقسام العادية النشطة
        all_regular_qisms = OrganizationUnit.objects.filter(
            unit_type='qism', qism_role='regular', is_active=True,
        ).exclude(id__in=submitted_qism_ids)

        late_submissions = []
        for qism in all_regular_qisms:
            # البحث عن القالب الفعّال لهذا القسم
            active_template = FormTemplate.objects.filter(
                qism=qism,
                status=FormTemplate.Status.APPROVED,
                effective_from_year__lte=period.year,
            ).filter(
                Q(effective_from_year__lt=period.year)
                | Q(effective_from_week__lte=period.week_number)
            ).order_by('-version').first()

            if active_template:
                late_submissions.append(
                    WeeklySubmission(
                        qism=qism,
                        weekly_period=period,
                        form_template=active_template,
                        status=WeeklySubmission.Status.LATE,
                    )
                )

        if late_submissions:
            WeeklySubmission.objects.bulk_create(
                late_submissions, ignore_conflicts=True
            )

        serializer = self.get_serializer(period)
        return Response(serializer.data)

    # ─── تقرير الالتزام ──────────────────────
    @action(detail=True, methods=['get'], url_path='compliance',
            permission_classes=[permissions.IsAuthenticated,
                                IsStatisticsAdminOrPlanningSection])
    def compliance(self, request, pk=None):
        """
        تقرير الالتزام — GET /api/periods/{id}/compliance/
        يُرجع حالة تقديم المنجزات لكل قسم.
        """
        period = self.get_object()
        user = request.user

        # تحديد نطاق الأقسام حسب دور المستخدم
        qisms_qs = OrganizationUnit.objects.filter(
            unit_type='qism', qism_role='regular', is_active=True,
        )
        if user.role == 'planning_section' and user.unit and user.unit.parent:
            directorate = user.unit.parent
            descendant_ids = directorate.get_descendants(
                include_self=False
            ).filter(
                unit_type='qism', qism_role='regular', is_active=True,
            ).values_list('id', flat=True)
            qisms_qs = qisms_qs.filter(id__in=descendant_ids)

        # جلب المنجزات لهذه الفترة
        submissions = WeeklySubmission.objects.filter(
            weekly_period=period,
            qism__in=qisms_qs,
        ).select_related('qism')

        submissions_map = {sub.qism_id: sub for sub in submissions}

        sections = []
        counts = {'submitted': 0, 'late': 0, 'draft': 0}

        for qism in qisms_qs.order_by('name'):
            sub = submissions_map.get(qism.id)
            if sub:
                sub_status = sub.status
            else:
                # لا يوجد منجز — يُعتبر غير مقدم
                sub_status = 'not_submitted'

            sections.append({
                'qism_id': qism.id,
                'qism_name': qism.name,
                'status': sub_status,
            })

            if sub_status in ('submitted', 'approved'):
                counts['submitted'] += 1
            elif sub_status in ('late',):
                counts['late'] += 1
            elif sub_status in ('draft', 'extended'):
                counts['draft'] += 1
            # not_submitted لا يُحسب في أي فئة

        data = {
            'total_sections': qisms_qs.count(),
            'submitted': counts['submitted'],
            'late': counts['late'],
            'draft': counts['draft'],
            'sections': sections,
        }

        serializer = ComplianceSerializer(data)
        return Response(serializer.data)

    # ─── منح تمديد ───────────────────────────
    @action(detail=True, methods=['post'], url_path='extensions',
            permission_classes=[permissions.IsAuthenticated, IsStatisticsAdmin])
    def extensions(self, request, pk=None):
        """
        منح تمديد لقسم — POST /api/periods/{id}/extensions/
        """
        period = self.get_object()

        if period.status == WeeklyPeriod.Status.CLOSED:
            return Response(
                {
                    'error': True,
                    'message': 'لا يمكن منح تمديد لفترة مغلقة.',
                    'code': 'BUSINESS_RULE_VIOLATION',
                    'details': {},
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        data = request.data.copy()
        data['weekly_period'] = period.id

        serializer = QismExtensionSerializer(data=data)
        serializer.is_valid(raise_exception=True)

        try:
            serializer.save(granted_by=request.user)
        except IntegrityError:
            return Response(
                {
                    'error': True,
                    'message': 'يوجد تمديد مسبق لهذا القسم في هذه الفترة.',
                    'code': 'CONFLICT',
                    'details': {},
                },
                status=status.HTTP_409_CONFLICT,
            )

        # تحديث حالة المنجز إلى "ممدد" إن وُجد
        WeeklySubmission.objects.filter(
            qism_id=serializer.validated_data['qism'].id,
            weekly_period=period,
            status__in=[
                WeeklySubmission.Status.DRAFT,
                WeeklySubmission.Status.LATE,
            ],
        ).update(status=WeeklySubmission.Status.EXTENDED)

        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ══════════════════════════════════════════════
# المنجزات الأسبوعية
# ══════════════════════════════════════════════

class WeeklySubmissionViewSet(viewsets.ModelViewSet):
    """
    إدارة المنجزات الأسبوعية.
    GET    /api/submissions/              — قائمة المنجزات (حسب الدور)
    POST   /api/submissions/              — إنشاء/جلب منجز [section_manager]
    GET    /api/submissions/{id}/         — تفاصيل منجز
    PATCH  /api/submissions/{id}/         — حفظ إجابات [section_manager]
    POST   /api/submissions/{id}/submit/  — إرسال المنجز [section_manager]
    POST   /api/submissions/{id}/approve/ — اعتماد المنجز [planning_section]
    GET    /api/submissions/{id}/history/ — سجل المنجزات
    """
    serializer_class = WeeklySubmissionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['weekly_period', 'status']
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        """تحديد نطاق المنجزات حسب دور المستخدم"""
        user = self.request.user
        queryset = WeeklySubmission.objects.select_related(
            'qism', 'weekly_period', 'form_template',
            'planning_approved_by',
        ).prefetch_related(
            'answers__form_item__indicator',
        )

        if user.role == 'statistics_admin':
            pass  # جميع المنجزات
        elif user.role == 'planning_section':
            # منجزات أقسام المديرية التابعة
            if user.unit and user.unit.parent:
                directorate = user.unit.parent
                descendant_ids = directorate.get_descendants(
                    include_self=False
                ).values_list('id', flat=True)
                queryset = queryset.filter(qism_id__in=descendant_ids)
            else:
                queryset = queryset.none()
        elif user.role == 'section_manager':
            queryset = queryset.filter(qism=user.unit)
        else:
            queryset = queryset.none()

        # تصفية حسب qism_id (معامل استعلام)
        qism_id = self.request.query_params.get('qism_id')
        if qism_id:
            queryset = queryset.filter(qism_id=qism_id)

        return queryset.order_by('-weekly_period__year', '-weekly_period__week_number')

    def create(self, request, *args, **kwargs):
        """
        إنشاء أو جلب المنجز لفترة محددة — POST /api/submissions/
        العملية متساوية (idempotent): إذا وُجد منجز يُرجعه بدلاً من إنشاء جديد.
        """
        user = request.user

        if user.role != 'section_manager':
            return Response(
                {
                    'error': True,
                    'message': 'فقط مدير القسم يمكنه إنشاء منجز.',
                    'code': 'PERMISSION_DENIED',
                    'details': {},
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        period_id = request.data.get('weekly_period')
        if not period_id:
            return Response(
                {
                    'error': True,
                    'message': 'الفترة الأسبوعية مطلوبة.',
                    'code': 'VALIDATION_ERROR',
                    'details': {'weekly_period': ['هذا الحقل مطلوب.']},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # التحقق من وجود الفترة
        try:
            period = WeeklyPeriod.objects.get(id=period_id)
        except WeeklyPeriod.DoesNotExist:
            return Response(
                {
                    'error': True,
                    'message': 'الفترة الأسبوعية المحددة غير موجودة.',
                    'code': 'NOT_FOUND',
                    'details': {},
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        qism = user.unit

        # التحقق من أن الفترة مفتوحة
        if period.status != WeeklyPeriod.Status.OPEN:
            return Response(
                {
                    'error': True,
                    'message': 'لا يمكن إنشاء منجز لفترة مغلقة.',
                    'code': 'BUSINESS_RULE_VIOLATION',
                    'details': {},
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # البحث عن منجز موجود (idempotent)
        existing = WeeklySubmission.objects.filter(
            qism=qism, weekly_period=period
        ).first()
        if existing:
            serializer = WeeklySubmissionSerializer(existing)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # البحث عن القالب الفعّال
        active_template = FormTemplate.objects.filter(
            qism=qism,
            status=FormTemplate.Status.APPROVED,
            effective_from_year__lte=period.year,
        ).filter(
            Q(effective_from_year__lt=period.year)
            | Q(effective_from_week__lte=period.week_number)
        ).order_by('-version').first()

        if not active_template:
            return Response(
                {
                    'error': True,
                    'message': 'لا يوجد قالب استمارة فعّال لهذا القسم في هذه الفترة.',
                    'code': 'BUSINESS_RULE_VIOLATION',
                    'details': {},
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # إنشاء المنجز
        submission = WeeklySubmission.objects.create(
            qism=qism,
            weekly_period=period,
            form_template=active_template,
            status=WeeklySubmission.Status.DRAFT,
        )

        # إنشاء إجابات فارغة لجميع بنود القالب
        template_items = active_template.items.select_related('indicator').all()
        answers = [
            SubmissionAnswer(
                submission=submission,
                form_item=item,
            )
            for item in template_items
        ]
        SubmissionAnswer.objects.bulk_create(answers)

        serializer = WeeklySubmissionSerializer(submission)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        """
        حفظ إجابات المنجز — PATCH /api/submissions/{id}/
        مسموح فقط لمدير القسم وعندما يكون المنجز قابلاً للتعديل.
        """
        submission = self.get_object()
        user = request.user

        # التحقق من الصلاحية
        if user.role != 'section_manager' or submission.qism_id != user.unit_id:
            return Response(
                {
                    'error': True,
                    'message': 'ليس لديك صلاحية لتعديل هذا المنجز.',
                    'code': 'PERMISSION_DENIED',
                    'details': {},
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # التحقق من إمكانية التعديل
        if not submission.is_editable():
            return Response(
                {
                    'error': True,
                    'message': 'لا يمكن تعديل هذا المنجز. الموعد النهائي قد انتهى أو الفترة مغلقة.',
                    'code': 'BUSINESS_RULE_VIOLATION',
                    'details': {},
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # التحقق من أن الحالة تسمح بالتعديل
        if submission.status not in (
            WeeklySubmission.Status.DRAFT,
            WeeklySubmission.Status.EXTENDED,
        ):
            return Response(
                {
                    'error': True,
                    'message': 'لا يمكن تعديل منجز تم إرساله أو اعتماده.',
                    'code': 'BUSINESS_RULE_VIOLATION',
                    'details': {},
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        update_serializer = WeeklySubmissionUpdateSerializer(data=request.data)
        update_serializer.is_valid(raise_exception=True)

        # تحديث الملاحظات
        notes = update_serializer.validated_data.get('notes', '')
        if notes is not None:
            submission.notes = notes
            submission.save(update_fields=['notes'])

        # تحديث الإجابات
        answers_data = update_serializer.validated_data.get('answers', [])
        for answer_data in answers_data:
            form_item = answer_data.get('form_item')
            SubmissionAnswer.objects.update_or_create(
                submission=submission,
                form_item=form_item,
                defaults={
                    'numeric_value': answer_data.get('numeric_value'),
                    'text_value': answer_data.get('text_value', ''),
                    'is_qualitative': answer_data.get('is_qualitative', False),
                    'qualitative_details': answer_data.get(
                        'qualitative_details', ''
                    ),
                },
            )

        # إعادة جلب المنجز بالإجابات المحدثة
        submission.refresh_from_db()
        serializer = WeeklySubmissionSerializer(submission)
        return Response(serializer.data)

    # ─── إرسال المنجز ────────────────────────
    @action(detail=True, methods=['post'], url_path='submit')
    def submit(self, request, pk=None):
        """
        إرسال المنجز — POST /api/submissions/{id}/submit/
        ينقل الحالة من مسودة إلى مُرسل مع التحقق من الحقول الإلزامية.
        """
        submission = self.get_object()
        user = request.user

        # التحقق من الصلاحية
        if user.role != 'section_manager' or submission.qism_id != user.unit_id:
            return Response(
                {
                    'error': True,
                    'message': 'ليس لديك صلاحية لإرسال هذا المنجز.',
                    'code': 'PERMISSION_DENIED',
                    'details': {},
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # التحقق من إمكانية التعديل
        if not submission.is_editable():
            return Response(
                {
                    'error': True,
                    'message': 'لا يمكن إرسال هذا المنجز. الموعد النهائي قد انتهى أو الفترة مغلقة.',
                    'code': 'BUSINESS_RULE_VIOLATION',
                    'details': {},
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # التحقق من أن الحالة تسمح بالإرسال
        if submission.status not in (
            WeeklySubmission.Status.DRAFT,
            WeeklySubmission.Status.EXTENDED,
        ):
            return Response(
                {
                    'error': True,
                    'message': 'لا يمكن إرسال منجز ليس في حالة مسودة أو مُمدد.',
                    'code': 'BUSINESS_RULE_VIOLATION',
                    'details': {},
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # التحقق من الحقول الإلزامية
        mandatory_items = submission.form_template.items.filter(
            is_mandatory=True
        ).values_list('id', flat=True)

        answered_items = submission.answers.exclude(
            numeric_value__isnull=True, text_value=''
        ).values_list('form_item_id', flat=True)

        missing = set(mandatory_items) - set(answered_items)
        if missing:
            return Response(
                {
                    'error': True,
                    'message': 'يجب ملء جميع الحقول الإلزامية قبل الإرسال.',
                    'code': 'VALIDATION_ERROR',
                    'details': {
                        'missing_items': list(missing),
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # التحقق من صحة الإجابات النوعية
        qualitative_answers = submission.answers.filter(is_qualitative=True)
        for answer in qualitative_answers:
            if not answer.qualitative_details.strip():
                return Response(
                    {
                        'error': True,
                        'message': 'يجب إدخال تفاصيل جميع المنجزات النوعية قبل الإرسال.',
                        'code': 'VALIDATION_ERROR',
                        'details': {},
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # تحديث الحالة
        submission.status = WeeklySubmission.Status.SUBMITTED
        submission.submitted_at = timezone.now()
        submission.save(update_fields=['status', 'submitted_at'])

        # تحديث حالة المنجزات النوعية إلى "بانتظار اعتماد التخطيط"
        qualitative_answers.update(
            qualitative_status=SubmissionAnswer.QualitativeStatus.PENDING_PLANNING
        )

        serializer = WeeklySubmissionSerializer(submission)
        return Response(serializer.data)

    # ─── اعتماد المنجز ───────────────────────
    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, pk=None):
        """
        اعتماد المنجز — POST /api/submissions/{id}/approve/
        ينقل الحالة من مُرسل إلى معتمد (بواسطة قسم التخطيط).
        """
        submission = self.get_object()
        user = request.user

        # التحقق من الصلاحية
        if user.role != 'planning_section':
            return Response(
                {
                    'error': True,
                    'message': 'فقط قسم التخطيط يمكنه اعتماد المنجزات.',
                    'code': 'PERMISSION_DENIED',
                    'details': {},
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # التحقق من نطاق المديرية
        if user.unit and user.unit.parent:
            directorate = user.unit.parent
            descendant_ids = list(
                directorate.get_descendants(include_self=False)
                .values_list('id', flat=True)
            )
            if submission.qism_id not in descendant_ids:
                return Response(
                    {
                        'error': True,
                        'message': 'ليس لديك صلاحية لاعتماد منجز هذا القسم.',
                        'code': 'PERMISSION_DENIED',
                        'details': {},
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
        else:
            return Response(
                {
                    'error': True,
                    'message': 'لا يمكن تحديد نطاق صلاحياتك.',
                    'code': 'PERMISSION_DENIED',
                    'details': {},
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # التحقق من أن الحالة هي "مُرسل"
        if submission.status != WeeklySubmission.Status.SUBMITTED:
            return Response(
                {
                    'error': True,
                    'message': 'لا يمكن اعتماد منجز ليس في حالة مُرسل.',
                    'code': 'BUSINESS_RULE_VIOLATION',
                    'details': {},
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # اعتماد المنجز
        submission.status = WeeklySubmission.Status.APPROVED
        submission.planning_approved_by = user
        submission.planning_approved_at = timezone.now()
        submission.save(update_fields=[
            'status', 'planning_approved_by', 'planning_approved_at',
        ])

        # نقل المنجزات النوعية إلى "بانتظار اعتماد الإحصاء"
        submission.answers.filter(
            is_qualitative=True,
            qualitative_status=SubmissionAnswer.QualitativeStatus.PENDING_PLANNING,
        ).update(
            qualitative_status=SubmissionAnswer.QualitativeStatus.PENDING_STATISTICS
        )

        serializer = WeeklySubmissionSerializer(submission)
        return Response(serializer.data)

    # ─── سجل المنجزات ────────────────────────
    @action(detail=True, methods=['get'], url_path='history')
    def history(self, request, pk=None):
        """
        سجل المنجزات — GET /api/submissions/{id}/history/
        يُرجع المنجزات السابقة لنفس القسم.
        """
        submission = self.get_object()
        user = request.user

        # التحقق من الصلاحية
        allowed_roles = ('section_manager', 'planning_section', 'statistics_admin')
        if user.role not in allowed_roles:
            return Response(
                {
                    'error': True,
                    'message': 'ليس لديك صلاحية لعرض سجل المنجزات.',
                    'code': 'PERMISSION_DENIED',
                    'details': {},
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # جلب المنجزات السابقة لنفس القسم
        history_qs = WeeklySubmission.objects.filter(
            qism=submission.qism,
        ).select_related(
            'qism', 'weekly_period', 'form_template',
            'planning_approved_by',
        ).prefetch_related(
            'answers__form_item__indicator',
        ).order_by('-weekly_period__year', '-weekly_period__week_number')

        serializer = WeeklySubmissionSerializer(history_qs, many=True)
        return Response(serializer.data)


# ══════════════════════════════════════════════
# المنجزات النوعية
# ══════════════════════════════════════════════

class QualitativeViewSet(viewsets.GenericViewSet):
    """
    إدارة المنجزات النوعية.
    GET    /api/qualitative/                   — قائمة المنجزات النوعية
    POST   /api/qualitative/{answer_id}/approve/ — اعتماد نهائي [statistics_admin]
    POST   /api/qualitative/{answer_id}/reject/  — رفض [statistics_admin]
    """
    serializer_class = QualitativeAnswerSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'pk'

    def get_queryset(self):
        return SubmissionAnswer.objects.filter(
            is_qualitative=True,
        ).select_related(
            'submission__qism',
            'submission__weekly_period',
            'form_item__indicator',
            'qualitative_approved_by',
        )

    def list(self, request):
        """
        قائمة المنجزات النوعية — GET /api/qualitative/
        مع تصفية حسب الحالة والقسم والفترة.
        """
        queryset = self.get_queryset()

        # تصفية حسب الحالة
        qualitative_status = request.query_params.get('qualitative_status')
        if qualitative_status:
            queryset = queryset.filter(qualitative_status=qualitative_status)

        # تصفية حسب القسم
        qism_id = request.query_params.get('qism_id')
        if qism_id:
            queryset = queryset.filter(submission__qism_id=qism_id)

        # تصفية حسب الفترة
        weekly_period_id = request.query_params.get('weekly_period_id')
        if weekly_period_id:
            queryset = queryset.filter(
                submission__weekly_period_id=weekly_period_id
            )

        # تحديد النطاق حسب دور المستخدم
        user = request.user
        if user.role == 'planning_section':
            if user.unit and user.unit.parent:
                directorate = user.unit.parent
                descendant_ids = directorate.get_descendants(
                    include_self=False
                ).values_list('id', flat=True)
                queryset = queryset.filter(
                    submission__qism_id__in=descendant_ids
                )
            else:
                queryset = queryset.none()
        elif user.role == 'section_manager':
            queryset = queryset.filter(submission__qism=user.unit)

        queryset = queryset.order_by('-submission__weekly_period__year',
                                     '-submission__weekly_period__week_number')

        # التقسيم إلى صفحات
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='approve',
            permission_classes=[permissions.IsAuthenticated, IsStatisticsAdmin])
    def approve(self, request, pk=None):
        """
        اعتماد نهائي للمنجز النوعي — POST /api/qualitative/{answer_id}/approve/
        ينقل الحالة من "بانتظار اعتماد الإحصاء" إلى "معتمد".
        """
        try:
            answer = self.get_queryset().get(pk=pk)
        except SubmissionAnswer.DoesNotExist:
            return Response(
                {
                    'error': True,
                    'message': 'المنجز النوعي المحدد غير موجود.',
                    'code': 'NOT_FOUND',
                    'details': {},
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if answer.qualitative_status != SubmissionAnswer.QualitativeStatus.PENDING_STATISTICS:
            return Response(
                {
                    'error': True,
                    'message': 'لا يمكن اعتماد منجز نوعي ليس في حالة "بانتظار اعتماد الإحصاء".',
                    'code': 'BUSINESS_RULE_VIOLATION',
                    'details': {},
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        answer.qualitative_status = SubmissionAnswer.QualitativeStatus.APPROVED
        answer.qualitative_approved_by = request.user
        answer.qualitative_approved_at = timezone.now()
        answer.save(update_fields=[
            'qualitative_status', 'qualitative_approved_by',
            'qualitative_approved_at',
        ])

        serializer = QualitativeAnswerSerializer(answer)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='reject',
            permission_classes=[permissions.IsAuthenticated, IsStatisticsAdmin])
    def reject(self, request, pk=None):
        """
        رفض المنجز النوعي — POST /api/qualitative/{answer_id}/reject/
        """
        try:
            answer = self.get_queryset().get(pk=pk)
        except SubmissionAnswer.DoesNotExist:
            return Response(
                {
                    'error': True,
                    'message': 'المنجز النوعي المحدد غير موجود.',
                    'code': 'NOT_FOUND',
                    'details': {},
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if answer.qualitative_status != SubmissionAnswer.QualitativeStatus.PENDING_STATISTICS:
            return Response(
                {
                    'error': True,
                    'message': 'لا يمكن رفض منجز نوعي ليس في حالة "بانتظار اعتماد الإحصاء".',
                    'code': 'BUSINESS_RULE_VIOLATION',
                    'details': {},
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        reject_serializer = QualitativeRejectSerializer(data=request.data)
        reject_serializer.is_valid(raise_exception=True)

        answer.qualitative_status = SubmissionAnswer.QualitativeStatus.REJECTED
        answer.rejection_reason = reject_serializer.validated_data['rejection_reason']
        answer.qualitative_approved_by = request.user
        answer.qualitative_approved_at = timezone.now()
        answer.save(update_fields=[
            'qualitative_status', 'rejection_reason',
            'qualitative_approved_by', 'qualitative_approved_at',
        ])

        serializer = QualitativeAnswerSerializer(answer)
        return Response(serializer.data)
