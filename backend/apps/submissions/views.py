"""
طبقة العرض (Views) لتطبيق المنجزات — نقاط نهاية الفترات والمنجزات والمنجزات النوعية.
"""
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.organization.models import OrganizationUnit
from apps.organization.permissions import (
    IsStatisticsAdmin,
    IsStatisticsAdminOrPlanningSection,
    IsStatisticsAdminOrReadOnly,
)

from .models import (
    SubmissionAnswer,
    WeeklyPeriod,
    WeeklySubmission,
)
from .serializers import (
    ComplianceSerializer,
    QismExtensionSerializer,
    QualitativeAnswerSerializer,
    QualitativeRejectSerializer,
    SubmissionAnswerSerializer,
    SubmissionRejectSerializer,
    WeeklyPeriodSerializer,
    WeeklySubmissionSerializer,
    WeeklySubmissionUpdateSerializer,
)
from .services import (
    QualitativeService,
    SubmissionAdminService,
    SubmissionService,
    WeeklyPeriodService,
    _planning_section_scope_qism_ids,
)


def _service_error_response(exc):
    """تحويل أخطاء طبقة الخدمة (Django) إلى استجابات HTTP موحّدة."""
    if isinstance(exc, DjangoPermissionDenied):
        return Response(
            {
                'error': True,
                'message': str(exc) or 'ليس لديك صلاحية لتنفيذ هذا الإجراء.',
                'code': 'PERMISSION_DENIED',
                'details': {},
            },
            status=status.HTTP_403_FORBIDDEN,
        )
    # DjangoValidationError
    details = {}
    message = 'بيانات غير صالحة.'
    if hasattr(exc, 'message_dict'):
        details = exc.message_dict
        # 1) إذا تضمّن القاموس مفتاح 'message' صريح — استخدمه
        explicit_message = details.get('message')
        if isinstance(explicit_message, list) and explicit_message:
            message = str(explicit_message[0])
        elif isinstance(explicit_message, str) and explicit_message:
            message = explicit_message
        else:
            # 2) خلاف ذلك: استخراج أول قيمة قابلة للقراءة
            for value in details.values():
                if isinstance(value, list) and value:
                    message = str(value[0])
                    break
                if isinstance(value, str) and value:
                    message = value
                    break
    elif hasattr(exc, 'messages') and exc.messages:
        message = str(exc.messages[0])
        details = {'errors': list(exc.messages)}
    else:
        message = str(exc)
    return Response(
        {
            'error': True,
            'message': message,
            'code': 'BUSINESS_RULE_VIOLATION',
            'details': details,
        },
        status=status.HTTP_422_UNPROCESSABLE_ENTITY,
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

    def create(self, request, *args, **kwargs):
        """إنشاء فترة أسبوعية جديدة عبر طبقة الخدمة"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            period = WeeklyPeriodService.create_period(
                data=serializer.validated_data,
                created_by=request.user,
            )
        except (DjangoValidationError, DjangoPermissionDenied) as exc:
            return _service_error_response(exc)
        out_serializer = self.get_serializer(period)
        return Response(out_serializer.data, status=status.HTTP_201_CREATED)

    # ─── إغلاق الفترة ────────────────────────
    @action(detail=True, methods=['post'], url_path='close',
            permission_classes=[permissions.IsAuthenticated, IsStatisticsAdmin])
    def close(self, request, pk=None):
        """
        إغلاق الفترة الأسبوعية — POST /api/periods/{id}/close/
        يغلق الفترة ويُعلّم الأقسام التي لم تقدّم بأنها متأخرة.
        يرفض الإغلاق إذا كانت هناك تمديدات سارية لم تنته.
        """
        period = self.get_object()
        try:
            WeeklyPeriodService.close_period(period, request.user)
        except (DjangoValidationError, DjangoPermissionDenied) as exc:
            return _service_error_response(exc)

        period.refresh_from_db()
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
        if user.role == 'planning_section':
            scope_ids = _planning_section_scope_qism_ids(user)
            if scope_ids is not None:  # None = نطاق مركزي يشمل الجميع
                qisms_qs = qisms_qs.filter(id__in=scope_ids)

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

    # ─── التفصيل المُجمّع لنطاق معيّن ───────
    @action(detail=True, methods=['get'], url_path='aggregated',
            permission_classes=[permissions.IsAuthenticated])
    def aggregated(self, request, pk=None):
        """
        GET /api/periods/{id}/aggregated/?unit_id=X
        يُرجع التفصيل المُجمّع لوحدة تنظيمية محددة ضمن هذه الفترة.

        - unit_id فارغ → المؤسسة كاملة
        - unit_id لقسم → تفاصيل منجز القسم الوحيد
        - unit_id لمديرية/دائرة → قيم مؤشرات مُجمّعة + قائمة أقسام

        الاستجابة:
        {
          "scope_unit": {id, name, unit_type} | null,
          "period": {id, year, week_number, ...},
          "mode": "qism" | "group",
          "submission": {...} (فقط لو mode=qism),
          "qism_submissions": [{qism_id, qism_name, submission_id, status, ...}],
          "aggregated_indicators": [
            {indicator_id, indicator_name, accumulation_type,
             aggregated_value, contributing_qisms, ...}
          ],
          "stats": {total_qisms, submitted, approved, late, not_submitted}
        }
        """
        from collections import defaultdict

        period = self.get_object()
        user = request.user
        unit_id = request.query_params.get('unit_id')

        # تحديد نطاق الأقسام حسب الوحدة المطلوبة
        if unit_id:
            try:
                unit_id = int(unit_id)
            except (ValueError, TypeError):
                return Response(
                    {'error': True, 'message': 'معرف الوحدة غير صالح',
                     'code': 'VALIDATION_ERROR', 'details': {}},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                scope_unit = OrganizationUnit.objects.get(pk=unit_id)
            except OrganizationUnit.DoesNotExist:
                return Response(
                    {'error': True, 'message': 'الوحدة غير موجودة',
                     'code': 'NOT_FOUND', 'details': {}},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            scope_unit = None

        # فحص صلاحية المستخدم على الوحدة المطلوبة
        if scope_unit and user.role == 'planning_section':
            scope_ids = _planning_section_scope_qism_ids(user)
            if scope_ids is not None:
                # يجب أن تكون الوحدة أو أحفادها ضمن نطاق المخطط
                allowed_unit_ids = set(scope_ids)
                # نسمح للمخطط بمشاهدة مديرياتهم ودوائرهم (الأجداد الخاصة بهم)
                if user.unit and user.unit.parent:
                    directorate = user.unit.parent
                    allowed_unit_ids.update(
                        directorate.get_descendants(include_self=True)
                        .values_list('id', flat=True)
                    )
                if scope_unit.id not in allowed_unit_ids:
                    return Response(
                        {'error': True, 'message': 'ليس لديك صلاحية لهذه الوحدة',
                         'code': 'PERMISSION_DENIED', 'details': {}},
                        status=status.HTTP_403_FORBIDDEN,
                    )
        elif user.role == 'section_manager':
            # مدير القسم يرى فقط قسمه (ولا يرى المستويات الأعلى)
            if not scope_unit or scope_unit.id != user.unit_id:
                return Response(
                    {'error': True, 'message': 'ليس لديك صلاحية لهذه الوحدة',
                     'code': 'PERMISSION_DENIED', 'details': {}},
                    status=status.HTTP_403_FORBIDDEN,
                )

        # حساب معرّفات الأقسام ضمن النطاق
        from .services import _planning_section_scope_qism_ids as _scope_helper
        if scope_unit is None:
            # المؤسسة كاملة
            qism_ids = list(
                OrganizationUnit.objects.filter(
                    unit_type='qism', qism_role='regular', is_active=True,
                ).values_list('id', flat=True)
            )
            # لمخطط: قيّد بالنطاق
            if user.role == 'planning_section':
                scope_ids = _scope_helper(user)
                if scope_ids is not None:
                    qism_ids = [i for i in qism_ids if i in scope_ids]
        elif scope_unit.unit_type == 'qism':
            if scope_unit.qism_role != 'regular':
                return Response(
                    {'error': True, 'message': 'الأقسام الخاصة غير مدعومة',
                     'code': 'VALIDATION_ERROR', 'details': {}},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            qism_ids = [scope_unit.id]
        else:
            # إعادة تحميل لتجنّب MPTT staleness
            fresh_unit = OrganizationUnit.objects.get(pk=scope_unit.pk)
            qism_ids = list(
                fresh_unit.get_descendants()
                .filter(unit_type='qism', qism_role='regular', is_active=True)
                .values_list('id', flat=True)
            )

        # جلب المنجزات لهذه الفترة ضمن الأقسام المحدّدة
        submissions_qs = WeeklySubmission.objects.filter(
            weekly_period=period,
            qism_id__in=qism_ids,
        ).select_related(
            'qism', 'form_template', 'planning_approved_by',
        )

        submissions_by_qism = {s.qism_id: s for s in submissions_qs}

        # بناء قائمة الأقسام (حتى التي لم تقدّم)
        qism_info = []
        qisms_dict = {
            q.id: q for q in OrganizationUnit.objects.filter(id__in=qism_ids)
        }
        stats = {'total': 0, 'submitted': 0, 'approved': 0, 'late': 0, 'not_submitted': 0}
        for qid in qism_ids:
            q = qisms_dict.get(qid)
            if not q:
                continue
            sub = submissions_by_qism.get(qid)
            qism_info.append({
                'qism_id': qid,
                'qism_name': q.name,
                'qism_code': q.code,
                'submission_id': sub.id if sub else None,
                'status': sub.status if sub else 'not_submitted',
                'submitted_at': sub.submitted_at.isoformat() if sub and sub.submitted_at else None,
            })
            stats['total'] += 1
            if sub:
                if sub.status == 'approved':
                    stats['approved'] += 1
                    stats['submitted'] += 1
                elif sub.status == 'submitted':
                    stats['submitted'] += 1
                elif sub.status == 'late':
                    stats['late'] += 1
            else:
                stats['not_submitted'] += 1

        # تجميع قيم المؤشرات عبر الأقسام (sum/average/last_value)
        from apps.indicators.models import Indicator
        answers = SubmissionAnswer.objects.filter(
            submission__in=submissions_qs,
            numeric_value__isnull=False,
        ).select_related(
            'form_item__indicator', 'form_item__indicator__category',
            'submission__qism',
        )

        by_indicator = defaultdict(
            lambda: {'values': [], 'qisms': set(), 'indicator': None}
        )
        for ans in answers:
            ind = ans.form_item.indicator
            by_indicator[ind.id]['values'].append(ans.numeric_value)
            by_indicator[ind.id]['qisms'].add(ans.submission.qism_id)
            by_indicator[ind.id]['indicator'] = ind

        aggregated_indicators = []
        for ind_id, bucket in by_indicator.items():
            ind = bucket['indicator']
            acc = ind.accumulation_type
            vals = bucket['values']
            if acc == Indicator.AccumulationType.SUM:
                total = sum(vals)
            elif acc == Indicator.AccumulationType.AVERAGE:
                total = sum(vals) / len(vals) if vals else 0
            elif acc == Indicator.AccumulationType.LAST_VALUE:
                total = vals[-1] if vals else 0
            else:
                total = sum(vals)
            aggregated_indicators.append({
                'indicator_id': ind_id,
                'indicator_name': ind.name,
                'indicator_unit_type': ind.unit_type,
                'indicator_unit_label': ind.unit_label,
                'indicator_category': (
                    ind.category.name if ind.category_id else None
                ),
                'accumulation_type': acc,
                'aggregated_value': round(total, 2),
                'contributing_qisms': len(bucket['qisms']),
                'data_points': len(vals),
            })
        aggregated_indicators.sort(
            key=lambda x: (x['indicator_category'] or '', x['indicator_name'])
        )

        # المنجزات النوعية المعتمدة في هذا النطاق
        qualitative_answers = SubmissionAnswer.objects.filter(
            submission__in=submissions_qs,
            is_qualitative=True,
            qualitative_status='approved',
        ).select_related(
            'submission__qism', 'form_item__indicator',
        )
        qualitative_list = [
            {
                'id': qa.id,
                'qism_name': qa.submission.qism.name,
                'indicator_name': qa.form_item.indicator.name,
                'details': qa.qualitative_details,
            }
            for qa in qualitative_answers
        ]

        # إذا كان النطاق قسم مفرد: أضف تفاصيل الاستمارة الكاملة
        qism_submission_detail = None
        if scope_unit and scope_unit.unit_type == 'qism':
            sub = submissions_by_qism.get(scope_unit.id)
            if sub:
                sub_answers = SubmissionAnswer.objects.filter(
                    submission=sub,
                ).select_related(
                    'form_item__indicator', 'form_item__indicator__category',
                )
                qism_submission_detail = {
                    'id': sub.id,
                    'status': sub.status,
                    'submitted_at': (
                        sub.submitted_at.isoformat() if sub.submitted_at else None
                    ),
                    'planning_approved_by': (
                        sub.planning_approved_by.full_name
                        if sub.planning_approved_by_id else None
                    ),
                    'planning_approved_at': (
                        sub.planning_approved_at.isoformat()
                        if sub.planning_approved_at else None
                    ),
                    'notes': sub.notes,
                    'answers': [
                        {
                            'id': a.id,
                            'indicator_name': a.form_item.indicator.name,
                            'indicator_unit_type': a.form_item.indicator.unit_type,
                            'indicator_unit_label': a.form_item.indicator.unit_label,
                            'indicator_category': (
                                a.form_item.indicator.category.name
                                if a.form_item.indicator.category_id else None
                            ),
                            'is_mandatory': a.form_item.is_mandatory,
                            'numeric_value': a.numeric_value,
                            'text_value': a.text_value,
                            'is_qualitative': a.is_qualitative,
                            'qualitative_details': a.qualitative_details,
                            'qualitative_status': a.qualitative_status,
                        }
                        for a in sub_answers
                    ],
                }

        return Response({
            'scope_unit': {
                'id': scope_unit.id if scope_unit else None,
                'name': scope_unit.name if scope_unit else 'المؤسسة كاملة',
                'unit_type': scope_unit.unit_type if scope_unit else 'institution',
                'code': scope_unit.code if scope_unit else None,
            },
            'period': {
                'id': period.id,
                'year': period.year,
                'week_number': period.week_number,
                'start_date': str(period.start_date),
                'end_date': str(period.end_date),
                'deadline': period.deadline.isoformat() if period.deadline else None,
                'status': period.status,
            },
            'mode': 'qism' if (scope_unit and scope_unit.unit_type == 'qism') else 'group',
            'qism_submission': qism_submission_detail,
            'qism_submissions': qism_info,
            'aggregated_indicators': aggregated_indicators,
            'qualitative_answers': qualitative_list,
            'stats': stats,
        })

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
    POST   /api/submissions/{id}/reject/  — إرجاع المنجز للتصحيح [planning_section]
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
            scope_ids = _planning_section_scope_qism_ids(user)
            if scope_ids is None:
                pass  # نطاق مركزي — جميع المنجزات
            else:
                queryset = queryset.filter(qism_id__in=scope_ids)
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

        try:
            submission, created = SubmissionService.get_or_create_submission(
                qism=user.unit, weekly_period=period, actor=user,
            )
        except (DjangoValidationError, DjangoPermissionDenied) as exc:
            return _service_error_response(exc)

        serializer = WeeklySubmissionSerializer(submission)
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def partial_update(self, request, *args, **kwargs):
        """
        حفظ إجابات المنجز — PATCH /api/submissions/{id}/
        الصلاحيات:
        - مدير القسم: يُعدِّل منجز قسمه (في الحالات القابلة للتعديل العادية).
        - قسم التخطيط: يُعدِّل المنجز إذا كان في حالة `returned_by_admin`
          وضمن نطاقه — هذا يسمح للتخطيط بتصحيح المنجز قبل إعادة اعتماده.
        """
        submission = self.get_object()
        user = request.user

        # التحقق من الصلاحية
        is_section_manager_owner = (
            user.role == 'section_manager' and submission.qism_id == user.unit_id
        )

        is_planning_editing_admin_returned = False
        if (
            user.role == 'planning_section'
            and submission.status == WeeklySubmission.Status.RETURNED_BY_ADMIN
        ):
            # فحص النطاق — يجب أن يكون القسم ضمن نطاق المخطّط
            from apps.submissions.services import _planning_section_scope_qism_ids
            scope_ids = _planning_section_scope_qism_ids(user)
            if scope_ids is None or submission.qism_id in scope_ids:
                is_planning_editing_admin_returned = True

        if not (is_section_manager_owner or is_planning_editing_admin_returned):
            return Response(
                {
                    'error': True,
                    'message': 'ليس لديك صلاحية لتعديل هذا المنجز.',
                    'code': 'PERMISSION_DENIED',
                    'details': {},
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # طبقة الخدمة تتحقق من قابلية التعديل (الحالة + الفترة + الموعد + التمديد)
        update_serializer = WeeklySubmissionUpdateSerializer(data=request.data)
        update_serializer.is_valid(raise_exception=True)

        notes = update_serializer.validated_data.get('notes')
        answers_data = [
            {
                'form_item_id': item['form_item'].id,
                'numeric_value': item.get('numeric_value'),
                'text_value': item.get('text_value', ''),
                'is_qualitative': item.get('is_qualitative', False),
                'qualitative_details': item.get('qualitative_details', ''),
            }
            for item in update_serializer.validated_data.get('answers', [])
        ]

        try:
            SubmissionService.save_answers(
                submission, answers_data, notes=notes, actor=user,
            )
        except (DjangoValidationError, DjangoPermissionDenied) as exc:
            return _service_error_response(exc)

        submission.refresh_from_db()
        serializer = WeeklySubmissionSerializer(submission)
        return Response(serializer.data)

    # ─── إرسال المنجز ────────────────────────
    @action(detail=True, methods=['post'], url_path='submit')
    def submit(self, request, pk=None):
        """
        إرسال المنجز — POST /api/submissions/{id}/submit/
        ينقل الحالة من مسودة/ممدد/مُرجَع إلى مُرسل مع التحقق من الحقول الإلزامية.
        """
        submission = self.get_object()
        try:
            submission = SubmissionService.submit(submission, request.user)
        except (DjangoValidationError, DjangoPermissionDenied) as exc:
            return _service_error_response(exc)

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
        try:
            submission = SubmissionService.approve(submission, request.user)
        except (DjangoValidationError, DjangoPermissionDenied) as exc:
            return _service_error_response(exc)

        serializer = WeeklySubmissionSerializer(submission)
        return Response(serializer.data)

    # ─── رفض/إرجاع المنجز ─────────────────────
    @action(detail=True, methods=['post'], url_path='reject')
    def reject(self, request, pk=None):
        """
        رفض/إرجاع المنجز للتصحيح — POST /api/submissions/{id}/reject/
        ينقل الحالة من مُرسل إلى مُرجَع للتصحيح (بواسطة قسم التخطيط).
        body: { "reason": "سبب الإرجاع" }
        """
        submission = self.get_object()
        reject_serializer = SubmissionRejectSerializer(data=request.data)
        reject_serializer.is_valid(raise_exception=True)

        try:
            submission = SubmissionService.reject_by_planning(
                submission=submission,
                user=request.user,
                reason=reject_serializer.validated_data['reason'],
            )
        except (DjangoValidationError, DjangoPermissionDenied) as exc:
            return _service_error_response(exc)

        serializer = WeeklySubmissionSerializer(submission)
        return Response(serializer.data)

    # ─── مراجعة الإحصاء: اعتماد ───────────────
    @action(
        detail=True, methods=['post'], url_path='admin-approve',
        permission_classes=[permissions.IsAuthenticated, IsStatisticsAdmin],
    )
    def admin_approve(self, request, pk=None):
        """
        اعتماد المنجز من الإحصاء — POST /api/submissions/{id}/admin-approve/
        لا يتطلّب سبباً. يُقفل المنجز من أي مراجعة أخرى من موظّفي الإحصاء.
        """
        submission = self.get_object()
        try:
            submission = SubmissionAdminService.approve(submission, request.user)
        except (DjangoValidationError, DjangoPermissionDenied) as exc:
            return _service_error_response(exc)

        serializer = WeeklySubmissionSerializer(submission)
        return Response(serializer.data)

    # ─── مراجعة الإحصاء: تعديل ────────────────
    @action(
        detail=True, methods=['post'], url_path='admin-edit',
        permission_classes=[permissions.IsAuthenticated, IsStatisticsAdmin],
    )
    def admin_edit(self, request, pk=None):
        """
        تعديل المنجز من الإحصاء — POST /api/submissions/{id}/admin-edit/
        body: {
            "reason": "سبب التعديل (إلزامي)",
            "answer_edits": [
                {"answer_id": 42, "numeric_value": 150},
                {"answer_id": 43, "text_value": "نص جديد"}
            ]
        }
        """
        submission = self.get_object()
        reason = request.data.get('reason', '')
        answer_edits = request.data.get('answer_edits', [])

        try:
            submission = SubmissionAdminService.edit(
                submission=submission,
                user=request.user,
                answer_edits=answer_edits,
                reason=reason,
            )
        except (DjangoValidationError, DjangoPermissionDenied) as exc:
            return _service_error_response(exc)

        serializer = WeeklySubmissionSerializer(submission)
        return Response(serializer.data)

    # ─── مراجعة الإحصاء: إرجاع للتخطيط ───────
    @action(
        detail=True, methods=['post'], url_path='admin-return',
        permission_classes=[permissions.IsAuthenticated, IsStatisticsAdmin],
    )
    def admin_return(self, request, pk=None):
        """
        إرجاع المنجز من الإحصاء للتخطيط — POST /api/submissions/{id}/admin-return/
        body: { "reason": "سبب الإرجاع (إلزامي)" }
        """
        submission = self.get_object()
        reason = request.data.get('reason', '')

        try:
            submission = SubmissionAdminService.return_to_planning(
                submission=submission,
                user=request.user,
                reason=reason,
            )
        except (DjangoValidationError, DjangoPermissionDenied) as exc:
            return _service_error_response(exc)

        serializer = WeeklySubmissionSerializer(submission)
        return Response(serializer.data)

    # ─── سجلّ التدقيق للمنجز ──────────────────
    @action(detail=True, methods=['get'], url_path='audit-log')
    def audit_log(self, request, pk=None):
        """
        سجلّ التدقيق للمنجز — GET /api/submissions/{id}/audit-log/
        مسموح لـ: مدير القسم الذي أرسله، قسم التخطيط ضمن نطاقه، ومدير الإحصاء.
        """
        from apps.audit.models import AuditLog
        submission = self.get_object()
        user = request.user

        # فحص الصلاحية
        allowed = False
        if user.role == 'statistics_admin':
            allowed = True
        elif user.role == 'section_manager' and submission.qism_id == user.unit_id:
            allowed = True
        elif user.role == 'planning_section':
            scope_ids = _planning_section_scope_qism_ids(user)
            if scope_ids is None or submission.qism_id in scope_ids:
                allowed = True

        if not allowed:
            return Response(
                {
                    'error': True,
                    'message': 'ليس لديك صلاحية لعرض سجلّ التدقيق لهذا المنجز.',
                    'code': 'PERMISSION_DENIED',
                    'details': {},
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        entries = AuditLog.objects.filter(
            target_model='WeeklySubmission',
            target_id=submission.pk,
        ).select_related('actor').order_by('-created_at')

        data = [
            {
                'id': e.id,
                'action_type': e.action_type,
                'action_label': e.get_action_type_display(),
                'actor_id': e.actor_id,
                'actor_name': e.actor.full_name if e.actor else 'النظام',
                'actor_role': e.actor_role,
                'field_changes': e.field_changes,
                'reason': e.reason,
                'metadata': e.metadata,
                'created_at': e.created_at.isoformat(),
            }
            for e in entries
        ]
        return Response({'results': data})

    # ─── قائمة المنجزات بانتظار مراجعة الإحصاء ───
    @action(
        detail=False, methods=['get'], url_path='pending-admin-review',
        permission_classes=[permissions.IsAuthenticated, IsStatisticsAdmin],
    )
    def pending_admin_review(self, request):
        """
        قائمة المنجزات المعتمَدة من التخطيط وبانتظار مراجعة الإحصاء.
        تدعم فلاتر: week, year, daira_id, mudiriya_id, qism_id, reviewed
        """
        qs = WeeklySubmission.objects.filter(
            status=WeeklySubmission.Status.APPROVED,
        ).select_related(
            'qism', 'qism__parent', 'weekly_period',
            'planning_approved_by', 'admin_reviewed_by', 'form_template',
        ).prefetch_related(
            'answers__form_item__indicator',
        )

        # فلتر: reviewed = true يعرض فقط المراجَعة، false يعرض غير المراجَعة
        reviewed_param = request.query_params.get('reviewed')
        if reviewed_param == 'true':
            qs = qs.filter(admin_reviewed_at__isnull=False)
        elif reviewed_param == 'false':
            qs = qs.filter(admin_reviewed_at__isnull=True)

        week = request.query_params.get('week')
        year = request.query_params.get('year')
        if week:
            qs = qs.filter(weekly_period__week_number=week)
        if year:
            qs = qs.filter(weekly_period__year=year)

        qism_id = request.query_params.get('qism_id')
        if qism_id:
            qs = qs.filter(qism_id=qism_id)

        mudiriya_id = request.query_params.get('mudiriya_id')
        if mudiriya_id:
            qs = qs.filter(qism__parent_id=mudiriya_id)

        daira_id = request.query_params.get('daira_id')
        if daira_id:
            from apps.organization.models import OrganizationUnit
            daira = OrganizationUnit.objects.filter(
                pk=daira_id, unit_type='daira'
            ).first()
            if daira:
                descendant_ids = list(
                    daira.get_descendants(include_self=False)
                    .filter(unit_type='qism')
                    .values_list('id', flat=True)
                )
                qs = qs.filter(qism_id__in=descendant_ids)
            else:
                qs = qs.none()

        qs = qs.order_by(
            '-weekly_period__year', '-weekly_period__week_number',
            'qism__parent__name', 'qism__name',
        )

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = WeeklySubmissionSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = WeeklySubmissionSerializer(qs, many=True)
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

    def get_permissions(self):
        if self.action in ['approve', 'reject']:
            return [permissions.IsAuthenticated(), IsStatisticsAdmin()]
        return [permissions.IsAuthenticated()]

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
            scope_ids = _planning_section_scope_qism_ids(user)
            if scope_ids is not None:  # None = نطاق مركزي يشمل الجميع
                queryset = queryset.filter(
                    submission__qism_id__in=scope_ids
                )
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

        try:
            answer = QualitativeService.approve_qualitative(answer, request.user)
        except (DjangoValidationError, DjangoPermissionDenied) as exc:
            return _service_error_response(exc)

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

        reject_serializer = QualitativeRejectSerializer(data=request.data)
        reject_serializer.is_valid(raise_exception=True)

        try:
            answer = QualitativeService.reject_qualitative(
                answer=answer,
                user=request.user,
                reason=reject_serializer.validated_data['rejection_reason'],
            )
        except (DjangoValidationError, DjangoPermissionDenied) as exc:
            return _service_error_response(exc)

        serializer = QualitativeAnswerSerializer(answer)
        return Response(serializer.data)
