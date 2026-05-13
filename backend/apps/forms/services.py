from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max, Q
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.audit.services import AuditService

from .models import FormTemplate, FormTemplateItem


class FormTemplateService:
    """خدمة إدارة قوالب الاستمارات"""

    @staticmethod
    @transaction.atomic
    def create_template(data, items_data, created_by):
        """
        إنشاء قالب استمارة جديد مع بنوده.
        يتم حساب رقم الإصدار تلقائياً (أقصى إصدار للقسم + 1).
        - مدير قسم الإحصاء: يستطيع إنشاء قوالب لأي قسم
        - قسم التخطيط: يستطيع إنشاء قوالب لأقسام مديريته فقط
        """
        qism = data.get('qism')

        # التحقق من أن القسم هو قسم عادي
        if qism.unit_type != 'qism' or qism.qism_role != 'regular':
            raise ValidationError({
                'qism': 'يجب أن تكون الاستمارة مرتبطة بقسم عادي فقط'
            })

        # التحقق من أن المنشئ (إن كان قسم تخطيط) ينطبق نطاقه على القسم المستهدف.
        # نستخدم نفس منطق تحديد النطاق الموحّد (يدعم هرمية MPTT):
        # - مخطط مديرية: يرى أقسام مديريته مباشرة
        # - مخطط دائرة: يرى كل الأقسام تحت دائرته (عبر المديريات المتوسطة)
        # - مخطط مركزي (بدون أب): نطاقه كامل
        if created_by.role == 'planning_section' and created_by.unit:
            from apps.submissions.services import (
                _planning_section_scope_qism_ids,
            )
            scope_ids = _planning_section_scope_qism_ids(created_by)
            if scope_ids is not None and qism.id not in scope_ids:
                raise ValidationError({
                    'qism': 'لا يمكنك إنشاء استمارة لقسم خارج نطاق مديريتك أو دائرتك'
                })

        # التحقق من وجود بنود
        if not items_data:
            raise ValidationError({
                'items': 'يجب أن تحتوي الاستمارة على بند واحد على الأقل'
            })

        # حساب رقم الإصدار الجديد مع قفل لمنع التعارضات المتزامنة
        max_version = FormTemplate.objects.select_for_update().filter(
            qism=qism
        ).aggregate(max_version=Max('version'))['max_version']
        new_version = (max_version or 0) + 1

        # إنشاء القالب
        template = FormTemplate(
            qism=qism,
            version=new_version,
            status=FormTemplate.Status.DRAFT,
            notes=data.get('notes', ''),
            created_by=created_by,
        )
        template.full_clean()
        try:
            template.save()
        except IntegrityError as e:
            # طبقة حماية في حال فشل الـ select_for_update (مثلاً بسبب
            # transaction isolation level منخفض): نُحوِّل التصادم إلى
            # رسالة خطأ عربية واضحة بدل 500.
            raise ValidationError({
                'version': (
                    'تعارض في ترقيم الإصدار بسبب عملية متزامنة. '
                    'يرجى المحاولة مرة أخرى.'
                )
            }) from e

        # إنشاء البنود
        FormTemplateService._create_items(template, items_data)

        AuditService.log(
            action_type=AuditLog.ActionType.TEMPLATE_CREATED,
            actor=created_by,
            target=template,
            qism=qism,
            metadata={
                'version': new_version,
                'items_count': len(items_data),
            },
        )

        return template

    @staticmethod
    @transaction.atomic
    def update_template(template, data, items_data, actor=None):
        """
        تحديث قالب استمارة. مسموح فقط في حالة المسودة.
        """
        if template.status != FormTemplate.Status.DRAFT:
            raise ValidationError(
                'لا يمكن تعديل الاستمارة إلا في حالة المسودة'
            )

        # تحديث بيانات القالب
        if 'notes' in data:
            template.notes = data['notes']

        template.full_clean()
        template.save()

        # تحديث البنود إذا تم توفيرها
        if items_data is not None:
            if not items_data:
                raise ValidationError({
                    'items': 'يجب أن تحتوي الاستمارة على بند واحد على الأقل'
                })
            # حذف البنود القديمة وإنشاء الجديدة
            template.items.all().delete()
            FormTemplateService._create_items(template, items_data)

        if actor is not None:
            AuditService.log(
                action_type=AuditLog.ActionType.TEMPLATE_UPDATED,
                actor=actor,
                target=template,
                qism=template.qism,
            )

        return template

    @staticmethod
    def submit_for_approval(template, actor=None):
        """
        تقديم القالب للاعتماد: مسودة ← بانتظار الاعتماد
        """
        if template.status != FormTemplate.Status.DRAFT:
            raise ValidationError(
                'لا يمكن تقديم الاستمارة للاعتماد إلا إذا كانت في حالة المسودة'
            )

        # التحقق من وجود بنود
        if not template.items.exists():
            raise ValidationError(
                'لا يمكن تقديم استمارة فارغة للاعتماد. يجب إضافة بنود أولاً'
            )

        template.status = FormTemplate.Status.PENDING_APPROVAL
        template.save(update_fields=['status'])

        if actor is not None:
            AuditService.log(
                action_type=AuditLog.ActionType.TEMPLATE_SUBMITTED,
                actor=actor,
                target=template,
                qism=template.qism,
            )

        return template

    @staticmethod
    @transaction.atomic
    def approve_template(template, approved_by, effective_from_week, effective_from_year):
        """
        اعتماد القالب: بانتظار الاعتماد ← معتمد.
        - يُرفض الاعتماد إذا كان تاريخ التفعيل في الماضي (قبل الأسبوع الحالي).
        - يُستبدَل (SUPERSEDED) أي قالب آخر معتمد لنفس القسم يبدأ في نفس الأسبوع
          أو بعده (أي يحلّ محلّ الخطط المستقبلية ونسخ نفس الأسبوع).
        - القالب الفعّال حالياً الذي بدأ قبل التاريخ الجديد يبقى APPROVED حتى يحلّ
          أسبوع التفعيل الجديد — عندها يلتقطه `get_active_template` تلقائياً.
        """
        # قفل السجل لمنع التعارضات المتزامنة
        template = FormTemplate.objects.select_for_update().get(pk=template.pk)

        if template.status != FormTemplate.Status.PENDING_APPROVAL:
            raise ValidationError(
                'يجب أن تكون الاستمارة بحالة \'بانتظار الاعتماد\''
            )

        # التحقق من صحة الأسبوع والسنة
        if not effective_from_week or not effective_from_year:
            raise ValidationError({
                'effective_from_week': 'يجب تحديد الأسبوع الذي يسري منه القالب',
                'effective_from_year': 'يجب تحديد السنة التي يسري منها القالب',
            })

        if effective_from_week < 1 or effective_from_week > 53:
            raise ValidationError({
                'effective_from_week': 'رقم الأسبوع يجب أن يكون بين 1 و 53'
            })

        # منع الاعتماد بأثر رجعي — قاعدة PRD: القالب يسري من effective_from_week فقط
        # ولا يُطبَّق على أسابيع ماضية (حماية سجل المنجزات التاريخي).
        from apps.submissions.services import PeriodAutoService
        from apps.submissions.models import SystemConfiguration
        config = SystemConfiguration.load()
        today = timezone.localdate()
        current_year, current_week, _, _ = (
            PeriodAutoService.compute_week_number_and_year(
                today, config.week_start_day
            )
        )
        if (effective_from_year, effective_from_week) < (current_year, current_week):
            raise ValidationError({
                'effective_from_week': (
                    f'لا يمكن اعتماد قالب بتاريخ تفعيل ماضٍ. '
                    f'الأسبوع الحالي هو {current_week}/{current_year}'
                )
            })

        # استبدال القوالب المعتمدة التي تبدأ في نفس الأسبوع أو بعده فقط.
        # القالب الفعّال حالياً (effective_from < التاريخ الجديد) يبقى APPROVED
        # ويغطّي الأسابيع حتى يحلّ أسبوع التفعيل الجديد.
        FormTemplate.objects.select_for_update().filter(
            qism=template.qism,
            status=FormTemplate.Status.APPROVED,
        ).filter(
            Q(effective_from_year__gt=effective_from_year)
            | Q(
                effective_from_year=effective_from_year,
                effective_from_week__gte=effective_from_week,
            )
        ).exclude(pk=template.pk).update(status=FormTemplate.Status.SUPERSEDED)

        # اعتماد القالب الحالي
        template.status = FormTemplate.Status.APPROVED
        template.approved_by = approved_by
        template.approved_at = timezone.now()
        template.effective_from_week = effective_from_week
        template.effective_from_year = effective_from_year
        template.save(update_fields=[
            'status', 'approved_by', 'approved_at',
            'effective_from_week', 'effective_from_year',
        ])

        AuditService.log(
            action_type=AuditLog.ActionType.TEMPLATE_APPROVED,
            actor=approved_by,
            target=template,
            qism=template.qism,
            metadata={
                'effective_from_week': effective_from_week,
                'effective_from_year': effective_from_year,
                'version': template.version,
            },
        )

        return template

    @staticmethod
    def reject_template(template, rejected_by, reason):
        """
        رفض القالب: بانتظار الاعتماد ← مرفوض
        """
        if template.status != FormTemplate.Status.PENDING_APPROVAL:
            raise ValidationError(
                'لا يمكن رفض الاستمارة إلا إذا كانت بانتظار الاعتماد'
            )

        if not reason or not reason.strip():
            raise ValidationError({
                'rejection_reason': 'يجب تحديد سبب الرفض'
            })

        template.status = FormTemplate.Status.REJECTED
        template.rejected_by = rejected_by
        template.rejection_reason = reason.strip()
        template.save(update_fields=[
            'status', 'rejected_by', 'rejection_reason',
        ])

        AuditService.log(
            action_type=AuditLog.ActionType.TEMPLATE_REJECTED,
            actor=rejected_by,
            target=template,
            qism=template.qism,
            reason=reason.strip(),
        )

        return template

    @staticmethod
    @transaction.atomic
    def create_new_version(source_template, created_by):
        """
        إنشاء إصدار جديد (مسودة) بناءً على قالب موجود.
        - يُستخدم لتعديل قالب معتمد دون كسر الربط التاريخي للمنجزات السابقة.
        - الإصدار الجديد ينسخ كل البنود من الإصدار المصدر مع رقم إصدار جديد.
        - يبقى المصدر معتمداً حتى يُعتمد الإصدار الجديد رسمياً.
        """
        # التحقق من نطاق الصلاحية لقسم التخطيط (يدعم مخطط مديرية ومخطط دائرة)
        if created_by.role == 'planning_section' and created_by.unit:
            from apps.submissions.services import (
                _planning_section_scope_qism_ids,
            )
            scope_ids = _planning_section_scope_qism_ids(created_by)
            if (
                scope_ids is not None
                and source_template.qism_id not in scope_ids
            ):
                raise ValidationError({
                    'qism': 'لا يمكنك إنشاء إصدار جديد لقسم خارج نطاق مديريتك أو دائرتك'
                })

        # إنشاء الإصدار الجديد عبر create_template (الذي يحسب رقم الإصدار تلقائياً)
        items_data = [
            {
                'indicator': item.indicator,
                'is_mandatory': item.is_mandatory,
                'display_order': item.display_order,
            }
            for item in source_template.items.select_related('indicator').all()
        ]

        new_template = FormTemplateService.create_template(
            data={
                'qism': source_template.qism,
                'notes': f'إصدار جديد بناءً على الإصدار {source_template.version}',
            },
            items_data=items_data,
            created_by=created_by,
        )

        AuditService.log(
            action_type=AuditLog.ActionType.TEMPLATE_NEW_VERSION,
            actor=created_by,
            target=new_template,
            qism=new_template.qism,
            metadata={
                'source_version': source_template.version,
                'new_version': new_template.version,
            },
        )

        return new_template

    @staticmethod
    def get_active_template(qism_id, year=None, week_number=None):
        """
        الحصول على القالب النشط لقسم معين في أسبوع محدد.
        - إذا لم يُحدَّد year/week يُحسب الأسبوع الحالي المنطقي تلقائياً.
        - يُعيد القالب الذي `effective_from` له أكبر ولكنه ≤ الأسبوع المطلوب
          (أي القالب الأحدث الذي سرى مفعوله فعلاً حتى ذلك الأسبوع).
        - لا يُعيد قوالب مُجدوَلة لأسبوع مستقبلي لم يحن بعد.
        """
        # إذا لم يُحدَّد year/week، استخدم الأسبوع الحالي المنطقي
        if year is None or week_number is None:
            from apps.submissions.services import PeriodAutoService
            from apps.submissions.models import SystemConfiguration
            config = SystemConfiguration.load()
            today = timezone.localdate()
            year, week_number, _, _ = (
                PeriodAutoService.compute_week_number_and_year(
                    today, config.week_start_day
                )
            )

        qs = FormTemplate.objects.filter(
            qism_id=qism_id,
            status=FormTemplate.Status.APPROVED,
            effective_from_week__isnull=False,
            effective_from_year__isnull=False,
        ).filter(
            Q(effective_from_year__lt=year)
            | Q(
                effective_from_year=year,
                effective_from_week__lte=week_number,
            )
        )

        # tie-breaker: -version كحسم أخير عند تعادل effective_from (نظرياً لا يحدث
        # بفضل قيد UniqueConstraint، لكنه حماية دفاعية).
        template = qs.order_by(
            '-effective_from_year', '-effective_from_week', '-version'
        ).first()

        if not template:
            raise ValidationError(
                'لا يوجد قالب استمارة نشط لهذا القسم'
            )

        return template

    @staticmethod
    def _create_items(template, items_data):
        """إنشاء بنود القالب"""
        seen_indicators = set()
        items_to_create = []

        for item_data in items_data:
            indicator = item_data.get('indicator')
            indicator_id = indicator.pk if hasattr(indicator, 'pk') else indicator

            # التحقق من عدم تكرار المؤشر
            if indicator_id in seen_indicators:
                raise ValidationError({
                    'items': f'المؤشر مكرر في الاستمارة'
                })
            seen_indicators.add(indicator_id)

            items_to_create.append(
                FormTemplateItem(
                    form_template=template,
                    indicator_id=indicator_id,
                    is_mandatory=item_data.get('is_mandatory', False),
                    display_order=item_data.get('display_order', 0),
                )
            )

        FormTemplateItem.objects.bulk_create(items_to_create)
