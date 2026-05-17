"""
خدمة إدارة المستهدفات المركّبة — تشمل CRUD وحساب التقدّم الهرمي.

المستهدف المركّب:
- اسم وصفي + قيمة مستهدفة + قائمة مؤشّرات (مكوّن أو أكثر).
- القيمة الفعليّة = جمع قيم كل المكوّنات (جمع بسيط، بدون أوزان).
- كل المكوّنات بنفس unit_type (يُفحَص في create/update).

منطق التقدّم:
- مستهدف مؤسسة → يُجمَّع من كل الأقسام المُسنَدة النشطة
- مستهدف دائرة/مديرية → يُجمَّع من أقسامها الفرعيّة (عبر MPTT descendants)
- مستهدف قسم → يُحسَب من بياناته مباشرة

تجميع كل مؤشّر يحترم accumulation_type الخاصّ به (sum / average / last_value)،
ثم تُجمَع قيم المؤشّرات معاً بجمع بسيط.
"""
from collections import defaultdict

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

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
    @transaction.atomic
    def create_target(data, indicator_ids, set_by):
        """
        إنشاء مستهدف مركّب جديد.

        Args:
            data: dict يحوي name, scope_unit, year, target_value, notes
            indicator_ids: قائمة معرّفات المؤشّرات المُكوِّنة (مكوّن واحد على الأقلّ)
            set_by: المستخدم الذي يُنشئ المستهدف
        """
        target = Target(**data)
        target.set_by = set_by
        target.full_clean()  # يفحص الحقول البسيطة (name, target_value, scope)
        target.save()

        # جلب وفحص المؤشّرات (بعد الحفظ — M2M يحتاج pk)
        indicators = list(Indicator.objects.filter(id__in=indicator_ids))
        if len(indicators) != len(set(indicator_ids)):
            raise ValidationError({
                'indicators': 'بعض المؤشّرات المُختارة غير موجودة'
            })

        target.validate_components(indicators)  # يفحص unit_type, تكرار اسم...
        target.indicators.set(indicators)

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
                'name': target.name,
                'year': target.year,
                'indicator_ids': sorted(ind.id for ind in indicators),
                'scope_unit_id': target.scope_unit_id,
                'target_value': str(target.target_value),
            },
        )
        return target

    # الحقول التي تُحدِّد «هويّة» المستهدف وتربطه بالبيانات التاريخية.
    # تعديلها بعد وجود منجزات لنفس السنة يكسر مقارنات «الإنجاز مقابل المستهدف».
    IDENTITY_FIELDS = ('year', 'scope_unit', 'scope_unit_id')

    @staticmethod
    @transaction.atomic
    def update_target(target, data, indicator_ids=None, actor=None):
        """
        تحديث مستهدف مركّب.
        - الحقول التعريفيّة (year/scope_unit) و indicators مقفلة إذا وُجدت
          منجزات لنفس السنة وأيّ من المؤشّرات الحاليّة، حفاظاً على صحّة التقارير.
        - `target_value`, `notes`, `name` تبقى قابلة للتعديل دائماً.

        Args:
            data: حقول المستهدف للتحديث
            indicator_ids: قائمة جديدة من المؤشّرات (None = لا تغيير)
        """
        identity_changed = any(
            field in data
            and getattr(target, field, None) != data[field]
            for field in TargetService.IDENTITY_FIELDS
        )
        indicators_changed = (
            indicator_ids is not None
            and set(indicator_ids) != set(
                target.indicators.values_list('id', flat=True)
            )
        )

        if identity_changed or indicators_changed:
            from apps.submissions.models import WeeklySubmission
            current_indicator_ids = list(
                target.indicators.values_list('id', flat=True)
            )
            has_submissions = WeeklySubmission.objects.filter(
                weekly_period__year=target.year,
                answers__form_item__indicator_id__in=current_indicator_ids,
            ).exists()
            if has_submissions:
                raise ValidationError(
                    'لا يمكن تعديل سنة المستهدف أو نطاقه أو مكوّناته بعد وجود '
                    'منجزات مسجّلة. يمكن تعديل اسم المستهدف وقيمته وملاحظاته فقط.'
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

        # تحديث المكوّنات إن طُلب
        if indicator_ids is not None:
            indicators = list(Indicator.objects.filter(id__in=indicator_ids))
            if len(indicators) != len(set(indicator_ids)):
                raise ValidationError({
                    'indicators': 'بعض المؤشّرات المُختارة غير موجودة'
                })
            target.validate_components(indicators)
            target.indicators.set(indicators)

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
        يُرفض الحذف إذا كانت هناك منجزات مسجّلة لنفس السنة وأيّ من مؤشّراته.
        """
        from apps.submissions.models import WeeklySubmission
        indicator_ids = list(target.indicators.values_list('id', flat=True))
        has_submissions = WeeklySubmission.objects.filter(
            weekly_period__year=target.year,
            answers__form_item__indicator_id__in=indicator_ids,
        ).exists()
        if has_submissions:
            raise ValidationError(
                'لا يمكن حذف مستهدف مرتبط بمنجزات مسجّلة. '
                'يمكن تعديل قيمته بدلاً من ذلك.'
            )

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
                    'name': target.name,
                    'year': target.year,
                    'indicator_ids': sorted(indicator_ids),
                    'scope_unit_id': target.scope_unit_id,
                    'target_value': str(target.target_value),
                },
            )
        target.delete()

    # ──────────────────────────────────────────
    # حساب التقدّم — مكوّن واحد (داخلي)
    # ──────────────────────────────────────────

    @staticmethod
    def get_scope_qism_ids(scope_unit):
        """
        إرجاع قائمة معرّفات الأقسام المُسنَدة النشطة التي تنتمي إلى نطاق معيّن.
        """
        base_qs = OrganizationUnit.objects.filter(
            unit_type=UnitType.QISM,
            is_active=True,
            supervisor_link__isnull=False,
        )
        if scope_unit is None:
            return list(base_qs.values_list('id', flat=True))
        if scope_unit.unit_type == UnitType.QISM:
            return [scope_unit.id]
        fresh_unit = OrganizationUnit.objects.get(pk=scope_unit.pk)
        descendants = fresh_unit.get_descendants(include_self=False).filter(
            unit_type=UnitType.QISM,
            is_active=True,
            supervisor_link__isnull=False,
        )
        return list(descendants.values_list('id', flat=True))

    @staticmethod
    def _fetch_raw_values_by_qism(indicator, qism_ids, year):
        """
        يجلب القيم الخام لمؤشّر معيّن مجمّعة حسب القسم.
        يُرجع: {qism_id: [value1, value2, ...]}
        """
        from apps.submissions.models import SubmissionAnswer, WeeklySubmission
        if not qism_ids:
            return {}
        # المنجزات المُعتمَدة فقط (قاعدة عمل #5)
        answers = SubmissionAnswer.objects.filter(
            submission__qism_id__in=qism_ids,
            submission__weekly_period__year=year,
            submission__status=WeeklySubmission.Status.APPROVED,
            form_item__indicator=indicator,
            numeric_value__isnull=False,
        ).values('submission__qism_id', 'numeric_value')
        result = defaultdict(list)
        for row in answers:
            result[row['submission__qism_id']].append(row['numeric_value'])
        return dict(result)

    @staticmethod
    def _aggregate_values(values, accumulation_type):
        """تجميع قائمة قيم وفق accumulation_type للمؤشّر الواحد."""
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
    def _compute_indicator_value_for_scope(indicator, qism_ids, year):
        """
        قيمة مؤشّر واحد عبر نطاق معيّن (مجمّعة بطريقة accumulation_type).
        """
        raw_by_qism = TargetService._fetch_raw_values_by_qism(
            indicator, qism_ids, year,
        )
        all_values = []
        for qid in qism_ids:
            all_values.extend(raw_by_qism.get(qid, []))
        return TargetService._aggregate_values(all_values, indicator.accumulation_type)

    # ──────────────────────────────────────────
    # حساب التقدّم — مستهدف مركّب
    # ──────────────────────────────────────────

    @staticmethod
    def compute_target_progress(target):
        """
        تقدّم المستهدف المركّب.
        القيمة الكليّة = جمع قيم كل المؤشّرات (المركّبات) عبر النطاق.
        كما يعود تفصيل لكل مكوّن ضمن `components`.
        """
        qism_ids = TargetService.get_scope_qism_ids(target.scope_unit)
        indicators = list(target.indicators.all())

        components = []
        total_value = 0
        for indicator in indicators:
            value = TargetService._compute_indicator_value_for_scope(
                indicator, qism_ids, target.year,
            )
            total_value += value
            components.append({
                'indicator_id': indicator.id,
                'indicator_name': indicator.name,
                'unit_type': indicator.unit_type,
                'accumulation_type': indicator.accumulation_type,
                'value': round(value, 2),
            })

        target_value = target.target_value or 0
        percentage = (total_value / target_value * 100) if target_value > 0 else 0
        remaining = max(target_value - total_value, 0)

        return {
            'cumulative_value': round(total_value, 2),
            'target_value': target_value,
            'remaining': round(remaining, 2),
            'progress_percentage': round(percentage, 1),
            'qisms_in_scope': len(qism_ids),
            'components': components,
        }

    @staticmethod
    def compute_scope_breakdown(target):
        """
        تفصيل مساهمة كل قسم في تحقيق المستهدف المركّب.
        لكل قسم: نجمع قيم كل المكوّنات (سلوك مماثل لـ compute_target_progress
        لكن على مستوى كل قسم منفرد).
        """
        qism_ids = TargetService.get_scope_qism_ids(target.scope_unit)
        if not qism_ids:
            return []

        qism_map = {
            q.id: q for q in OrganizationUnit.objects.filter(id__in=qism_ids)
        }

        # نجمع لكل قسم: قيمة كل مؤشّر، ثم نجمعها معاً
        values_by_qism = defaultdict(float)
        for indicator in target.indicators.all():
            raw_by_qism = TargetService._fetch_raw_values_by_qism(
                indicator, qism_ids, target.year,
            )
            for qid in qism_ids:
                values_by_qism[qid] += TargetService._aggregate_values(
                    raw_by_qism.get(qid, []), indicator.accumulation_type,
                )

        total_achieved = sum(values_by_qism.values())
        target_value = target.target_value or 0

        result = []
        for qid, value in values_by_qism.items():
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
        result.sort(key=lambda x: x['contribution_value'], reverse=True)
        return result

    # ──────────────────────────────────────────
    # شجرة التفصيل الهرميّة
    # ──────────────────────────────────────────

    @staticmethod
    def _compute_value_for_qisms(target, qism_ids):
        """
        مجموع قيم كل مؤشّرات المستهدف عبر مجموعة من الأقسام.
        يُستخدم لحساب قيمة العقدة الهرميّة في الشجرة.
        """
        total = 0
        for indicator in target.indicators.all():
            total += TargetService._compute_indicator_value_for_scope(
                indicator, qism_ids, target.year,
            )
        return total

    @staticmethod
    def _build_breakdown_node(unit, target, total_achieved, target_value,
                               all_scope_qism_ids):
        """يبني عقدة في شجرة التفصيل بشكل recursive."""
        if unit.unit_type == UnitType.QISM:
            if not unit.is_active or unit.id not in all_scope_qism_ids:
                return None
            value = TargetService._compute_value_for_qisms(target, [unit.id])
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

        if not unit.is_active:
            return None

        children_nodes = []
        for child in unit.get_children():
            child_node = TargetService._build_breakdown_node(
                child, target, total_achieved, target_value, all_scope_qism_ids,
            )
            if child_node is not None:
                children_nodes.append(child_node)

        descendant_qism_ids = list(
            unit.get_descendants().filter(
                unit_type=UnitType.QISM,
                is_active=True,
                supervisor_link__isnull=False,
            ).values_list('id', flat=True)
        )
        in_scope_ids = [
            qid for qid in descendant_qism_ids if qid in all_scope_qism_ids
        ]
        value = TargetService._compute_value_for_qisms(target, in_scope_ids)

        if not in_scope_ids and not children_nodes:
            return None

        pct_of_achieved = (
            (value / total_achieved * 100) if total_achieved > 0 else 0
        )
        pct_of_target = (
            (value / target_value * 100) if target_value > 0 else 0
        )
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
        """شجرة هرميّة قابلة للتوسيع تُبيّن مساهمة كل عقدة."""
        scope_unit = target.scope_unit
        target_value = target.target_value or 0
        scope_qism_ids = TargetService.get_scope_qism_ids(scope_unit)
        if not scope_qism_ids:
            return []
        scope_qism_set = set(scope_qism_ids)
        total_achieved = TargetService._compute_value_for_qisms(
            target, scope_qism_ids,
        )

        if scope_unit is None:
            roots = list(
                OrganizationUnit.objects.filter(
                    Q(unit_type=UnitType.DAIRA, is_active=True) |
                    Q(unit_type=UnitType.MUDIRIYA, parent__isnull=True, is_active=True)
                )
            )
        elif scope_unit.unit_type == UnitType.QISM:
            return []
        else:
            fresh_scope = OrganizationUnit.objects.get(pk=scope_unit.pk)
            roots = list(fresh_scope.get_children())

        tree = []
        for root in roots:
            node = TargetService._build_breakdown_node(
                root, target, total_achieved, target_value, scope_qism_set,
            )
            if node is not None:
                tree.append(node)
        tree.sort(key=lambda x: x['contribution_value'], reverse=True)
        return tree

    # ──────────────────────────────────────────
    # استعلامات مساعدة
    # ──────────────────────────────────────────

    @staticmethod
    def get_targets_for_scope(scope_unit_id, year):
        """مستهدفات نطاق معيّن لسنة معيّنة."""
        qs = Target.objects.filter(year=year)
        if scope_unit_id is None:
            qs = qs.filter(scope_unit__isnull=True)
        else:
            qs = qs.filter(scope_unit_id=scope_unit_id)
        return qs.select_related('scope_unit').prefetch_related('indicators')
