"""
طبقة الخدمات لتطبيق المنجزات — منطق الأعمال لإدارة الفترات الأسبوعية والمنجزات والتمديدات والتجميع.
"""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Avg, Max, Sum
from django.utils import timezone

from apps.organization.models import OrganizationUnit, UnitType

from .models import (
    QismExtension,
    SubmissionAnswer,
    WeeklyPeriod,
    WeeklySubmission,
)


class WeeklyPeriodService:
    """خدمة إدارة الفترات الأسبوعية"""

    @staticmethod
    @transaction.atomic
    def create_period(data, created_by):
        """
        إنشاء فترة أسبوعية جديدة.
        - التحقق من أن رقم الأسبوع بين 1 و 53
        - التحقق من عدم وجود فترة مكررة لنفس السنة ورقم الأسبوع
        - إنشاء إشعارات لجميع الأقسام النشطة
        """
        week_number = data.get('week_number')
        year = data.get('year')

        # التحقق من صحة رقم الأسبوع
        if week_number is None or week_number < 1 or week_number > 53:
            raise ValidationError({
                'week_number': 'رقم الأسبوع يجب أن يكون بين 1 و 53'
            })

        # التحقق من عدم وجود فترة مكررة
        if WeeklyPeriod.objects.filter(year=year, week_number=week_number).exists():
            raise ValidationError({
                'week_number': f'الأسبوع {week_number} للسنة {year} موجود مسبقاً'
            })

        period = WeeklyPeriod(**data)
        period.created_by = created_by
        period.full_clean()
        period.save()

        # إرسال إشعارات لجميع مديري الأقسام النشطة
        try:
            _notify_period_opened(period)
        except Exception:
            import logging
            logging.getLogger(__name__).warning("فشل إرسال إشعار فتح الفترة", exc_info=True)

        return period

    @staticmethod
    @transaction.atomic
    def close_period(period, user):
        """
        إغلاق فترة أسبوعية.
        - تغيير الحالة إلى 'مغلق'
        - تسجيل الأقسام التي لم ترسل منجزاتها كـ 'متأخر'
        """
        if period.status == WeeklyPeriod.Status.CLOSED:
            raise ValidationError('هذه الفترة مغلقة مسبقاً')

        period.status = WeeklyPeriod.Status.CLOSED
        period.save(update_fields=['status'])

        # الحصول على الأقسام العادية النشطة التي لم ترسل منجزاتها
        active_regular_qisms = OrganizationUnit.objects.filter(
            unit_type=UnitType.QISM,
            qism_role='regular',
            is_active=True,
        )

        submitted_qism_ids = WeeklySubmission.objects.filter(
            weekly_period=period,
            status__in=[
                WeeklySubmission.Status.SUBMITTED,
                WeeklySubmission.Status.APPROVED,
            ],
        ).values_list('qism_id', flat=True)

        non_submitted_qisms = active_regular_qisms.exclude(
            id__in=submitted_qism_ids
        )

        # تسجيل الأقسام المتأخرة
        for qism in non_submitted_qisms:
            submission = WeeklySubmission.objects.filter(
                qism=qism, weekly_period=period
            ).first()

            if submission:
                # تحديث حالة المنجز الموجود إلى متأخر
                submission.status = WeeklySubmission.Status.LATE
                submission.save(update_fields=['status'])
            else:
                # إنشاء منجز بحالة متأخر
                from apps.forms.models import FormTemplate

                active_template = FormTemplate.objects.filter(
                    qism=qism,
                    status=FormTemplate.Status.APPROVED,
                ).order_by('-version').first()

                if active_template:
                    WeeklySubmission.objects.create(
                        qism=qism,
                        weekly_period=period,
                        form_template=active_template,
                        status=WeeklySubmission.Status.LATE,
                    )

            # إرسال إشعار تأخر
            try:
                _notify_submission_late(qism, period)
            except Exception:
                import logging
                logging.getLogger(__name__).warning("فشل إرسال إشعار التأخر", exc_info=True)

        return period


class SubmissionService:
    """خدمة إدارة المنجزات الأسبوعية"""

    @staticmethod
    @transaction.atomic
    def get_or_create_submission(qism, weekly_period):
        """
        الحصول على أو إنشاء منجز لقسم وفترة محددة.
        في حالة الإنشاء، يتم البحث عن قالب الاستمارة النشط للقسم.
        """
        submission = WeeklySubmission.objects.filter(
            qism=qism, weekly_period=weekly_period
        ).first()

        if submission:
            return submission, False

        from apps.forms.models import FormTemplate

        # البحث عن القالب النشط الساري لهذا الأسبوع
        active_template = FormTemplate.objects.filter(
            qism=qism,
            status=FormTemplate.Status.APPROVED,
        ).filter(
            # القالب يجب أن يكون سارياً (effective_from_week/year <= الفترة الحالية)
            effective_from_year__lte=weekly_period.year,
        ).filter(
            # إما أن يكون من سنة سابقة أو من نفس السنة لكن أسبوع سابق أو نفسه
            effective_from_year__lt=weekly_period.year,
        ).union(
            FormTemplate.objects.filter(
                qism=qism,
                status=FormTemplate.Status.APPROVED,
                effective_from_year=weekly_period.year,
                effective_from_week__lte=weekly_period.week_number,
            )
        ).order_by('-effective_from_year', '-effective_from_week').first()

        # إذا لم يوجد بالطريقة أعلاه، نبحث بطريقة بديلة
        if not active_template:
            active_template = FormTemplate.objects.filter(
                qism=qism,
                status=FormTemplate.Status.APPROVED,
            ).order_by('-version').first()

        if not active_template:
            raise ValidationError(
                'لا يوجد قالب استمارة معتمد لهذا القسم'
            )

        submission = WeeklySubmission.objects.create(
            qism=qism,
            weekly_period=weekly_period,
            form_template=active_template,
            status=WeeklySubmission.Status.DRAFT,
        )

        return submission, True

    @staticmethod
    @transaction.atomic
    def save_answers(submission, answers_data):
        """
        حفظ أو تحديث إجابات المنجز.
        يعمل فقط إذا كان المنجز قابلاً للتعديل.
        answers_data: قائمة من القواميس بالشكل:
        [
            {
                'form_item_id': int,
                'numeric_value': float | None,
                'text_value': str,
                'is_qualitative': bool,
                'qualitative_details': str,
            },
            ...
        ]
        """
        # قفل السجل لمنع التعارضات المتزامنة
        submission = WeeklySubmission.objects.select_for_update().get(pk=submission.pk)

        if not submission.is_editable():
            raise ValidationError(
                'لا يمكن تعديل هذا المنجز - الموعد النهائي قد انتهى أو الفترة مغلقة'
            )

        saved_answers = []
        for answer_data in answers_data:
            form_item_id = answer_data.get('form_item_id')

            # التحقق من أن بند الاستمارة ينتمي لقالب المنجز
            if not submission.form_template.items.filter(id=form_item_id).exists():
                raise ValidationError(
                    f'بند الاستمارة رقم {form_item_id} لا ينتمي لقالب هذا المنجز'
                )

            # تحديد حالة المنجز النوعي
            qualitative_status = SubmissionAnswer.QualitativeStatus.NONE
            if answer_data.get('is_qualitative', False):
                qualitative_status = SubmissionAnswer.QualitativeStatus.PENDING_PLANNING

            answer, _created = SubmissionAnswer.objects.update_or_create(
                submission=submission,
                form_item_id=form_item_id,
                defaults={
                    'numeric_value': answer_data.get('numeric_value'),
                    'text_value': answer_data.get('text_value', ''),
                    'is_qualitative': answer_data.get('is_qualitative', False),
                    'qualitative_details': answer_data.get('qualitative_details', ''),
                    'qualitative_status': qualitative_status,
                },
            )
            answer.full_clean()
            answer.save()
            saved_answers.append(answer)

        return saved_answers

    @staticmethod
    @transaction.atomic
    def submit(submission, user):
        """
        إرسال المنجز (مسودة → مُرسل).
        - التحقق من أن الحالة الحالية مسودة أو مُمدَّد
        - التحقق من أن جميع الحقول الإلزامية مُعبأة
        - تحديث تاريخ الإرسال
        - إرسال إشعار لقسم التخطيط
        """
        # قفل السجل لمنع التعارضات المتزامنة
        submission = WeeklySubmission.objects.select_for_update().get(pk=submission.pk)

        valid_statuses = [
            WeeklySubmission.Status.DRAFT,
            WeeklySubmission.Status.EXTENDED,
        ]
        if submission.status not in valid_statuses:
            raise ValidationError(
                'لا يمكن إرسال هذا المنجز - الحالة الحالية غير مسموح بها'
            )

        if not submission.is_editable():
            raise ValidationError(
                'لا يمكن إرسال هذا المنجز - الموعد النهائي قد انتهى أو الفترة مغلقة'
            )

        # التحقق من الحقول الإلزامية
        mandatory_items = submission.form_template.items.filter(
            is_mandatory=True
        )
        for item in mandatory_items:
            answer = SubmissionAnswer.objects.filter(
                submission=submission, form_item=item
            ).first()

            if not answer:
                raise ValidationError(
                    f'الحقل الإلزامي "{item.indicator.name}" لم يتم تعبئته'
                )

            # التحقق من وجود قيمة فعلية
            if item.indicator.is_numeric:
                if answer.numeric_value is None:
                    raise ValidationError(
                        f'الحقل الإلزامي "{item.indicator.name}" لم يتم تعبئته بقيمة رقمية'
                    )
            else:
                if not answer.text_value.strip():
                    raise ValidationError(
                        f'الحقل الإلزامي "{item.indicator.name}" لم يتم تعبئته بقيمة نصية'
                    )

        submission.status = WeeklySubmission.Status.SUBMITTED
        submission.submitted_at = timezone.now()
        submission.save(update_fields=['status', 'submitted_at'])

        # إرسال إشعار لقسم التخطيط
        try:
            _notify_submission_received(submission)
        except Exception:
            import logging
            logging.getLogger(__name__).warning("فشل إرسال إشعار استلام المنجز", exc_info=True)

        return submission

    @staticmethod
    @transaction.atomic
    def approve(submission, user):
        """
        اعتماد المنجز بواسطة قسم التخطيط (مُرسل → معتمد).
        - تحديث بيانات الاعتماد
        - نقل المنجزات النوعية من pending_planning إلى pending_statistics
        - إرسال إشعار
        """
        if submission.status != WeeklySubmission.Status.SUBMITTED:
            raise ValidationError(
                'لا يمكن اعتماد هذا المنجز - يجب أن يكون بحالة "مُرسل"'
            )

        submission.status = WeeklySubmission.Status.APPROVED
        submission.planning_approved_by = user
        submission.planning_approved_at = timezone.now()
        submission.save(update_fields=[
            'status', 'planning_approved_by', 'planning_approved_at'
        ])

        # نقل المنجزات النوعية إلى المرحلة التالية
        qualitative_answers = submission.answers.filter(
            is_qualitative=True,
            qualitative_status=SubmissionAnswer.QualitativeStatus.PENDING_PLANNING,
        )
        for answer in qualitative_answers:
            answer.qualitative_status = SubmissionAnswer.QualitativeStatus.PENDING_STATISTICS
            answer.save(update_fields=['qualitative_status'])

        # إرسال إشعار اعتماد المنجز
        try:
            _notify_submission_approved(submission)
        except Exception:
            import logging
            logging.getLogger(__name__).warning("فشل إرسال إشعار اعتماد المنجز", exc_info=True)

        # إرسال إشعار للمنجزات النوعية المعلقة (لمدير قسم الإحصاء)
        try:
            if qualitative_answers.exists():
                _notify_qualitative_pending(submission)
        except Exception:
            import logging
            logging.getLogger(__name__).warning("فشل إرسال إشعار المنجزات النوعية", exc_info=True)

        return submission


class QismExtensionService:
    """خدمة إدارة تمديدات المواعيد"""

    @staticmethod
    @transaction.atomic
    def grant_extension(data, granted_by):
        """
        منح تمديد لقسم معين.
        - التحقق من أن الموعد الجديد بعد الموعد الأصلي
        - تحديث حالة المنجز إلى 'مُمدَّد' إن وجد
        - إرسال إشعار
        """
        qism = data.get('qism')
        weekly_period = data.get('weekly_period')
        new_deadline = data.get('new_deadline')

        if not qism or not weekly_period or not new_deadline:
            raise ValidationError('يجب تحديد القسم والفترة الأسبوعية والموعد الجديد')

        # التحقق من أن الموعد الجديد بعد الموعد الأصلي
        if new_deadline <= weekly_period.deadline:
            raise ValidationError({
                'new_deadline': 'الموعد الجديد يجب أن يكون بعد الموعد الأصلي'
            })

        # التحقق من عدم وجود تمديد مسبق
        if QismExtension.objects.filter(
            qism=qism, weekly_period=weekly_period
        ).exists():
            raise ValidationError(
                'يوجد تمديد مسبق لهذا القسم في هذه الفترة'
            )

        extension = QismExtension(
            qism=qism,
            weekly_period=weekly_period,
            new_deadline=new_deadline,
            reason=data.get('reason', ''),
            granted_by=granted_by,
        )
        extension.full_clean()
        extension.save()

        # تحديث حالة المنجز إلى مُمدَّد إن وجد
        submission = WeeklySubmission.objects.filter(
            qism=qism, weekly_period=weekly_period
        ).first()
        if submission and submission.status in [
            WeeklySubmission.Status.DRAFT,
            WeeklySubmission.Status.LATE,
        ]:
            submission.status = WeeklySubmission.Status.EXTENDED
            submission.save(update_fields=['status'])

        # إرسال إشعار
        try:
            _notify_extension_granted(extension)
        except Exception:
            import logging
            logging.getLogger(__name__).warning("فشل إرسال إشعار التمديد", exc_info=True)

        return extension


class AggregationService:
    """خدمة تجميع البيانات"""

    @staticmethod
    def aggregate(answers, accumulation_type):
        """
        تجميع قائمة من الإجابات بناءً على طريقة التجميع.
        answers: قائمة من SubmissionAnswer أو قيم رقمية
        accumulation_type: 'sum' | 'average' | 'last_value'
        """
        from apps.indicators.models import Indicator

        # استخراج القيم الرقمية
        if not answers:
            return None

        values = []
        for answer in answers:
            if isinstance(answer, SubmissionAnswer):
                if answer.numeric_value is not None:
                    values.append(answer.numeric_value)
            elif isinstance(answer, (int, float)):
                values.append(answer)

        if not values:
            return None

        if accumulation_type == Indicator.AccumulationType.SUM:
            return sum(values)
        elif accumulation_type == Indicator.AccumulationType.AVERAGE:
            return sum(values) / len(values)
        elif accumulation_type == Indicator.AccumulationType.LAST_VALUE:
            return values[-1]

        return None

    @staticmethod
    def aggregate_for_period(qism_id, indicator_id, period_type, year, period_number):
        """
        حساب القيمة المجمعة لمؤشر في فترة معينة.
        period_type: 'weekly' | 'monthly' | 'quarterly' | 'semi_annual' | 'annual'
        period_number: رقم الفترة (رقم الأسبوع، الشهر، الربع، النصف)
        """
        from apps.indicators.models import Indicator

        try:
            indicator = Indicator.objects.get(id=indicator_id)
        except Indicator.DoesNotExist:
            raise ValidationError('المؤشر غير موجود')

        # المؤشرات النصية لا تُجمَّع
        if not indicator.is_numeric:
            return None

        # تحديد نطاق الأسابيع حسب نوع الفترة
        week_ranges = _get_week_range(period_type, year, period_number)
        if not week_ranges:
            return None

        start_week, end_week = week_ranges

        # الحصول على الإجابات ضمن النطاق
        answers = SubmissionAnswer.objects.filter(
            submission__qism_id=qism_id,
            submission__weekly_period__year=year,
            submission__weekly_period__week_number__gte=start_week,
            submission__weekly_period__week_number__lte=end_week,
            submission__status__in=[
                WeeklySubmission.Status.SUBMITTED,
                WeeklySubmission.Status.APPROVED,
            ],
            form_item__indicator_id=indicator_id,
            numeric_value__isnull=False,
        ).order_by('submission__weekly_period__week_number')

        if not answers.exists():
            return None

        # التجميع حسب النوع
        if indicator.accumulation_type == Indicator.AccumulationType.SUM:
            result = answers.aggregate(total=Sum('numeric_value'))
            return result['total']
        elif indicator.accumulation_type == Indicator.AccumulationType.AVERAGE:
            result = answers.aggregate(avg=Avg('numeric_value'))
            return result['avg']
        elif indicator.accumulation_type == Indicator.AccumulationType.LAST_VALUE:
            last_answer = answers.last()
            return last_answer.numeric_value if last_answer else None

        return None

    @staticmethod
    def aggregate_hierarchy(unit, indicator, year):
        """
        تجميع القيم على مستوى الهرمي (مديرية/دائرة).
        يجمع قيم الأقسام التابعة.
        """
        from apps.indicators.models import Indicator

        # المؤشرات النصية لا تُجمَّع
        if not indicator.is_numeric:
            return None

        # إذا كان القسم نفسه (مستوى القسم)
        if unit.unit_type == UnitType.QISM:
            # إرجاع مجموع القيم الأسبوعية للسنة
            answers = SubmissionAnswer.objects.filter(
                submission__qism=unit,
                submission__weekly_period__year=year,
                submission__status__in=[
                    WeeklySubmission.Status.SUBMITTED,
                    WeeklySubmission.Status.APPROVED,
                ],
                form_item__indicator=indicator,
                numeric_value__isnull=False,
            ).order_by('submission__weekly_period__week_number')

            return AggregationService.aggregate(
                list(answers), indicator.accumulation_type
            )

        # للمديرية أو الدائرة: تجميع قيم الأقسام التابعة
        child_qisms = OrganizationUnit.objects.filter(
            unit_type=UnitType.QISM,
            qism_role='regular',
            is_active=True,
        )

        if unit.unit_type == UnitType.MUDIRIYA:
            # الأقسام التابعة للمديرية مباشرة
            child_qisms = child_qisms.filter(parent=unit)
        elif unit.unit_type == UnitType.DAIRA:
            # الأقسام التابعة للدائرة مباشرة أو عبر مديرياتها
            from django.db.models import Q
            mudiriyas = OrganizationUnit.objects.filter(
                parent=unit, unit_type=UnitType.MUDIRIYA, is_active=True
            )
            child_qisms = child_qisms.filter(
                Q(parent=unit) | Q(parent__in=mudiriyas)
            )
        else:
            return None

        if not child_qisms.exists():
            return None

        # تجميع قيم كل قسم
        qism_values = []
        for qism in child_qisms:
            qism_value = AggregationService.aggregate_hierarchy(
                qism, indicator, year
            )
            if qism_value is not None:
                qism_values.append(qism_value)

        if not qism_values:
            return None

        # تجميع القيم حسب نوع التجميع
        return AggregationService.aggregate(
            qism_values, indicator.accumulation_type
        )


class QualitativeService:
    """خدمة إدارة المنجزات النوعية"""

    @staticmethod
    @transaction.atomic
    def approve_qualitative(answer, user):
        """
        اعتماد المنجز النوعي (pending_statistics → approved).
        """
        if answer.qualitative_status != SubmissionAnswer.QualitativeStatus.PENDING_STATISTICS:
            raise ValidationError(
                'لا يمكن اعتماد هذا المنجز النوعي - يجب أن يكون بحالة "بانتظار اعتماد الإحصاء"'
            )

        answer.qualitative_status = SubmissionAnswer.QualitativeStatus.APPROVED
        answer.qualitative_approved_by = user
        answer.qualitative_approved_at = timezone.now()
        answer.save(update_fields=[
            'qualitative_status', 'qualitative_approved_by', 'qualitative_approved_at'
        ])

        # إرسال إشعار
        try:
            _notify_qualitative_approved(answer)
        except Exception:
            import logging
            logging.getLogger(__name__).warning("فشل إرسال إشعار اعتماد النوعي", exc_info=True)

        return answer

    @staticmethod
    @transaction.atomic
    def reject_qualitative(answer, user, reason):
        """
        رفض المنجز النوعي (pending_statistics → rejected).
        """
        if answer.qualitative_status != SubmissionAnswer.QualitativeStatus.PENDING_STATISTICS:
            raise ValidationError(
                'لا يمكن رفض هذا المنجز النوعي - يجب أن يكون بحالة "بانتظار اعتماد الإحصاء"'
            )

        if not reason or not reason.strip():
            raise ValidationError({
                'reason': 'يجب تحديد سبب الرفض'
            })

        answer.qualitative_status = SubmissionAnswer.QualitativeStatus.REJECTED
        answer.rejection_reason = reason
        answer.qualitative_approved_by = user
        answer.qualitative_approved_at = timezone.now()
        answer.save(update_fields=[
            'qualitative_status', 'rejection_reason',
            'qualitative_approved_by', 'qualitative_approved_at',
        ])

        # إرسال إشعار
        try:
            _notify_qualitative_rejected(answer)
        except Exception:
            import logging
            logging.getLogger(__name__).warning("فشل إرسال إشعار رفض النوعي", exc_info=True)

        return answer


# ========================================
# دوال الإشعارات المساعدة (الداخلية)
# ========================================


def _notify_period_opened(period):
    """إرسال إشعارات فتح فترة أسبوعية جديدة لجميع مديري الأقسام النشطة"""
    from apps.notifications.services import NotificationService

    from apps.accounts.models import User, UserRole

    # إشعار لجميع مديري الأقسام العادية
    section_managers = User.objects.filter(
        role=UserRole.SECTION_MANAGER,
        is_active=True,
    )
    for manager in section_managers:
        NotificationService.create_notification(
            recipient=manager,
            notification_type='period_opened',
            title='فتح أسبوع جديد',
            message=f'تم فتح {period} للإدخال. الموعد النهائي: {period.deadline.strftime("%Y-%m-%d %H:%M")}',
            related_model='WeeklyPeriod',
            related_id=period.id,
        )


def _notify_submission_late(qism, period):
    """إرسال إشعار تأخر في التسليم"""
    from apps.notifications.services import NotificationService

    from apps.accounts.models import User, UserRole

    managers = User.objects.filter(
        unit=qism,
        role=UserRole.SECTION_MANAGER,
        is_active=True,
    )
    for manager in managers:
        NotificationService.create_notification(
            recipient=manager,
            notification_type='submission_late',
            title='تأخر في التسليم',
            message=f'لم يتم إرسال منجز {qism.name} لـ {period}. تم تسجيله كمتأخر.',
            related_model='WeeklyPeriod',
            related_id=period.id,
        )


def _notify_submission_received(submission):
    """إرسال إشعار استلام منجز لقسم التخطيط"""
    from apps.notifications.services import NotificationService

    from apps.accounts.models import User, UserRole

    # إيجاد قسم التخطيط التابع لنفس المديرية/الدائرة
    parent_unit = submission.qism.parent
    if parent_unit:
        planning_users = User.objects.filter(
            role=UserRole.PLANNING_SECTION,
            is_active=True,
            unit__parent=parent_unit,
        )
        for planner in planning_users:
            NotificationService.create_notification(
                recipient=planner,
                notification_type='submission_received',
                title='استلام منجز',
                message=f'تم استلام منجز {submission.qism.name} لـ {submission.weekly_period}',
                related_model='WeeklySubmission',
                related_id=submission.id,
            )


def _notify_submission_approved(submission):
    """إرسال إشعار اعتماد المنجز لمدير القسم"""
    from apps.notifications.services import NotificationService

    from apps.accounts.models import User, UserRole

    managers = User.objects.filter(
        unit=submission.qism,
        role=UserRole.SECTION_MANAGER,
        is_active=True,
    )
    for manager in managers:
        NotificationService.create_notification(
            recipient=manager,
            notification_type='submission_approved',
            title='اعتماد المنجز',
            message=f'تم اعتماد منجز {submission.qism.name} لـ {submission.weekly_period}',
            related_model='WeeklySubmission',
            related_id=submission.id,
        )


def _notify_qualitative_pending(submission):
    """إرسال إشعار وجود منجزات نوعية بانتظار اعتماد الإحصاء"""
    from apps.notifications.services import NotificationService

    from apps.accounts.models import User, UserRole

    stats_admins = User.objects.filter(
        role=UserRole.STATISTICS_ADMIN,
        is_active=True,
    )
    for admin in stats_admins:
        NotificationService.create_notification(
            recipient=admin,
            notification_type='qualitative_pending',
            title='منجز نوعي بانتظار الاعتماد',
            message=f'يوجد منجزات نوعية من {submission.qism.name} لـ {submission.weekly_period} بانتظار اعتمادكم',
            related_model='WeeklySubmission',
            related_id=submission.id,
        )


def _notify_extension_granted(extension):
    """إرسال إشعار منح تمديد"""
    from apps.notifications.services import NotificationService

    from apps.accounts.models import User, UserRole

    managers = User.objects.filter(
        unit=extension.qism,
        role=UserRole.SECTION_MANAGER,
        is_active=True,
    )
    for manager in managers:
        NotificationService.create_notification(
            recipient=manager,
            notification_type='extension_granted',
            title='منح تمديد',
            message=(
                f'تم منح تمديد لقسم {extension.qism.name} لـ {extension.weekly_period}. '
                f'الموعد الجديد: {extension.new_deadline.strftime("%Y-%m-%d %H:%M")}'
            ),
            related_model='QismExtension',
            related_id=extension.id,
        )


def _notify_qualitative_approved(answer):
    """إرسال إشعار اعتماد المنجز النوعي"""
    from apps.notifications.services import NotificationService

    from apps.accounts.models import User, UserRole

    managers = User.objects.filter(
        unit=answer.submission.qism,
        role=UserRole.SECTION_MANAGER,
        is_active=True,
    )
    for manager in managers:
        NotificationService.create_notification(
            recipient=manager,
            notification_type='qualitative_approved',
            title='اعتماد المنجز النوعي',
            message=(
                f'تم اعتماد المنجز النوعي "{answer.form_item.indicator.name}" '
                f'لـ {answer.submission.weekly_period}'
            ),
            related_model='SubmissionAnswer',
            related_id=answer.id,
        )


def _notify_qualitative_rejected(answer):
    """إرسال إشعار رفض المنجز النوعي"""
    from apps.notifications.services import NotificationService

    from apps.accounts.models import User, UserRole

    managers = User.objects.filter(
        unit=answer.submission.qism,
        role=UserRole.SECTION_MANAGER,
        is_active=True,
    )
    for manager in managers:
        NotificationService.create_notification(
            recipient=manager,
            notification_type='qualitative_rejected',
            title='رفض المنجز النوعي',
            message=(
                f'تم رفض المنجز النوعي "{answer.form_item.indicator.name}" '
                f'لـ {answer.submission.weekly_period}. '
                f'السبب: {answer.rejection_reason}'
            ),
            related_model='SubmissionAnswer',
            related_id=answer.id,
        )


# ========================================
# دوال مساعدة
# ========================================


def _get_week_range(period_type, year, period_number):
    """
    تحديد نطاق الأسابيع حسب نوع الفترة.
    يُرجع (start_week, end_week) أو None.
    """
    if period_type == 'weekly':
        return (period_number, period_number)
    elif period_type == 'monthly':
        # تقريب: كل شهر يحتوي على ~4.33 أسابيع
        start_week = (period_number - 1) * 4 + 1
        end_week = period_number * 4 + (1 if period_number == 12 else 0)
        return (start_week, min(end_week, 53))
    elif period_type == 'quarterly':
        # كل ربع يحتوي على 13 أسبوع
        start_week = (period_number - 1) * 13 + 1
        end_week = period_number * 13
        return (start_week, min(end_week, 53))
    elif period_type == 'semi_annual':
        # كل نصف سنة يحتوي على 26 أسبوع
        start_week = (period_number - 1) * 26 + 1
        end_week = period_number * 26
        return (start_week, min(end_week, 53))
    elif period_type == 'annual':
        return (1, 53)
    return None
