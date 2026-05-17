"""
اختبارات خدمات المستهدفات — TargetService.
تغطي: CRUD، حساب التقدم الهرمي، تفصيل مساهمة الأقسام.
"""
import pytest
from django.core.exceptions import ValidationError

from apps.accounts.tests.factories import StatisticsAdminFactory
from apps.forms.tests.factories import (
    FormTemplateFactory, FormTemplateItemFactory,
)
from apps.indicators.tests.factories import IndicatorFactory
from apps.organization.models import PlanningAssignment, SupervisedUnit
from apps.organization.tests.factories import (
    DairaFactory, MudiriyaFactory, PlanningQismFactory, QismFactory,
)
from apps.submissions.tests.factories import (
    SubmissionAnswerFactory, WeeklyPeriodFactory, WeeklySubmissionFactory,
)
from apps.targets.models import Target
from apps.targets.services import TargetService
from apps.targets.tests.factories import TargetFactory


def _make_supervised_qism(**kwargs):
    """ينشئ قسماً عاديّاً مرتبطاً بـ PlanningAssignment + SupervisedUnit.

    يقبل نفس kwargs الخاصة بـ QismFactory (parent, is_active, ...).
    """
    qism = QismFactory(**kwargs)
    planning = PlanningQismFactory(parent=qism.parent)
    assignment, _ = PlanningAssignment.objects.get_or_create(planning_unit=planning)
    SupervisedUnit.objects.get_or_create(assignment=assignment, unit=qism)
    return qism


@pytest.mark.django_db
class TestTargetServiceCRUD:
    """اختبارات العمليات الأساسية (إنشاء/تحديث/حذف)"""

    def test_create_qism_target(self):
        """إنشاء مستهدف على مستوى قسم"""
        admin = StatisticsAdminFactory()
        qism = _make_supervised_qism()
        indicator = IndicatorFactory(
            unit_type="number", accumulation_type="sum"
        )
        data = {
            'scope_unit': qism,
            'indicator': indicator,
            'year': 2026,
            'target_value': 150.0,
            'notes': 'مستهدف اختبار',
        }
        target = TargetService.create_target(data, set_by=admin)
        assert target.pk is not None
        assert target.scope_unit == qism
        assert target.scope_level == 'qism'
        assert target.set_by == admin

    def test_create_institution_target(self):
        """إنشاء مستهدف على مستوى المؤسسة"""
        admin = StatisticsAdminFactory()
        indicator = IndicatorFactory(
            unit_type="number", accumulation_type="sum"
        )
        data = {
            'scope_unit': None,
            'indicator': indicator,
            'year': 2026,
            'target_value': 1000.0,
        }
        target = TargetService.create_target(data, set_by=admin)
        assert target.scope_unit is None
        assert target.scope_level == 'institution'

    def test_create_daira_target(self):
        """إنشاء مستهدف على مستوى دائرة"""
        admin = StatisticsAdminFactory()
        daira = DairaFactory()
        indicator = IndicatorFactory(
            unit_type="number", accumulation_type="sum"
        )
        data = {
            'scope_unit': daira,
            'indicator': indicator,
            'year': 2026,
            'target_value': 400.0,
        }
        target = TargetService.create_target(data, set_by=admin)
        assert target.scope_level == 'daira'

    def test_create_target_with_zero_value_fails(self):
        """فشل إنشاء مستهدف بقيمة صفر"""
        admin = StatisticsAdminFactory()
        qism = QismFactory()
        indicator = IndicatorFactory()
        data = {
            'scope_unit': qism,
            'indicator': indicator,
            'year': 2026,
            'target_value': 0,
        }
        with pytest.raises(ValidationError) as exc_info:
            TargetService.create_target(data, set_by=admin)
        assert 'target_value' in exc_info.value.message_dict

    def test_update_target(self):
        """تحديث مستهدف"""
        target = TargetFactory(scope_unit=_make_supervised_qism(), target_value=100.0)
        updated = TargetService.update_target(target, {'target_value': 200.0})
        assert updated.target_value == 200.0

    def test_delete_target(self):
        """حذف مستهدف"""
        target = TargetFactory(scope_unit=_make_supervised_qism())
        pk = target.pk
        TargetService.delete_target(target)
        assert not Target.objects.filter(pk=pk).exists()


@pytest.mark.django_db
class TestScopeQismIds:
    """اختبارات get_scope_qism_ids"""

    def test_institution_scope_returns_all_regular_qisms(self):
        """نطاق المؤسسة يُرجع كل الأقسام العادية النشطة"""
        q1 = _make_supervised_qism(is_active=True)
        q2 = _make_supervised_qism(is_active=True)
        _make_supervised_qism(is_active=False)  # غير نشط — يجب أن يُستبعد

        result = TargetService.get_scope_qism_ids(None)
        assert q1.id in result
        assert q2.id in result
        assert len(result) >= 2

    def test_qism_scope_returns_only_that_qism(self):
        """نطاق قسم يُرجع هذا القسم فقط"""
        qism = QismFactory()
        result = TargetService.get_scope_qism_ids(qism)
        assert result == [qism.id]

    def test_mudiriya_scope_returns_child_qisms(self):
        """نطاق مديرية يُرجع أقسامها التابعة"""
        mudiriya = MudiriyaFactory()
        q1 = _make_supervised_qism(parent=mudiriya)
        q2 = _make_supervised_qism(parent=mudiriya)
        # قسم في مديرية أخرى — لا يجب أن يظهر
        _make_supervised_qism()

        result = TargetService.get_scope_qism_ids(mudiriya)
        assert q1.id in result
        assert q2.id in result
        assert len(result) == 2

    def test_daira_scope_returns_nested_qisms(self):
        """نطاق دائرة يُرجع الأقسام المتداخلة عبر المديريات"""
        daira = DairaFactory()
        mudiriya = MudiriyaFactory(parent=daira)
        q1 = _make_supervised_qism(parent=mudiriya)
        q2 = _make_supervised_qism(parent=mudiriya)

        result = TargetService.get_scope_qism_ids(daira)
        assert q1.id in result
        assert q2.id in result


@pytest.mark.django_db
class TestTargetProgress:
    """اختبارات حساب تقدم المستهدف"""

    @staticmethod
    def _get_or_create_template(qism, indicator):
        """يُرجع (template, item) — يُعيد استخدام القائم إن وُجد"""
        from apps.forms.models import FormTemplate
        template = FormTemplate.objects.filter(qism=qism, status='approved').first()
        if not template:
            template = FormTemplateFactory(qism=qism, status='approved')
        item = template.items.filter(indicator=indicator).first()
        if not item:
            item = FormTemplateItemFactory(
                form_template=template, indicator=indicator
            )
        return template, item

    @staticmethod
    def _get_or_create_period(year, week):
        """يُرجع فترة أسبوعية (تُعيد الاستخدام لتجنّب تعارض unique_together)"""
        from apps.submissions.models import WeeklyPeriod
        period = WeeklyPeriod.objects.filter(year=year, week_number=week).first()
        if not period:
            period = WeeklyPeriodFactory(year=year, week_number=week)
        return period

    def _create_submission_with_value(self, qism, indicator, value, year=2026, week=1):
        """مساعد لإنشاء إجابة معتمدة بقيمة معيّنة"""
        period = self._get_or_create_period(year, week)
        template, item = self._get_or_create_template(qism, indicator)
        submission = WeeklySubmissionFactory(
            qism=qism,
            weekly_period=period,
            form_template=template,
            status='approved',
        )
        SubmissionAnswerFactory(
            submission=submission,
            form_item=item,
            numeric_value=value,
        )

    def test_qism_progress_with_sum(self):
        """تقدم قسم لمؤشر sum"""
        qism = QismFactory()
        indicator = IndicatorFactory(
            unit_type="number", accumulation_type="sum"
        )
        self._create_submission_with_value(qism, indicator, 30, week=1)
        self._create_submission_with_value(qism, indicator, 20, week=2)

        target = TargetFactory(
            scope_unit=qism, indicator=indicator,
            year=2026, target_value=100,
        )
        progress = TargetService.compute_target_progress(target)

        assert progress['cumulative_value'] == 50
        assert progress['target_value'] == 100
        assert progress['progress_percentage'] == 50.0
        assert progress['remaining'] == 50
        assert progress['qisms_in_scope'] == 1

    def test_mudiriya_progress_aggregates_all_child_qisms(self):
        """تقدم مديرية يُجمّع من كل أقسامها"""
        mudiriya = MudiriyaFactory()
        q1 = QismFactory(parent=mudiriya)
        q2 = QismFactory(parent=mudiriya)
        indicator = IndicatorFactory(
            unit_type="number", accumulation_type="sum"
        )
        self._create_submission_with_value(q1, indicator, 30)
        self._create_submission_with_value(q2, indicator, 40)

        target = TargetFactory(
            scope_unit=mudiriya, indicator=indicator,
            year=2026, target_value=100,
        )
        progress = TargetService.compute_target_progress(target)

        assert progress['cumulative_value'] == 70  # 30 + 40
        assert progress['progress_percentage'] == 70.0
        assert progress['qisms_in_scope'] == 2

    def test_average_indicator_progress(self):
        """تقدم مؤشر average يُحسب كمتوسط"""
        mudiriya = MudiriyaFactory()
        q1 = QismFactory(parent=mudiriya)
        q2 = QismFactory(parent=mudiriya)
        indicator = IndicatorFactory(
            unit_type="percentage", accumulation_type="average"
        )
        self._create_submission_with_value(q1, indicator, 80)
        self._create_submission_with_value(q2, indicator, 90)

        target = TargetFactory(
            scope_unit=mudiriya, indicator=indicator,
            year=2026, target_value=95,
        )
        progress = TargetService.compute_target_progress(target)
        # المتوسط = (80+90)/2 = 85
        assert progress['cumulative_value'] == 85
        # النسبة = 85/95 ≈ 89.5%
        assert abs(progress['progress_percentage'] - 89.5) < 0.1

    def test_progress_for_empty_scope(self):
        """تقدم مستهدف دون أي إجابات = 0"""
        mudiriya = MudiriyaFactory()
        QismFactory(parent=mudiriya)
        indicator = IndicatorFactory(
            unit_type="number", accumulation_type="sum"
        )
        target = TargetFactory(
            scope_unit=mudiriya, indicator=indicator,
            year=2026, target_value=100,
        )
        progress = TargetService.compute_target_progress(target)
        assert progress['cumulative_value'] == 0
        assert progress['progress_percentage'] == 0


@pytest.mark.django_db
class TestScopeBreakdown:
    """اختبارات تفصيل مساهمة الأقسام"""

    @staticmethod
    def _get_or_create_template(qism, indicator):
        from apps.forms.models import FormTemplate
        template = FormTemplate.objects.filter(qism=qism, status='approved').first()
        if not template:
            template = FormTemplateFactory(qism=qism, status='approved')
        item = template.items.filter(indicator=indicator).first()
        if not item:
            item = FormTemplateItemFactory(
                form_template=template, indicator=indicator
            )
        return template, item

    @staticmethod
    def _get_or_create_period(year, week):
        from apps.submissions.models import WeeklyPeriod
        period = WeeklyPeriod.objects.filter(year=year, week_number=week).first()
        if not period:
            period = WeeklyPeriodFactory(year=year, week_number=week)
        return period

    def _create_submission_with_value(self, qism, indicator, value, week=1):
        period = self._get_or_create_period(2026, week)
        template, item = self._get_or_create_template(qism, indicator)
        submission = WeeklySubmissionFactory(
            qism=qism,
            weekly_period=period,
            form_template=template,
            status='approved',
        )
        SubmissionAnswerFactory(
            submission=submission, form_item=item, numeric_value=value,
        )

    def test_breakdown_shows_all_qisms(self):
        """التفصيل يُظهر كل الأقسام حتى غير المساهمة"""
        mudiriya = MudiriyaFactory()
        q1 = _make_supervised_qism(parent=mudiriya)
        q2 = _make_supervised_qism(parent=mudiriya)
        q3 = _make_supervised_qism(parent=mudiriya)  # لن يساهم
        indicator = IndicatorFactory(
            unit_type="number", accumulation_type="sum"
        )
        self._create_submission_with_value(q1, indicator, 60)
        self._create_submission_with_value(q2, indicator, 40)

        target = TargetFactory(
            scope_unit=mudiriya, indicator=indicator,
            year=2026, target_value=200,
        )
        breakdown = TargetService.compute_scope_breakdown(target)

        assert len(breakdown) == 3
        ids = {row['qism_id'] for row in breakdown}
        assert q1.id in ids
        assert q2.id in ids
        assert q3.id in ids

        # الأقسام المساهمة مرتّبة تنازلياً
        assert breakdown[0]['contribution_value'] == 60
        assert breakdown[1]['contribution_value'] == 40
        # القسم غير المساهم في الأخير بقيمة 0
        assert breakdown[2]['contribution_value'] == 0

    def test_breakdown_percentages(self):
        """حسابات النسب في التفصيل صحيحة"""
        mudiriya = MudiriyaFactory()
        q1 = QismFactory(parent=mudiriya)
        q2 = QismFactory(parent=mudiriya)
        indicator = IndicatorFactory(
            unit_type="number", accumulation_type="sum"
        )
        self._create_submission_with_value(q1, indicator, 60)  # 60% من 100
        self._create_submission_with_value(q2, indicator, 40)  # 40% من 100

        target = TargetFactory(
            scope_unit=mudiriya, indicator=indicator,
            year=2026, target_value=200,  # المحقّق 100 من 200 = 50%
        )
        breakdown = TargetService.compute_scope_breakdown(target)

        q1_row = next(r for r in breakdown if r['qism_id'] == q1.id)
        q2_row = next(r for r in breakdown if r['qism_id'] == q2.id)

        # من المحقق (100)
        assert q1_row['contribution_percentage_of_achieved'] == 60.0
        assert q2_row['contribution_percentage_of_achieved'] == 40.0
        # من المستهدف (200)
        assert q1_row['contribution_percentage_of_target'] == 30.0
        assert q2_row['contribution_percentage_of_target'] == 20.0


@pytest.mark.django_db
class TestBreakdownTree:
    """اختبارات شجرة التفصيل (tree) لمستهدفات هرمية"""

    @staticmethod
    def _get_or_create_template(qism, indicator):
        from apps.forms.models import FormTemplate
        template = FormTemplate.objects.filter(qism=qism, status='approved').first()
        if not template:
            template = FormTemplateFactory(qism=qism, status='approved')
        item = template.items.filter(indicator=indicator).first()
        if not item:
            item = FormTemplateItemFactory(
                form_template=template, indicator=indicator
            )
        return template, item

    @staticmethod
    def _get_or_create_period(year, week):
        from apps.submissions.models import WeeklyPeriod
        p = WeeklyPeriod.objects.filter(year=year, week_number=week).first()
        if not p:
            p = WeeklyPeriodFactory(year=year, week_number=week)
        return p

    def _submit(self, qism, indicator, value, week=1):
        period = self._get_or_create_period(2026, week)
        template, item = self._get_or_create_template(qism, indicator)
        submission = WeeklySubmissionFactory(
            qism=qism, weekly_period=period,
            form_template=template, status='approved',
        )
        SubmissionAnswerFactory(
            submission=submission, form_item=item, numeric_value=value,
        )

    def test_institution_target_tree_has_dairas_as_roots(self):
        """تفصيل مستهدف مؤسسة يُرجع الدوائر كجذور"""
        daira1 = DairaFactory()
        mudiriya1 = MudiriyaFactory(parent=daira1)
        q1 = QismFactory(parent=mudiriya1)

        daira2 = DairaFactory()
        mudiriya2 = MudiriyaFactory(parent=daira2)
        q2 = QismFactory(parent=mudiriya2)

        indicator = IndicatorFactory(
            unit_type="number", accumulation_type="sum"
        )
        self._submit(q1, indicator, 30)
        self._submit(q2, indicator, 40)

        target = TargetFactory(
            scope_unit=None, indicator=indicator,
            year=2026, target_value=200,
        )
        tree = TargetService.compute_scope_breakdown_tree(target)

        # يجب أن تظهر الدائرتان كجذور
        root_ids = {n['unit_id'] for n in tree}
        assert daira1.id in root_ids
        assert daira2.id in root_ids

        # كل جذر من نوع دائرة
        for node in tree:
            assert node['unit_type'] == 'daira'

    def test_daira_tree_contains_mudiriya_children(self):
        """عقدة الدائرة تحوي أطفالها (المديريات)"""
        daira = DairaFactory()
        mudiriya = MudiriyaFactory(parent=daira)
        qism = QismFactory(parent=mudiriya)
        indicator = IndicatorFactory(
            unit_type="number", accumulation_type="sum"
        )
        self._submit(qism, indicator, 50)

        target = TargetFactory(
            scope_unit=None, indicator=indicator,
            year=2026, target_value=100,
        )
        tree = TargetService.compute_scope_breakdown_tree(target)

        daira_node = next(n for n in tree if n['unit_id'] == daira.id)
        assert daira_node['has_children'] is True
        assert daira_node['contribution_value'] == 50

        # أطفال الدائرة = المديرية
        child_ids = {c['unit_id'] for c in daira_node['children']}
        assert mudiriya.id in child_ids

        # المديرية لديها القسم كطفل
        mudiriya_node = next(
            c for c in daira_node['children'] if c['unit_id'] == mudiriya.id
        )
        assert mudiriya_node['contribution_value'] == 50
        qism_ids = {c['unit_id'] for c in mudiriya_node['children']}
        assert qism.id in qism_ids

    def test_daira_scope_tree_roots_are_direct_children(self):
        """تفصيل مستهدف دائرة: الجذور = أبناء الدائرة المباشرة"""
        daira = DairaFactory()
        mudiriya1 = MudiriyaFactory(parent=daira)
        mudiriya2 = MudiriyaFactory(parent=daira)
        q1 = QismFactory(parent=mudiriya1)
        q2 = QismFactory(parent=mudiriya2)

        indicator = IndicatorFactory(
            unit_type="number", accumulation_type="sum"
        )
        self._submit(q1, indicator, 30)
        self._submit(q2, indicator, 40)

        target = TargetFactory(
            scope_unit=daira, indicator=indicator,
            year=2026, target_value=100,
        )
        tree = TargetService.compute_scope_breakdown_tree(target)

        root_ids = {n['unit_id'] for n in tree}
        assert mudiriya1.id in root_ids
        assert mudiriya2.id in root_ids
        # الدائرة نفسها ليست جذراً (نحن بداخلها)
        assert daira.id not in root_ids

    def test_tree_aggregation_sum_bubbles_up(self):
        """تجميع sum يصعد للأعلى عبر الشجرة بشكل صحيح"""
        daira = DairaFactory()
        mudiriya = MudiriyaFactory(parent=daira)
        q1 = QismFactory(parent=mudiriya)
        q2 = QismFactory(parent=mudiriya)

        indicator = IndicatorFactory(
            unit_type="number", accumulation_type="sum"
        )
        self._submit(q1, indicator, 25)
        self._submit(q2, indicator, 35)

        target = TargetFactory(
            scope_unit=None, indicator=indicator,
            year=2026, target_value=200,
        )
        tree = TargetService.compute_scope_breakdown_tree(target)

        daira_node = next(n for n in tree if n['unit_id'] == daira.id)
        # المجموع الكلي للدائرة = 25+35 = 60
        assert daira_node['contribution_value'] == 60

    def test_qism_target_returns_empty_tree(self):
        """مستهدف قسم يُرجع شجرة فارغة (لا تفصيل)"""
        qism = _make_supervised_qism()
        indicator = IndicatorFactory(
            unit_type="number", accumulation_type="sum"
        )
        target = TargetFactory(scope_unit=qism, indicator=indicator, year=2026)
        tree = TargetService.compute_scope_breakdown_tree(target)
        assert tree == []
