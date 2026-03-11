from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from .models import FormTemplate, FormTemplateItem


class FormTemplateService:
    """خدمة إدارة قوالب الاستمارات"""

    @staticmethod
    @transaction.atomic
    def create_template(data, items_data, created_by):
        """
        إنشاء قالب استمارة جديد مع بنوده.
        يتم حساب رقم الإصدار تلقائياً (أقصى إصدار للقسم + 1).
        """
        qism = data.get('qism')

        # التحقق من أن القسم هو قسم عادي
        if qism.unit_type != 'qism' or qism.qism_role != 'regular':
            raise ValidationError({
                'qism': 'يجب أن تكون الاستمارة مرتبطة بقسم عادي فقط'
            })

        # التحقق من أن المنشئ ينتمي لنفس المديرية/الدائرة
        if created_by.role == 'planning_section' and created_by.unit:
            planning_parent = created_by.unit.parent
            qism_parent = qism.parent
            if planning_parent != qism_parent:
                raise ValidationError({
                    'qism': 'لا يمكنك إنشاء استمارة لقسم خارج نطاق مديريتك'
                })

        # التحقق من وجود بنود
        if not items_data:
            raise ValidationError({
                'items': 'يجب أن تحتوي الاستمارة على بند واحد على الأقل'
            })

        # حساب رقم الإصدار الجديد
        max_version = FormTemplate.objects.filter(
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
        template.save()

        # إنشاء البنود
        FormTemplateService._create_items(template, items_data)

        return template

    @staticmethod
    @transaction.atomic
    def update_template(template, data, items_data):
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

        return template

    @staticmethod
    def submit_for_approval(template):
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
        return template

    @staticmethod
    @transaction.atomic
    def approve_template(template, approved_by, effective_from_week, effective_from_year):
        """
        اعتماد القالب: بانتظار الاعتماد ← معتمد.
        يتم استبدال الإصدار المعتمد السابق لنفس القسم.
        """
        if template.status != FormTemplate.Status.PENDING_APPROVAL:
            raise ValidationError(
                'لا يمكن اعتماد الاستمارة إلا إذا كانت بانتظار الاعتماد'
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

        # استبدال الإصدار المعتمد السابق لنفس القسم
        FormTemplate.objects.filter(
            qism=template.qism,
            status=FormTemplate.Status.APPROVED,
        ).update(status=FormTemplate.Status.SUPERSEDED)

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

        return template

    @staticmethod
    def get_active_template(qism_id, year=None, week_number=None):
        """
        الحصول على القالب النشط حالياً لقسم معين.
        إذا تم تحديد السنة والأسبوع، يتم إرجاع القالب الساري في ذلك الأسبوع.
        """
        qs = FormTemplate.objects.filter(
            qism_id=qism_id,
            status=FormTemplate.Status.APPROVED,
            effective_from_week__isnull=False,
            effective_from_year__isnull=False,
        )

        if year is not None and week_number is not None:
            from django.db.models import Q
            qs = qs.filter(
                Q(effective_from_year__lt=year) |
                Q(
                    effective_from_year=year,
                    effective_from_week__lte=week_number,
                )
            )

        template = qs.order_by(
            '-effective_from_year', '-effective_from_week'
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
