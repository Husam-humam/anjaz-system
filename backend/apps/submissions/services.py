"""
طبقة الخدمات لتطبيق المنجزات — منطق الأعمال لإدارة الفترات الأسبوعية والمنجزات والتمديدات والتجميع.
"""
import datetime

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Avg, Sum
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.audit.services import AuditService
from apps.organization.models import OrganizationUnit, UnitType

from .models import (
    QismExtension,
    SubmissionAnswer,
    SystemConfiguration,
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
        - يرفض الإغلاق إذا كانت هناك تمديدات سارية لم تنته
        - تغيير الحالة إلى 'مغلق'
        - تسجيل الأقسام التي لم ترسل منجزاتها كـ 'متأخر'
        - معالجة المنجزات في حالة EXTENDED أو DRAFT
        """
        if period.status == WeeklyPeriod.Status.CLOSED:
            raise ValidationError('هذه الفترة مغلقة مسبقاً')

        # منع الإغلاق إذا كانت هناك تمديدات لم تنته بعد
        now = timezone.now()
        active_extensions = QismExtension.objects.filter(
            weekly_period=period,
            new_deadline__gt=now,
        )
        if active_extensions.exists():
            qisms_with_active_ext = list(
                active_extensions.values_list('qism__name', flat=True)
            )
            raise ValidationError({
                'extensions': (
                    f'لا يمكن إغلاق الفترة - هناك تمديدات سارية لم تنته بعد: '
                    f'{", ".join(qisms_with_active_ext)}'
                )
            })

        period.status = WeeklyPeriod.Status.CLOSED
        period.save(update_fields=['status'])

        # تعليم المنجزات في حالة DRAFT أو EXTENDED بأنها متأخرة
        WeeklySubmission.objects.filter(
            weekly_period=period,
            status__in=[
                WeeklySubmission.Status.DRAFT,
                WeeklySubmission.Status.EXTENDED,
                WeeklySubmission.Status.RETURNED,
            ],
        ).update(status=WeeklySubmission.Status.LATE)

        # الحصول على الأقسام العادية النشطة التي لم ترسل منجزاتها أبداً
        active_regular_qisms = OrganizationUnit.objects.filter(
            unit_type=UnitType.QISM,
            qism_role='regular',
            is_active=True,
        )

        any_submission_qism_ids = set(
            WeeklySubmission.objects.filter(
                weekly_period=period,
            ).values_list('qism_id', flat=True)
        )

        non_submitted_qisms = active_regular_qisms.exclude(
            id__in=any_submission_qism_ids
        )

        from apps.forms.services import FormTemplateService

        # إنشاء منجز بحالة "متأخر" للأقسام التي لم تنشئ منجزاً
        for qism in non_submitted_qisms:
            try:
                active_template = FormTemplateService.get_active_template(
                    qism_id=qism.id,
                    year=period.year,
                    week_number=period.week_number,
                )
            except ValidationError:
                # القسم بدون قالب فعّال — نتجاوزه بدل تعطيل الإغلاق
                continue

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


class PeriodAutoService:
    """
    خدمة الإدارة التلقائية للأسابيع.
    تتحكّم بترقيم الأسابيع وفقاً للإعدادات (يوم البداية) وتُنشئ الأسبوع الحالي
    تلقائياً، وتُغلق الأسبوع السابق بعد مرور الموعد النهائي.
    """

    # ──────────────────────────────────────────
    # دوال الحساب النقي (بدون آثار جانبية)
    # ──────────────────────────────────────────

    @staticmethod
    def compute_week_start(date, start_day):
        """
        تُرجع تاريخ بداية الأسبوع الذي ينتمي إليه `date` بناءً على `start_day`.
        start_day: 0=الاثنين .. 5=السبت .. 6=الأحد (يوافق datetime.weekday())
        """
        # عدد الأيام التي يجب الرجوع إليها للوصول إلى يوم البداية
        days_back = (date.weekday() - start_day) % 7
        return date - datetime.timedelta(days=days_back)

    @staticmethod
    def compute_week_number_and_year(date, start_day):
        """
        تحسب رقم الأسبوع والسنة المنطقية بناءً على تاريخ معيّن ويوم البداية.
        - الأسبوع #1 = الأسبوع الذي يحتوي أول يوم بداية في السنة
        - الأيام قبل أول يوم بداية من السنة تنتمي للسنة السابقة
        - الأيام بعد آخر يوم بداية من السنة الحالية قد تنتمي للسنة التالية

        ترجع: (logical_year, week_number, week_start_date, week_end_date)
        """
        week_start = PeriodAutoService.compute_week_start(date, start_day)

        # ابحث في أي سنة تقع أول يوم بداية من الأسبوع
        candidate_year = week_start.year
        jan_1 = datetime.date(candidate_year, 1, 1)
        days_to_first = (start_day - jan_1.weekday()) % 7
        first_week_start = jan_1 + datetime.timedelta(days=days_to_first)

        if week_start < first_week_start:
            # هذا الأسبوع بدأ في ديسمبر من السنة السابقة
            candidate_year -= 1
            jan_1 = datetime.date(candidate_year, 1, 1)
            days_to_first = (start_day - jan_1.weekday()) % 7
            first_week_start = jan_1 + datetime.timedelta(days=days_to_first)

        delta_days = (week_start - first_week_start).days
        week_number = (delta_days // 7) + 1
        week_end = week_start + datetime.timedelta(days=6)
        return candidate_year, week_number, week_start, week_end

    @staticmethod
    def compute_deadline(week_end_date, config):
        """
        تحسب الموعد النهائي من تاريخ نهاية الأسبوع وفقاً لإعدادات النظام.
        الموعد = نهاية الأسبوع + (deadline_days_after_week_end) + (deadline_hour)
        """
        deadline_date = week_end_date + datetime.timedelta(
            days=config.deadline_days_after_week_end
        )
        naive_dt = datetime.datetime.combine(
            deadline_date,
            datetime.time(hour=config.deadline_hour, minute=0),
        )
        return timezone.make_aware(naive_dt)

    # ──────────────────────────────────────────
    # دوال الإنشاء والإغلاق
    # ──────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def ensure_current_period(now=None):
        """
        النقطة الرئيسية للاستدعاء — يضمن وجود الأسبوع الحالي ويُغلق القديم إن لزم.
        - لا يفعل شيئاً إذا كان `auto_create_enabled = False`
        - يُنشئ الأسبوع الحالي إن لم يكن موجوداً (بناءً على الوقت الحالي)
        - يُغلق الأسبوع السابق إذا مرّ موعده النهائي وكانت `auto_close_previous = True`

        ترجع قاموساً يصف ما تم: {'created': ..., 'closed': [...]}
        """
        config = SystemConfiguration.load()
        if not config.auto_create_enabled:
            return {'created': None, 'closed': [], 'skipped': 'disabled'}

        if now is None:
            now = timezone.now()

        today = timezone.localdate(now) if timezone.is_aware(now) else now.date()
        start_day = config.week_start_day

        # احسب الأسبوع المنطقي لليوم الحالي
        year, week_number, week_start, week_end = (
            PeriodAutoService.compute_week_number_and_year(today, start_day)
        )

        created_period = None
        # هل الأسبوع موجود أصلاً؟
        existing = WeeklyPeriod.objects.select_for_update().filter(
            year=year, week_number=week_number
        ).first()

        if not existing:
            deadline = PeriodAutoService.compute_deadline(week_end, config)
            created_period = WeeklyPeriod.objects.create(
                year=year,
                week_number=week_number,
                start_date=week_start,
                end_date=week_end,
                deadline=deadline,
                status=WeeklyPeriod.Status.OPEN,
                created_by=None,  # إنشاء آلي
            )
            # إرسال إشعارات فتح الأسبوع
            try:
                _notify_period_opened(created_period)
            except Exception:
                import logging
                logging.getLogger(__name__).warning(
                    "فشل إرسال إشعار فتح الفترة التلقائية", exc_info=True
                )

        # إغلاق الأسابيع المنتهية إن كان ذلك مفعّلاً
        closed_ids = []
        if config.auto_close_previous:
            closed_ids = PeriodAutoService._auto_close_expired_periods(
                now=now, current_year=year, current_week=week_number
            )

        return {
            'created': created_period,
            'closed': closed_ids,
            'logical_period': {
                'year': year,
                'week_number': week_number,
                'start_date': week_start,
                'end_date': week_end,
            },
        }

    @staticmethod
    def _auto_close_expired_periods(now, current_year, current_week):
        """
        تُغلق الأسابيع المفتوحة التي مرّ موعدها النهائي (عدا الأسبوع الحالي).
        تتجنّب الإغلاق إذا وجدت تمديدات ساريّة — في هذه الحالة يُترك الأسبوع مفتوحاً.
        ترجع قائمة بمعرّفات الفترات التي أُغلقت.
        """
        expired_periods = WeeklyPeriod.objects.filter(
            status=WeeklyPeriod.Status.OPEN,
            deadline__lt=now,
        ).exclude(
            year=current_year, week_number=current_week,
        )

        closed_ids = []
        for period in expired_periods:
            try:
                WeeklyPeriodService.close_period(period, user=None)
                closed_ids.append(period.id)
            except ValidationError:
                # قد توجد تمديدات سارية — نتجاوز هذا الأسبوع ونُعيد المحاولة لاحقاً
                continue
            except Exception:
                import logging
                logging.getLogger(__name__).warning(
                    f"فشل الإغلاق التلقائي للفترة {period.id}", exc_info=True
                )
                continue
        return closed_ids


class SubmissionService:
    """خدمة إدارة المنجزات الأسبوعية"""

    @staticmethod
    @transaction.atomic
    def get_or_create_submission(qism, weekly_period, actor=None):
        """
        الحصول على أو إنشاء منجز لقسم وفترة محددة.
        في حالة الإنشاء، يتم البحث عن قالب الاستمارة النشط للقسم.
        `actor` اختياري: إن وُفِّر، يُسجَّل إنشاء المنجز في سجلّ التدقيق.
        """
        submission = WeeklySubmission.objects.filter(
            qism=qism, weekly_period=weekly_period
        ).first()

        if submission:
            return submission, False

        from apps.forms.services import FormTemplateService

        try:
            active_template = FormTemplateService.get_active_template(
                qism_id=qism.id,
                year=weekly_period.year,
                week_number=weekly_period.week_number,
            )
        except ValidationError:
            raise ValidationError(
                'لا يوجد قالب استمارة فعّال لهذا القسم في هذه الفترة'
            )

        submission = WeeklySubmission.objects.create(
            qism=qism,
            weekly_period=weekly_period,
            form_template=active_template,
            status=WeeklySubmission.Status.DRAFT,
        )

        # إنشاء إجابات فارغة لكل بنود القالب
        empty_answers = [
            SubmissionAnswer(submission=submission, form_item=item)
            for item in active_template.items.select_related('indicator').all()
        ]
        if empty_answers:
            SubmissionAnswer.objects.bulk_create(empty_answers)

        if actor is not None:
            AuditService.log_submission_action(
                action_type=AuditLog.ActionType.SUBMISSION_CREATED,
                actor=actor,
                submission=submission,
            )

        return submission, True

    @staticmethod
    @transaction.atomic
    def save_answers(submission, answers_data, notes=None, actor=None):
        """
        حفظ أو تحديث إجابات المنجز (وملاحظاته اختيارياً).
        يعمل فقط إذا كان المنجز قابلاً للتعديل.
        `actor` اختياري: إن وُفِّر، يُسجَّل الإجراء في سجلّ التدقيق.
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
        notes: نص اختياري لتحديث ملاحظات المنجز.
        """
        # قفل السجل لمنع التعارضات المتزامنة
        submission = WeeklySubmission.objects.select_for_update().get(pk=submission.pk)

        if not submission.is_editable():
            raise ValidationError(
                'لا يمكن تعديل هذا المنجز - الموعد النهائي قد انتهى أو الفترة مغلقة'
            )

        # تحديث الملاحظات إن وُفرت
        if notes is not None:
            submission.notes = notes
            submission.save(update_fields=['notes'])

        # تحقق مسبق من أن جميع البنود تنتمي لقالب المنجز (استعلام واحد)
        provided_item_ids = {a.get('form_item_id') for a in answers_data}
        valid_item_ids = set(
            submission.form_template.items.filter(
                id__in=provided_item_ids
            ).values_list('id', flat=True)
        )
        invalid = provided_item_ids - valid_item_ids
        if invalid:
            raise ValidationError(
                f'بنود الاستمارة التالية لا تنتمي لقالب هذا المنجز: {sorted(invalid)}'
            )

        saved_answers = []
        for answer_data in answers_data:
            form_item_id = answer_data.get('form_item_id')

            # تحديد حالة المنجز النوعي:
            # - غير نوعي → NONE
            # - نوعي وكان معتمداً سابقاً → نُبقيه معتمداً
            # - نوعي ولم يُعتمد → PENDING_PLANNING (يُحدّث عند submit أيضاً)
            is_qualitative = answer_data.get('is_qualitative', False)
            existing = SubmissionAnswer.objects.filter(
                submission=submission, form_item_id=form_item_id,
            ).first()

            if not is_qualitative:
                qualitative_status = SubmissionAnswer.QualitativeStatus.NONE
            elif existing and existing.qualitative_status == SubmissionAnswer.QualitativeStatus.APPROVED:
                qualitative_status = SubmissionAnswer.QualitativeStatus.APPROVED
            else:
                qualitative_status = SubmissionAnswer.QualitativeStatus.PENDING_PLANNING

            answer, _created = SubmissionAnswer.objects.update_or_create(
                submission=submission,
                form_item_id=form_item_id,
                defaults={
                    'numeric_value': answer_data.get('numeric_value'),
                    'text_value': answer_data.get('text_value', ''),
                    'is_qualitative': is_qualitative,
                    'qualitative_details': answer_data.get('qualitative_details', ''),
                    'qualitative_status': qualitative_status,
                },
            )
            answer.full_clean()
            answer.save()
            saved_answers.append(answer)

        # سجلّ التدقيق — سطر واحد لكل عملية save، بدون تفاصيل الحقول
        # (تفادي إغراق السجلّ بكلّ تعديل صغير قبل الإرسال).
        if actor is not None:
            AuditService.log_submission_action(
                action_type=AuditLog.ActionType.SUBMISSION_SAVED,
                actor=actor,
                submission=submission,
                metadata={'answers_count': len(saved_answers)},
            )

        return saved_answers

    @staticmethod
    @transaction.atomic
    def submit(submission, user):
        """
        إرسال المنجز (مسودة/مُمدَّد/مُرجَع → مُرسل).
        - التحقق من صلاحية مدير القسم على المنجز
        - التحقق من قابلية التعديل (الفترة مفتوحة + موعد ساري أو تمديد)
        - التحقق من أن جميع الحقول الإلزامية مُعبأة بقيم فعلية
        - تحديث تاريخ الإرسال
        - إرسال إشعار لقسم التخطيط
        """
        # التحقق من الصلاحية: مدير قسم لمنجز قسمه
        if user.role != 'section_manager' or submission.qism_id != user.unit_id:
            raise PermissionDenied(
                'ليس لديك صلاحية لإرسال هذا المنجز'
            )

        # قفل السجل لمنع التعارضات المتزامنة
        submission = WeeklySubmission.objects.select_for_update().get(pk=submission.pk)

        valid_statuses = (
            WeeklySubmission.Status.DRAFT,
            WeeklySubmission.Status.EXTENDED,
            WeeklySubmission.Status.RETURNED,
            # مسموح بإعادة الإرسال بعد إرجاع من الإحصاء — حتى لو انتهى الأسبوع
            WeeklySubmission.Status.RETURNED_BY_ADMIN,
        )
        if submission.status not in valid_statuses:
            raise ValidationError(
                'لا يمكن إرسال هذا المنجز - الحالة الحالية غير مسموح بها'
            )

        if not submission.is_editable():
            raise ValidationError(
                'لا يمكن إرسال هذا المنجز - الموعد النهائي قد انتهى أو الفترة مغلقة'
            )

        # التحقق من الحقول الإلزامية وقيمها الفعلية
        existing_answers = {
            ans.form_item_id: ans
            for ans in submission.answers.select_related('form_item__indicator').all()
        }
        mandatory_items = submission.form_template.items.select_related(
            'indicator'
        ).filter(is_mandatory=True)

        missing_items = []
        for item in mandatory_items:
            answer = existing_answers.get(item.id)
            if not answer or not _has_actual_value(answer, item.indicator):
                missing_items.append(item.indicator.name)

        if missing_items:
            raise ValidationError({
                'missing_items': missing_items,
                'message': 'يجب ملء جميع الحقول الإلزامية قبل الإرسال',
            })

        # التحقق من تفاصيل المنجزات النوعية
        for answer in existing_answers.values():
            if answer.is_qualitative and not answer.qualitative_details.strip():
                raise ValidationError(
                    'يجب إدخال تفاصيل جميع المنجزات النوعية قبل الإرسال'
                )

        previous_status = submission.status
        submission.status = WeeklySubmission.Status.SUBMITTED
        submission.submitted_at = timezone.now()
        submission.save(update_fields=['status', 'submitted_at'])

        # نقل الإجابات النوعية إلى المرحلة الأولى من الاعتماد
        SubmissionAnswer.objects.filter(
            submission=submission,
            is_qualitative=True,
        ).exclude(
            qualitative_status=SubmissionAnswer.QualitativeStatus.APPROVED,
        ).update(
            qualitative_status=SubmissionAnswer.QualitativeStatus.PENDING_PLANNING
        )

        AuditService.log_submission_action(
            action_type=AuditLog.ActionType.SUBMISSION_SUBMITTED,
            actor=user,
            submission=submission,
            metadata={'previous_status': previous_status},
        )

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
        اعتماد المنجز بواسطة قسم التخطيط.
        حالات الدخول المقبولة:
        - مُرسل (SUBMITTED) → اعتماد أوّل
        - مُرجَع من الإحصاء (RETURNED_BY_ADMIN) → إعادة اعتماد بعد تصحيح
        الانتقال: → معتمد (APPROVED)

        - التحقق من صلاحية المستخدم ونطاقه
        - تحديث بيانات الاعتماد
        - إعادة تصفير حقول مراجعة الإحصاء (لأن الإحصاء يجب أن تُعيد المراجعة
          بعد أي تعديل لاحق للاعتماد الأوّل)
        - نقل المنجزات النوعية من pending_planning إلى pending_statistics
        - إرسال إشعار
        """
        SubmissionService._assert_planning_scope(user, submission)

        # قفل السجل لمنع التعارضات المتزامنة
        submission = WeeklySubmission.objects.select_for_update().get(pk=submission.pk)

        allowed_statuses = (
            WeeklySubmission.Status.SUBMITTED,
            WeeklySubmission.Status.RETURNED_BY_ADMIN,
        )
        if submission.status not in allowed_statuses:
            raise ValidationError(
                'لا يمكن اعتماد هذا المنجز - يجب أن يكون بحالة "مُرسل" '
                'أو "مُرجَع من الإحصاء"'
            )

        previous_status = submission.status
        submission.status = WeeklySubmission.Status.APPROVED
        submission.planning_approved_by = user
        submission.planning_approved_at = timezone.now()
        # إعادة تصفير حقول مراجعة الإحصاء — المحتوى قد يكون تغيّر، فيجب
        # أن تراجعه الإحصاء من جديد كأنه منجز جديد.
        submission.admin_reviewed_at = None
        submission.admin_reviewed_by = None
        submission.admin_review_action = ''
        submission.save(update_fields=[
            'status', 'planning_approved_by', 'planning_approved_at',
            'admin_reviewed_at', 'admin_reviewed_by', 'admin_review_action',
        ])

        AuditService.log_submission_action(
            action_type=AuditLog.ActionType.SUBMISSION_PLANNING_APPROVED,
            actor=user,
            submission=submission,
            metadata={'previous_status': previous_status},
        )

        # نقل المنجزات النوعية إلى المرحلة التالية
        qualitative_answers = submission.answers.filter(
            is_qualitative=True,
            qualitative_status=SubmissionAnswer.QualitativeStatus.PENDING_PLANNING,
        )
        has_pending_qualitative = qualitative_answers.exists()
        qualitative_answers.update(
            qualitative_status=SubmissionAnswer.QualitativeStatus.PENDING_STATISTICS
        )

        # إرسال إشعار اعتماد المنجز
        try:
            _notify_submission_approved(submission)
        except Exception:
            import logging
            logging.getLogger(__name__).warning("فشل إرسال إشعار اعتماد المنجز", exc_info=True)

        # إرسال إشعار للمنجزات النوعية المعلقة (لمدير قسم الإحصاء)
        if has_pending_qualitative:
            try:
                _notify_qualitative_pending(submission)
            except Exception:
                import logging
                logging.getLogger(__name__).warning("فشل إرسال إشعار المنجزات النوعية", exc_info=True)

        return submission

    @staticmethod
    @transaction.atomic
    def reject_by_planning(submission, user, reason):
        """
        رفض المنجز من قسم التخطيط (مُرسل → مُرجَع للتصحيح).
        - يعيد المنجز إلى حالة قابلة للتعديل من قبل مدير القسم
        - يُلغي اعتمادات الإجابات النوعية في المرحلة الأولى
        - يُرسل إشعاراً لمدير القسم بسبب الرفض
        """
        SubmissionService._assert_planning_scope(user, submission)

        if not reason or not reason.strip():
            raise ValidationError({
                'reason': 'يجب تحديد سبب الرفض'
            })

        # قفل السجل
        submission = WeeklySubmission.objects.select_for_update().get(pk=submission.pk)

        allowed_statuses = (
            WeeklySubmission.Status.SUBMITTED,
            WeeklySubmission.Status.RETURNED_BY_ADMIN,
        )
        if submission.status not in allowed_statuses:
            raise ValidationError(
                'لا يمكن رفض هذا المنجز - يجب أن يكون بحالة "مُرسل" '
                'أو "مُرجَع من الإحصاء"'
            )

        previous_status = submission.status
        submission.status = WeeklySubmission.Status.RETURNED
        # إلحاق سبب الرفض بالملاحظات لتسهيل عرضه لمدير القسم
        rejection_note = f'[سبب الإرجاع — {timezone.now().strftime("%Y-%m-%d %H:%M")}] {reason.strip()}'
        if submission.notes:
            submission.notes = f'{submission.notes}\n{rejection_note}'
        else:
            submission.notes = rejection_note
        # إذا كان المنجز قد مرّ سابقاً بمراجعة الإحصاء وتُرجَع الآن،
        # نُعيد تصفير حقول المراجعة — سيمرّ مرة أخرى بسلسلة كاملة.
        submission.admin_reviewed_at = None
        submission.admin_reviewed_by = None
        submission.admin_review_action = ''
        submission.save(update_fields=[
            'status', 'notes',
            'admin_reviewed_at', 'admin_reviewed_by', 'admin_review_action',
        ])

        AuditService.log_submission_action(
            action_type=AuditLog.ActionType.SUBMISSION_PLANNING_RETURNED,
            actor=user,
            submission=submission,
            reason=reason.strip(),
            metadata={'previous_status': previous_status},
        )

        # إعادة الإجابات النوعية إلى مسودة لإتاحة تعديلها
        SubmissionAnswer.objects.filter(
            submission=submission,
            is_qualitative=True,
            qualitative_status=SubmissionAnswer.QualitativeStatus.PENDING_PLANNING,
        ).update(
            qualitative_status=SubmissionAnswer.QualitativeStatus.NONE,
        )

        try:
            _notify_submission_returned(submission, reason.strip())
        except Exception:
            import logging
            logging.getLogger(__name__).warning("فشل إرسال إشعار إرجاع المنجز", exc_info=True)

        return submission

    @staticmethod
    def _assert_planning_scope(user, submission):
        """يتحقق أن المستخدم في دور قسم التخطيط ومنجز ضمن نطاقه"""
        if user.role != 'planning_section':
            raise PermissionDenied('فقط قسم التخطيط يمكنه اعتماد أو رفض المنجزات')

        scope_qism_ids = _planning_section_scope_qism_ids(user)
        if scope_qism_ids is None:
            return  # نطاق مركزي = جميع الأقسام
        if submission.qism_id not in scope_qism_ids:
            raise PermissionDenied('ليس لديك صلاحية على منجز هذا القسم')


class SubmissionAdminService:
    """
    خدمة مراجعة المنجزات من قبل قسم الإحصاء (الطبقة الثالثة).

    الدور العام:
    - موظف قسم الإحصاء يرى المنجزات بعد اعتماد التخطيط.
    - يستطيع **مرّة واحدة فقط** أن يقوم بواحدة من ثلاث إجراءات:
        (١) اعتماد بدون تعديل
        (٢) تعديل حقول مع سبب إلزامي
        (٣) إرجاع للتخطيط مع سبب إلزامي
    - بمجرّد أن يتصرّف أي موظف من الإحصاء، يُقفَل المنجز من الآخرين.
    - الإحصائيّات المعتمَدة على المنجز لا تتأثّر في (١) و (٢)؛ في (٣)
      تنتقل الحالة إلى `returned_by_admin` فيُستبعَد من التقارير حتى
      يعيده التخطيط إلى `approved`.

    كل الإجراءات تُسجَّل في AuditLog.
    """

    @staticmethod
    def _assert_admin(user):
        if not user or getattr(user, 'role', None) != 'statistics_admin':
            raise PermissionDenied(
                'فقط مدير قسم الإحصاء يستطيع مراجعة المنجزات'
            )

    @staticmethod
    def _assert_reviewable(submission):
        """
        يتحقّق من أن المنجز:
        - معتمد من التخطيط (في حالة approved)
        - لم يراجعه أي موظف إحصاء بعد (admin_reviewed_at IS NULL)
        """
        if submission.status != WeeklySubmission.Status.APPROVED:
            raise ValidationError(
                'يمكن مراجعة المنجزات المعتمدة من قسم التخطيط فقط'
            )
        if submission.admin_reviewed_at is not None:
            reviewer_name = (
                submission.admin_reviewed_by.full_name
                if submission.admin_reviewed_by else 'موظف آخر'
            )
            raise ValidationError(
                f'تمّت مراجعة هذا المنجز من قِبَل {reviewer_name} '
                f'في {submission.admin_reviewed_at:%Y-%m-%d %H:%M}. '
                f'لا يمكن مراجعته مرّة أخرى.'
            )

    @staticmethod
    @transaction.atomic
    def approve(submission, user):
        """
        اعتماد المنجز من الإحصاء بدون تعديل (لا يتطلّب سبباً).
        لا يُغيِّر حالة المنجز — يبقى `approved` — لكنه يُقفله من مراجعة أخرى.
        """
        from apps.audit.services import AuditService
        from apps.audit.models import AuditLog

        SubmissionAdminService._assert_admin(user)

        # قفل السجل
        submission = WeeklySubmission.objects.select_for_update().get(pk=submission.pk)
        SubmissionAdminService._assert_reviewable(submission)

        submission.admin_reviewed_at = timezone.now()
        submission.admin_reviewed_by = user
        submission.admin_review_action = 'approved'
        submission.save(update_fields=[
            'admin_reviewed_at', 'admin_reviewed_by', 'admin_review_action',
        ])

        AuditService.log_submission_action(
            action_type=AuditLog.ActionType.SUBMISSION_ADMIN_APPROVED,
            actor=user,
            submission=submission,
        )
        return submission

    @staticmethod
    @transaction.atomic
    def edit(submission, user, answer_edits, reason):
        """
        تعديل إجابات المنجز من قبل الإحصاء مع سبب إلزامي.

        `answer_edits` قائمة من dicts بالشكل:
            [{"answer_id": 42, "numeric_value": 150}, ...]
            أو {"answer_id": 42, "text_value": "...", "reason": "اختياري"}

        تُسجَّل التغييرات في AuditLog مع القيم القديمة والجديدة.
        """
        from apps.audit.services import AuditService
        from apps.audit.models import AuditLog

        SubmissionAdminService._assert_admin(user)

        if not reason or not reason.strip():
            raise ValidationError({'reason': 'يجب تحديد سبب التعديل'})

        if not answer_edits:
            raise ValidationError({'answer_edits': 'لا توجد تعديلات مُرسَلة'})

        # قفل المنجز
        submission = WeeklySubmission.objects.select_for_update().get(pk=submission.pk)
        SubmissionAdminService._assert_reviewable(submission)

        field_changes = []
        # قفل الإجابات المُعدَّلة + جمع فروقات القيم
        answer_ids = [edit.get('answer_id') for edit in answer_edits if edit.get('answer_id')]
        answers_map = {
            a.pk: a
            for a in SubmissionAnswer.objects.select_for_update()
            .filter(pk__in=answer_ids, submission=submission)
            .select_related('form_item__indicator')
        }

        for edit in answer_edits:
            answer_id = edit.get('answer_id')
            answer = answers_map.get(answer_id)
            if answer is None:
                raise ValidationError(
                    {'answer_edits': f'الإجابة {answer_id} غير موجودة في هذا المنجز'}
                )

            changed = False
            if 'numeric_value' in edit:
                from decimal import Decimal, InvalidOperation

                raw_new = edit['numeric_value']
                old_value = answer.numeric_value

                # تطبيع القيم للمقارنة — نستخدم Decimal للقيم الرقمية
                # لتفادي اختلافات التمثيل (100 vs 100.0 vs 100.00).
                def _to_decimal(v):
                    if v is None:
                        return None
                    try:
                        return Decimal(str(v))
                    except (InvalidOperation, ValueError):
                        return None

                new_decimal = _to_decimal(raw_new)
                old_decimal = _to_decimal(old_value)

                if new_decimal != old_decimal:
                    field_changes.append({
                        'field': 'numeric_value',
                        'answer_id': answer.pk,
                        'indicator_id': answer.form_item.indicator_id,
                        'indicator_name': answer.form_item.indicator.name,
                        'old': str(old_decimal) if old_decimal is not None else None,
                        'new': str(new_decimal) if new_decimal is not None else None,
                    })
                    answer.numeric_value = new_decimal
                    changed = True

            if 'text_value' in edit:
                new_text = edit['text_value'] or ''
                old_text = answer.text_value or ''
                if old_text != new_text:
                    field_changes.append({
                        'field': 'text_value',
                        'answer_id': answer.pk,
                        'indicator_id': answer.form_item.indicator_id,
                        'indicator_name': answer.form_item.indicator.name,
                        'old': old_text,
                        'new': new_text,
                    })
                    answer.text_value = new_text
                    changed = True

            if changed:
                answer.save(update_fields=['numeric_value', 'text_value'])

        if not field_changes:
            raise ValidationError(
                'لم يتم تعديل أي حقل فعلياً — القيم الجديدة مطابقة للقيم الحالية'
            )

        submission.admin_reviewed_at = timezone.now()
        submission.admin_reviewed_by = user
        submission.admin_review_action = 'edited'
        submission.save(update_fields=[
            'admin_reviewed_at', 'admin_reviewed_by', 'admin_review_action',
        ])

        AuditService.log_submission_action(
            action_type=AuditLog.ActionType.SUBMISSION_ADMIN_EDITED,
            actor=user,
            submission=submission,
            field_changes=field_changes,
            reason=reason.strip(),
        )
        return submission

    @staticmethod
    @transaction.atomic
    def return_to_planning(submission, user, reason):
        """
        إرجاع المنجز من الإحصاء إلى قسم التخطيط مع سبب إلزامي.
        - الحالة تنتقل إلى `returned_by_admin`
        - يُستبعَد من الإحصائيّات (لأن الاستعلامات تفلتر status='approved')
        - قسم التخطيط يرى المنجز في قائمته ويُقرّر: تعديل وإعادة اعتماد،
          أو إعادة للقسم لتصحيحه (returned).
        - قابل للتعديل دائماً بعد ذلك حتى لو انتهى الأسبوع (is_editable).
        """
        from apps.audit.services import AuditService
        from apps.audit.models import AuditLog

        SubmissionAdminService._assert_admin(user)

        if not reason or not reason.strip():
            raise ValidationError({'reason': 'يجب تحديد سبب الإرجاع'})

        submission = WeeklySubmission.objects.select_for_update().get(pk=submission.pk)
        SubmissionAdminService._assert_reviewable(submission)

        submission.status = WeeklySubmission.Status.RETURNED_BY_ADMIN
        submission.admin_reviewed_at = timezone.now()
        submission.admin_reviewed_by = user
        submission.admin_review_action = 'returned'
        # إلحاق سبب الإرجاع بالملاحظات لسهولة عرضه للتخطيط
        return_note = (
            f'[إرجاع من الإحصاء — {timezone.now():%Y-%m-%d %H:%M}] '
            f'{reason.strip()}'
        )
        submission.notes = (
            f'{submission.notes}\n{return_note}' if submission.notes else return_note
        )
        submission.save(update_fields=[
            'status', 'admin_reviewed_at', 'admin_reviewed_by',
            'admin_review_action', 'notes',
        ])

        AuditService.log_submission_action(
            action_type=AuditLog.ActionType.SUBMISSION_ADMIN_RETURNED,
            actor=user,
            submission=submission,
            reason=reason.strip(),
            metadata={'new_status': WeeklySubmission.Status.RETURNED_BY_ADMIN},
        )
        return submission


class QismExtensionService:
    """خدمة إدارة تمديدات المواعيد"""

    @staticmethod
    @transaction.atomic
    def grant_extension(data, granted_by):
        """
        منح تمديد لقسم معين.
        - فقط مدير قسم الإحصاء يستطيع منح التمديدات (قاعدة CLAUDE.md #9)
        - التحقق من أن الموعد الجديد بعد الموعد الأصلي
        - تحديث حالة المنجز إلى 'مُمدَّد' إن وجد
        - إرسال إشعار
        """
        # فحص الدور في طبقة الخدمة — دفاع مستقل عن طبقة الـ view
        if not granted_by or getattr(granted_by, 'role', None) != 'statistics_admin':
            raise PermissionDenied(
                'فقط مدير قسم الإحصاء يستطيع منح تمديدات المواعيد'
            )

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

        AuditService.log(
            action_type=AuditLog.ActionType.EXTENSION_GRANTED,
            actor=granted_by,
            target=extension,
            qism=qism,
            reason=data.get('reason', ''),
            metadata={
                'weekly_period_id': weekly_period.id,
                'new_deadline': new_deadline.isoformat(),
            },
        )

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

        AuditService.log(
            action_type=AuditLog.ActionType.QUALITATIVE_ADMIN_APPROVED,
            actor=user,
            target=answer,
            qism=getattr(answer.submission, 'qism', None),
            metadata={'submission_id': answer.submission_id},
        )

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

        AuditService.log(
            action_type=AuditLog.ActionType.QUALITATIVE_ADMIN_REJECTED,
            actor=user,
            target=answer,
            qism=getattr(answer.submission, 'qism', None),
            reason=reason,
            metadata={'submission_id': answer.submission_id},
        )

        # إرسال إشعار
        try:
            _notify_qualitative_rejected(answer)
        except Exception:
            import logging
            logging.getLogger(__name__).warning("فشل إرسال إشعار رفض النوعي", exc_info=True)

        return answer


# ========================================
# دوال مساعدة للنطاقات والقيم
# ========================================


def _has_actual_value(answer, indicator):
    """يتحقق من وجود قيمة فعلية في الإجابة بحسب نوع المؤشر"""
    if indicator.is_numeric:
        return answer.numeric_value is not None
    return bool(answer.text_value and answer.text_value.strip())


def _planning_section_scope_qism_ids(user):
    """
    يُرجع مجموعة معرّفات الأقسام التي يشرف عليها مستخدم قسم التخطيط.
    - إذا كان قسم التخطيط له أب (تابع لمديرية/دائرة): الأقسام التابعة لذلك الأب فقط.
    - إذا كان قسم التخطيط بدون أب (مركزي): يُرجع None للإشارة إلى نطاق مفتوح (كل الأقسام).
    """
    if not user.unit:
        return set()

    parent_id = user.unit.parent_id
    if parent_id is None:
        # قسم تخطيط مركزي — صلاحية على كل الأقسام
        return None

    # استعلام مباشر بالـ id يضمن قراءة قيم MPTT المحدّثة من قاعدة البيانات
    # (تجنّب MPTT cache staleness عند إنشاء عناصر الشجرة في وقت التشغيل)
    parent = OrganizationUnit.objects.get(pk=parent_id)
    descendant_ids = set(
        parent.get_descendants(include_self=False)
        .filter(unit_type=UnitType.QISM, qism_role='regular', is_active=True)
        .values_list('id', flat=True)
    )
    return descendant_ids


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


def _notify_submission_returned(submission, reason):
    """إرسال إشعار رفض/إرجاع المنجز لمدير القسم"""
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
            notification_type='submission_returned',
            title='إرجاع المنجز للتصحيح',
            message=(
                f'تم إرجاع منجز {submission.qism.name} لـ {submission.weekly_period} من قسم التخطيط. '
                f'السبب: {reason}'
            ),
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
