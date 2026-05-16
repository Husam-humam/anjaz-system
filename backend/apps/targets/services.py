"""
خدمة إدارة المستهدفات — تشمل CRUD وحساب التقدم الهرمي.

منطق التقدم:
- مستهدف مؤسسة → يُجمّع من كل الأقسام العادية النشطة
- مستهدف دائرة/مديرية → يُجمّع من أقسامها الفرعية (عبر MPTT descendants)
- مستهدف قسم → يُحسب من بياناته مباشرة

تجميع القيم يحترم accumulation_type للمؤشر:
- sum: مجموع كل القيم
- average: متوسط بسيط
- last_value: مسموح فقط على مستوى القسم (يرفضها النموذج على مستويات أعلى)
"""
from django.core.exceptions import ValidationError
from django.db.models import Avg, Sum

from apps.audit.models import AuditLog
from apps.audit.services import AuditService
from apps.indicators.models import Indicator
from apps.organization.models import OrganizationUnit, UnitType

from .models import Target


class TargetService:
    """خدمة إدارة المستهدفات والتقدّم الهرمي"""

    # ──────────────────────────────────────────
    # CRUD
    # ──────────────────────────────────────────

    @staticmethod
    def create_target(data, set_by):
        """إنشاء مستهدف جديد على أي مستوى (مؤسسة/دائرة/مديرية/قسم)"""
        target = Target(**data)
        target.set_by = set_by
        target.full_clean()
        target.save()

        # نُمرِّر scope_unit كـ qism فقط إذا كان فعلاً قسماً (UnitType.QISM).
        scope_unit = target.scope_unit
        audit_qism = (
            scope_unit
            if scope_unit is not None and scope_unit.unit_type == UnitType.QISM
            else None
        )

        AuditService.log(
            action_type=AuditLog.ActionType.TARGET_CREATED,
            actor=set_by,
            target=target,
            qism=audit_qism,
            metadata={
                'year': target.year,
                'indicator_id': target.indicator_id,
                'scope_unit_id': target.scope_unit_id,
                'target_value': str(target.target_value),
            },
        )

        return target

    # الحقول التي تُحدِّد «هويّة» المستهدف وتربطه بالبيانات التاريخية.
    # تعديلها بعد وجود منجزات لنفس السنة يكسر مقارنات «الإنجاز مقابل المستهدف».
    IDENTITY_FIELDS = ('year', 'indicator', 'indicator_id', 'scope_unit', 'scope_unit_id')

    @staticmethod
    def update_target(target, data, actor=None):
        """
        تحديث مستهدف.
        - الحقول التعريفية (year/indicator/scope/scope_unit) مقفلة إذا وُجدت
          منجزات لنفس السنة والمؤشر، حفاظاً على صحّة التقارير التاريخية.
        - `target_value` و `notes` يبقيان قابلَين للتعديل دائماً (مع اعتبارهما
          «تحديث خطة» وليس إعادة كتابة تاريخ).
        """
        identity_changed = any(
            field in data
            and getattr(target, field, None) != data[field]
            for field in TargetService.IDENTITY_FIELDS
        )
        if identity_changed:
            from apps.submissions.models import WeeklySubmission
            has_submissions = WeeklySubmission.objects.filter(
                weekly_period__year=target.year,
                answers__form_item__indicator_id=target.indicator_id,
            ).exists()
            if has_submissions:
                raise ValidationError(
                    'لا يمكن تعديل سنة المستهدف أو مؤشره أو نطاقه بعد وجود '
                    'منجزات مسجّلة لنفس السنة. يمكن تعديل قيمة المستهدف فقط.'
                )

        # جمع فروقات القيم قبل التحديث (للـ audit)
        field_changes = []
        for key, value in data.items():
            old_value = getattr(target, key, None)
            if old_value != value:
                field_changes.append({
                    'field': key,
                    'old': str(old_value) if old_value is not None else None,
                    'new': str(value) if value is not None else None,
                })
            setattr(target, key, value)

        target.full_clean()
        target.save()

        if actor is not None and field_changes:
            scope_unit = target.scope_unit
            audit_qism = (
                scope_unit
                if scope_unit is not None and scope_unit.unit_type == UnitType.QISM
                else None
            )
            AuditService.log(
                action_type=AuditLog.ActionType.TARGET_UPDATED,
                actor=actor,
                target=target,
                qism=audit_qism,
                field_changes=field_changes,
            )

        return target

    @staticmethod
    def delete_target(target, actor=None):
        """
        حذف مستهدف.
        يُرفض الحذف إذا كانت هناك منجزات مسجّلة لنفس السنة والمؤشر —
        المستهدفات اختيارية لكن حذفها مع وجود بيانات يُربك التقارير.
        """
        from apps.submissions.models import WeeklySubmission
        has_submissions = WeeklySubmission.objects.filter(
            weekly_period__year=target.year,
            answers__form_item__indicator_id=target.indicator_id,
        ).exists()
        if has_submissions:
            raise ValidationError(
                'لا يمكن حذف مستهدف مرتبط بمنجزات مسجّلة. '
                'يمكن تعديل قيمته بدلاً من ذلك.'
            )

        # نحفظ معرّف الكائن قبل الحذف لأنه سيُصبح None بعد delete()
        if actor is not None:
            scope_unit = target.scope_unit
            audit_qism = (
                scope_unit
                if scope_unit is not None and scope_unit.unit_type == UnitType.QISM
                else None
            )
            AuditService.log(
                action_type=AuditLog.ActionType.TARGET_DELETED,
                actor=actor,
                target_model='Target',
                target_id=target.pk,
                target_repr=str(target)[:255],
                qism=audit_qism,
                metadata={
                    'year': target.year,
                    'indicator_id': target.indicator_id,
                    'scope_unit_id': target.scope_unit_id,
                    'target_value': str(target.target_value),
                },
            )

        target.delete()

    # ──────────────────────────────────────────
    # حساب التقدم الهرمي
    # ──────────────────────────────────────────

    @staticmethod
    def get_scope_qism_ids(scope_unit):
        """
        إرجاع قائمة معرّفات الأقسام العادية النشطة التي تنتمي إلى نطاق معيّن.
        - scope_unit = None → كل الأقسام العادية النشطة (مستوى المؤسسة)
        - scope_unit.unit_type = 'qism' → معرّف هذا القسم فقط
        - scope_unit.unit_type = 'mudiriya' / 'daira' → كل الأقسام التابعة (عبر MPTT)
        """
        # الأقسام «العاديّة» الآن = أقسام مُشرَف عليها (لها SupervisedUnit)
        base_qs = OrganizationUnit.objects.filter(
            unit_type=UnitType.QISM,
            is_active=True,
            supervisor_link__isnull=False,
        )

        if scope_unit is None:
            return list(base_qs.values_list('id', flat=True))

        if scope_unit.unit_type == UnitType.QISM:
            return [scope_unit.id]

        # لأقسام التابعة لمديرية أو دائرة — نستخدم MPTT
        # نعيد تحميل الوحدة من قاعدة البيانات لتجنّب MPTT staleness
        fresh_unit = OrganizationUnit.objects.get(pk=scope_unit.pk)
        descendants = fresh_unit.get_descendants(include_self=False).filter(
            unit_type=UnitType.QISM,
            is_active=True,
            supervisor_link__isnull=False,
        )
        return list(descendants.values_list('id', flat=True))

    @staticmethod
    def compute_cumulative_value(indicator, qism_ids, year):
        """
        يحسب القيمة التراكمية لمؤشر عبر مجموعة من الأقسام في سنة معيّنة،
        بناءً على accumulation_type للمؤشر.

        يقرأ من SubmissionAnswer (الإجابات المعتمدة فقط).
        """
        from apps.submissions.models import SubmissionAnswer, WeeklySubmission

        if not qism_ids:
            return 0

        answers = SubmissionAnswer.objects.filter(
            submission__qism_id__in=qism_ids,
            submission__weekly_period__year=year,
            submission__status__in=[
                WeeklySubmission.Status.SUBMITTED,
                WeeklySubmission.Status.APPROVED,
            ],
            form_item__indicator=indicator,
            numeric_value__isnull=False,
        )

        acc_type = indicator.accumulation_type

        if acc_type == Indicator.AccumulationType.SUM:
            result = answers.aggregate(total=Sum('numeric_value'))
            return result['total'] or 0

        if acc_type == Indicator.AccumulationType.AVERAGE:
            # المتوسط البسيط عبر كل الإجابات من كل الأقسام في النطاق
            result = answers.aggregate(avg=Avg('numeric_value'))
            return result['avg'] or 0

        if acc_type == Indicator.AccumulationType.LAST_VALUE:
            # آخر قيمة مسموح فقط على مستوى قسم واحد — أصغر تعقيد
            last = answers.order_by(
                '-submission__weekly_period__week_number'
            ).first()
            return last.numeric_value if last else 0

        return 0

    @staticmethod
    def compute_target_progress(target):
        """
        حساب تقدّم مستهدف واحد.
        ترجع قاموساً بالبيانات الكاملة: cumulative, percentage, remaining، إلخ.
        """
        qism_ids = TargetService.get_scope_qism_ids(target.scope_unit)
        cumulative = TargetService.compute_cumulative_value(
            indicator=target.indicator,
            qism_ids=qism_ids,
            year=target.year,
        )
        target_value = target.target_value or 0
        percentage = (
            (cumulative / target_value * 100) if target_value > 0 else 0
        )
        remaining = max(target_value - cumulative, 0)

        return {
            'cumulative_value': round(cumulative, 2),
            'target_value': target_value,
            'remaining': round(remaining, 2),
            'progress_percentage': round(percentage, 1),
            'qisms_in_scope': len(qism_ids),
        }

    @staticmethod
    def compute_scope_breakdown(target):
        """
        حساب تفصيل مساهمة كل قسم في تحقيق مستهدف هرمي (دائرة/مديرية/مؤسسة).
        لا معنى لها على مستوى القسم المفرد.

        ترجع قائمة من القواميس لكل قسم، مرتّبة تنازلياً حسب المساهمة:
        [
            {
                'qism_id': ...,
                'qism_name': ...,
                'contribution_value': ...,  # قيمة ما ساهم به القسم
                'contribution_percentage_of_achieved': ...,  # نسبة من المحقّق
                'contribution_percentage_of_target': ...,  # نسبة من المستهدف
            },
            ...
        ]
        """
        from apps.submissions.models import SubmissionAnswer, WeeklySubmission

        qism_ids = TargetService.get_scope_qism_ids(target.scope_unit)
        if not qism_ids:
            return []

        indicator = target.indicator

        # جلب قائمة الأقسام مع أسمائها
        qism_map = {
            q.id: q for q in OrganizationUnit.objects.filter(id__in=qism_ids)
        }

        # جمع الإجابات وتجميعها حسب القسم
        answers_qs = SubmissionAnswer.objects.filter(
            submission__qism_id__in=qism_ids,
            submission__weekly_period__year=target.year,
            submission__status__in=[
                WeeklySubmission.Status.SUBMITTED,
                WeeklySubmission.Status.APPROVED,
            ],
            form_item__indicator=indicator,
            numeric_value__isnull=False,
        ).values('submission__qism_id')

        acc_type = indicator.accumulation_type
        if acc_type == Indicator.AccumulationType.SUM:
            grouped = answers_qs.annotate(value=Sum('numeric_value'))
        elif acc_type == Indicator.AccumulationType.AVERAGE:
            grouped = answers_qs.annotate(value=Avg('numeric_value'))
        else:
            # last_value لا يُفترض أن يصل هنا (محظور على المستويات الهرمية)
            # لكن للسلامة: نستخدم آخر قيمة لكل قسم
            grouped = []  # سنحسبها يدوياً
            per_qism = {}
            for q_id in qism_ids:
                last = SubmissionAnswer.objects.filter(
                    submission__qism_id=q_id,
                    submission__weekly_period__year=target.year,
                    submission__status__in=[
                        WeeklySubmission.Status.SUBMITTED,
                        WeeklySubmission.Status.APPROVED,
                    ],
                    form_item__indicator=indicator,
                    numeric_value__isnull=False,
                ).order_by('-submission__weekly_period__week_number').first()
                if last:
                    per_qism[q_id] = last.numeric_value
            grouped = [
                {'submission__qism_id': qid, 'value': v}
                for qid, v in per_qism.items()
            ]

        # المجموع الكلي للمحقّق (لحساب النسب)
        total_achieved = sum((row['value'] or 0) for row in grouped)
        target_value = target.target_value or 0

        result = []
        for row in grouped:
            qid = row['submission__qism_id']
            value = row['value'] or 0
            qism = qism_map.get(qid)
            if not qism:
                continue

            pct_of_achieved = (
                (value / total_achieved * 100) if total_achieved > 0 else 0
            )
            pct_of_target = (
                (value / target_value * 100) if target_value > 0 else 0
            )

            result.append({
                'qism_id': qid,
                'qism_name': qism.name,
                'qism_code': qism.code,
                'contribution_value': round(value, 2),
                'contribution_percentage_of_achieved': round(pct_of_achieved, 1),
                'contribution_percentage_of_target': round(pct_of_target, 1),
            })

        # إضافة الأقسام التي لم تساهم (0) لتعطي الصورة الكاملة
        contributing_ids = {r['qism_id'] for r in result}
        for q_id in qism_ids:
            if q_id in contributing_ids:
                continue
            qism = qism_map.get(q_id)
            if not qism:
                continue
            result.append({
                'qism_id': q_id,
                'qism_name': qism.name,
                'qism_code': qism.code,
                'contribution_value': 0,
                'contribution_percentage_of_achieved': 0,
                'contribution_percentage_of_target': 0,
            })

        # ترتيب تنازلي حسب المساهمة
        result.sort(key=lambda x: x['contribution_value'], reverse=True)
        return result

    # ──────────────────────────────────────────
    # تفصيل هرمي شجري (tree breakdown)
    # ──────────────────────────────────────────

    @staticmethod
    def _fetch_raw_values_by_qism(indicator, qism_ids, year):
        """
        يجلب كل القيم الخام مجمّعة حسب القسم (بدون تجميع رياضي).
        يُستخدم لبناء شجرة التفصيل بحيث يمكن إعادة تجميع أي عقدة بأي طريقة.
        يُرجع: {qism_id: [value1, value2, ...]}
        """
        from collections import defaultdict
        from apps.submissions.models import SubmissionAnswer, WeeklySubmission

        if not qism_ids:
            return {}

        answers = SubmissionAnswer.objects.filter(
            submission__qism_id__in=qism_ids,
            submission__weekly_period__year=year,
            submission__status__in=[
                WeeklySubmission.Status.SUBMITTED,
                WeeklySubmission.Status.APPROVED,
            ],
            form_item__indicator=indicator,
            numeric_value__isnull=False,
        ).values('submission__qism_id', 'numeric_value')

        result = defaultdict(list)
        for row in answers:
            result[row['submission__qism_id']].append(row['numeric_value'])
        return dict(result)

    @staticmethod
    def _aggregate_values(values, accumulation_type):
        """تجميع قائمة قيم وفق accumulation_type"""
        if not values:
            return 0
        if accumulation_type == Indicator.AccumulationType.SUM:
            return sum(values)
        if accumulation_type == Indicator.AccumulationType.AVERAGE:
            return sum(values) / len(values)
        if accumulation_type == Indicator.AccumulationType.LAST_VALUE:
            return values[-1]
        return 0

    @staticmethod
    def _build_breakdown_node(unit, raw_values_by_qism, acc_type,
                               total_achieved, target_value,
                               all_scope_qism_ids):
        """
        يبني عقدة في شجرة التفصيل بشكل recursive.
        - إذا كانت العقدة قسماً: تُرجع بياناتها (leaf)
        - إذا كانت دائرة/مديرية: تُرجع بياناتها مع أبنائها
        يتجاهل الوحدات غير النشطة والأقسام غير النظامية.
        ترجع None إذا لم تكن العقدة ضمن النطاق ولا تحتوي على أي وحدة ضمنه.
        """
        from apps.organization.models import UnitType

        # أقسام — ورقة (يجب أن تكون مُشرَفاً عليها — لها supervisor_link)
        if unit.unit_type == UnitType.QISM:
            if not unit.is_active:
                return None
            if unit.id not in all_scope_qism_ids:
                return None
            values = raw_values_by_qism.get(unit.id, [])
            value = TargetService._aggregate_values(values, acc_type)
            pct_of_achieved = (
                (value / total_achieved * 100) if total_achieved > 0 else 0
            )
            pct_of_target = (
                (value / target_value * 100) if target_value > 0 else 0
            )
            return {
                'unit_id': unit.id,
                'unit_name': unit.name,
                'unit_code': unit.code,
                'unit_type': 'qism',
                'contribution_value': round(value, 2),
                'contribution_percentage_of_achieved': round(pct_of_achieved, 1),
                'contribution_percentage_of_target': round(pct_of_target, 1),
                'has_children': False,
                'children': [],
            }

        # دائرة أو مديرية — عقدة داخلية
        if not unit.is_active:
            return None

        # بناء الأبناء recursively
        children_nodes = []
        for child in unit.get_children():
            child_node = TargetService._build_breakdown_node(
                child, raw_values_by_qism, acc_type,
                total_achieved, target_value, all_scope_qism_ids,
            )
            if child_node is not None:
                children_nodes.append(child_node)

        # احسب قيمة العقدة من كل الأقسام الورقية تحتها (عبر raw values)
        # نُعيد بناء descendants للعقدة الحالية لنحسم القيم الخام
        descendant_qism_ids = list(
            unit.get_descendants().filter(
                unit_type=UnitType.QISM,
                is_active=True,
                supervisor_link__isnull=False,
            ).values_list('id', flat=True)
        )
        # استبعاد الأقسام غير الموجودة في النطاق
        in_scope_ids = [
            qid for qid in descendant_qism_ids if qid in all_scope_qism_ids
        ]

        all_raw = []
        for qid in in_scope_ids:
            all_raw.extend(raw_values_by_qism.get(qid, []))
        value = TargetService._aggregate_values(all_raw, acc_type)

        # إذا لا توجد أي أقسام ضمن النطاق تحت هذه العقدة، نتخطّاها
        if not in_scope_ids and not children_nodes:
            return None

        pct_of_achieved = (
            (value / total_achieved * 100) if total_achieved > 0 else 0
        )
        pct_of_target = (
            (value / target_value * 100) if target_value > 0 else 0
        )

        # ترتيب الأبناء تنازلياً حسب المساهمة
        children_nodes.sort(
            key=lambda x: x['contribution_value'], reverse=True
        )

        return {
            'unit_id': unit.id,
            'unit_name': unit.name,
            'unit_code': unit.code,
            'unit_type': unit.unit_type,
            'contribution_value': round(value, 2),
            'contribution_percentage_of_achieved': round(pct_of_achieved, 1),
            'contribution_percentage_of_target': round(pct_of_target, 1),
            'has_children': len(children_nodes) > 0,
            'children': children_nodes,
        }

    @staticmethod
    def compute_scope_breakdown_tree(target):
        """
        يحسب تفصيل المستهدف كشجرة هرمية قابلة للتوسيع.
        - مستهدف مؤسسة: الجذور = الدوائر + المديريات اليتيمة (بدون دائرة أب)
        - مستهدف دائرة: الجذور = أبناء الدائرة المباشرة (مديريات + أقسام مباشرة)
        - مستهدف مديرية: الجذور = أبناء المديرية المباشرة (أقسام عادةً)
        - مستهدف قسم: يُرجع قائمة فارغة (لا تفصيل)
        """
        from django.db.models import Q
        from apps.organization.models import UnitType

        scope_unit = target.scope_unit
        indicator = target.indicator
        year = target.year
        acc_type = indicator.accumulation_type
        target_value = target.target_value or 0

        # أقسام ضمن النطاق
        scope_qism_ids = TargetService.get_scope_qism_ids(scope_unit)
        if not scope_qism_ids:
            return []

        scope_qism_set = set(scope_qism_ids)

        # جلب القيم الخام لكل قسم (استعلام واحد)
        raw_values_by_qism = TargetService._fetch_raw_values_by_qism(
            indicator, scope_qism_ids, year
        )

        # القيمة الكلية المحقّقة (لحساب نسب "من المحقّق")
        all_raw = []
        for qid in scope_qism_ids:
            all_raw.extend(raw_values_by_qism.get(qid, []))
        total_achieved = TargetService._aggregate_values(all_raw, acc_type)

        # تحديد الجذور حسب مستوى المستهدف
        if scope_unit is None:
            # مستوى المؤسسة: دوائر + مديريات بدون أب + أقسام بدون أب (نادراً)
            roots = list(
                OrganizationUnit.objects.filter(
                    Q(unit_type=UnitType.DAIRA, is_active=True) |
                    Q(unit_type=UnitType.MUDIRIYA, parent__isnull=True, is_active=True)
                )
            )
        elif scope_unit.unit_type == UnitType.QISM:
            # لا تفصيل لمستهدف قسم
            return []
        else:
            # دائرة أو مديرية: الأبناء المباشرون
            fresh_scope = OrganizationUnit.objects.get(pk=scope_unit.pk)
            roots = list(fresh_scope.get_children())

        # بناء الشجرة
        tree = []
        for root in roots:
            node = TargetService._build_breakdown_node(
                root, raw_values_by_qism, acc_type,
                total_achieved, target_value, scope_qism_set,
            )
            if node is not None:
                tree.append(node)

        # ترتيب تنازلي حسب المساهمة
        tree.sort(key=lambda x: x['contribution_value'], reverse=True)
        return tree

    # ──────────────────────────────────────────
    # استعلامات مساعدة
    # ──────────────────────────────────────────

    @staticmethod
    def get_targets_for_scope(scope_unit_id, year):
        """
        الحصول على مستهدفات نطاق معيّن لسنة معيّنة.
        scope_unit_id = None يعني مستوى المؤسسة.
        """
        qs = Target.objects.filter(year=year)
        if scope_unit_id is None:
            qs = qs.filter(scope_unit__isnull=True)
        else:
            qs = qs.filter(scope_unit_id=scope_unit_id)
        return qs.select_related('indicator', 'scope_unit')
