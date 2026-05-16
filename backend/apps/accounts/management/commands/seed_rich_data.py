"""
أمر إنشاء بيانات حقيقية شاملة للنظام — يبني هيكلاً تنظيمياً واقعياً
مع مؤشرات وقوالب وفترات أسبوعية ومنجزات ومستهدفات.

يستخدم البيانات الموجودة ويضيف إليها دون تكرار.

الاستخدام:
    python manage.py seed_rich_data
    python manage.py seed_rich_data --weeks 12  # عدد الأسابيع لإنشاء منجزات لها
"""
import datetime
import random
import sys

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User, UserRole
from apps.forms.models import FormTemplate, FormTemplateItem
from apps.indicators.models import Indicator, IndicatorCategory
from apps.organization.models import OrganizationUnit
from apps.submissions.models import (
    SubmissionAnswer,
    SystemConfiguration,
    WeeklyPeriod,
    WeeklySubmission,
)
from apps.submissions.services import PeriodAutoService
from apps.targets.models import Target


# ═══════════════════════════════════════════════════════════
# البيانات المرجعية (يمكن تعديلها)
# ═══════════════════════════════════════════════════════════

ORGANIZATION_DATA = [
    {
        'code': 'ADMIN_AFFAIRS',
        'name': 'دائرة الشؤون الإدارية',
        'unit_type': 'daira',
        'mudiriyas': [
            {
                'code': 'HR',
                'name': 'مديرية الموارد البشرية',
                'qisms': [
                    ('EMP', 'قسم التوظيف', 'regular'),
                    ('TRAIN', 'قسم التدريب', 'regular'),
                    ('PAYROLL', 'قسم الرواتب', 'regular'),
                    ('PLAN_HR', 'قسم تخطيط الموارد', 'planning'),
                ],
            },
            {
                'code': 'ADMIN_SERV',
                'name': 'مديرية الخدمات الإدارية',
                'qisms': [
                    ('SERV', 'قسم الخدمات', 'regular'),
                    ('MAIL', 'قسم البريد والمراسلات', 'regular'),
                    ('ARCH', 'قسم الأرشيف', 'regular'),
                ],
            },
        ],
    },
    {
        'code': 'FIN',
        'name': 'دائرة المالية',
        'unit_type': 'daira',
        'mudiriyas': [
            {
                'code': 'BUDGET',
                'name': 'مديرية الميزانية',
                'qisms': [
                    ('BUDGET_PLAN', 'قسم تخطيط الميزانية', 'regular'),
                    ('BUDGET_REV', 'قسم مراجعة الميزانية', 'regular'),
                ],
            },
            {
                'code': 'ACCOUNTS',
                'name': 'مديرية المحاسبة',
                'qisms': [
                    ('ACC', 'قسم المحاسبة العامة', 'regular'),
                    ('PROCURE', 'قسم المشتريات', 'regular'),
                    ('AUDIT_INT', 'قسم التدقيق الداخلي', 'regular'),
                ],
            },
        ],
    },
    {
        'code': 'IT',
        'name': 'دائرة تقنية المعلومات',
        'unit_type': 'daira',
        'mudiriyas': [
            {
                'code': 'SYS',
                'name': 'مديرية الأنظمة',
                'qisms': [
                    ('DEV', 'قسم التطوير', 'regular'),
                    ('SUPPORT', 'قسم الدعم الفني', 'regular'),
                    ('OPS', 'قسم العمليات والبنية التحتية', 'regular'),
                ],
            },
            {
                'code': 'SEC',
                'name': 'مديرية الأمن السيبراني',
                'qisms': [
                    ('CYBER', 'قسم حماية الشبكات', 'regular'),
                    ('AUDIT_SEC', 'قسم التدقيق الأمني', 'regular'),
                ],
            },
        ],
    },
]


INDICATORS_DATA = [
    # إداري
    ('عدد القرارات الإدارية الصادرة', 'number', 'sum', 'إداري', ''),
    ('عدد المراسلات الواردة', 'number', 'sum', 'إداري', ''),
    ('عدد المراسلات الصادرة', 'number', 'sum', 'إداري', ''),
    ('نسبة الحضور اليومي', 'percentage', 'average', 'إداري', ''),
    ('عدد الموظفين النشطين', 'number', 'last_value', 'إداري', ''),
    ('أبرز الإنجازات الأسبوعية', 'text', 'last_value', 'إداري', ''),  # نوعي
    # مالي
    ('المصروفات الشهرية', 'number', 'sum', 'مالي', 'د.ع'),
    ('نسبة تنفيذ الميزانية', 'percentage', 'average', 'مالي', ''),
    ('عدد فواتير المشتريات', 'number', 'sum', 'مالي', ''),
    # فني
    ('عدد التقارير الفنية', 'number', 'sum', 'فني', ''),
    ('ساعات الصيانة', 'hours', 'sum', 'فني', 'ساعة'),
    ('عدد الأعطال المُعالجة', 'number', 'sum', 'فني', ''),
    ('وصف إنجاز فني مميّز', 'text', 'last_value', 'فني', ''),  # نوعي
    # أمني
    ('عدد المخاطر المرصودة', 'number', 'sum', 'أمني', ''),
    ('نسبة تغطية التدقيق', 'percentage', 'average', 'أمني', ''),
    # رقابي
    ('عدد عمليات التدقيق المنجزة', 'number', 'sum', 'رقابي', ''),
    ('عدد الملاحظات المعالجة', 'number', 'sum', 'رقابي', ''),
]

# عيّنات نصوص واقعية للمنجزات النوعية (الـ seed يختار منها عشوائياً)
QUALITATIVE_SAMPLES = [
    'إنجاز مشروع إعادة هيكلة قاعدة البيانات بنجاح خلال الأسبوع، مما سمح بتحسين أداء النظام بنسبة 35% وتقليل زمن الاستجابة للاستعلامات الكبيرة.',
    'توقيع مذكّرة تفاهم مع جامعة بغداد لتطوير برنامج تدريبي متخصّص للموظفين، يبدأ تنفيذه في الشهر القادم ويستفيد منه 80 موظفاً.',
    'افتتاح مكتب فرعي جديد في المحافظة الجنوبية لتقديم الخدمات بشكل أقرب للمواطنين، مع تخصيص فريق من 12 موظفاً.',
    'إطلاق بوابة إلكترونية موحّدة لاستقبال الشكاوى وتتبعها، حيث تمّ استقبال 240 شكوى في الأسبوع الأول وحلّ 180 منها.',
    'تنظيم ورشة عمل لتدريب 45 موظفاً على نظام الأرشفة الإلكتروني الجديد، مع تحقيق نسبة رضا بلغت 92% من المشاركين.',
    'الانتهاء من مراجعة وتصديق الحسابات الختامية للسنة المالية الماضية قبل الموعد المحدّد بأسبوعين كاملين.',
    'تحديث كامل لأنظمة الحماية على مستوى الشبكة المؤسسية، مع تطبيق سياسات أمن جديدة وتفعيل نظام الرصد على مدار الساعة.',
    'إنجاز تقرير التقييم الربع سنوي حول أداء الأقسام الفنية، تضمّن 15 توصية تطويرية مُوزّعة على الإدارات المختصّة.',
    'إعادة تنظيم ترتيب الملفات في الأرشيف الإداري وتحويل 1,200 ملف إلى النظام الإلكتروني الجديد خلال هذا الأسبوع.',
    'تقديم ورقة علمية متخصّصة في المؤتمر الوطني للإدارة العامة، والتي نالت استحسان اللجنة العلمية.',
]


class Command(BaseCommand):
    help = 'إنشاء بيانات حقيقية شاملة للنظام (أقسام، مؤشرات، قوالب، فترات، منجزات، مستهدفات)'

    _admin_cache = None

    def _get_admin_cached(self):
        if self._admin_cache is None:
            self._admin_cache = User.objects.filter(
                role=UserRole.STATISTICS_ADMIN
            ).first()
        return self._admin_cache

    def add_arguments(self, parser):
        parser.add_argument(
            '--weeks',
            type=int,
            default=8,
            help='عدد الأسابيع الماضية لإنشاء منجزات لها (الافتراضي 8)',
        )

    def handle(self, *args, **options):
        # ضمان أن stdout يدعم UTF-8
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

        weeks = options.get('weeks', 8)

        self.stdout.write(self.style.MIGRATE_HEADING(
            '═══ بدء إنشاء البيانات الحقيقية ═══'
        ))

        self._ensure_system_config()
        self._ensure_categories()
        self._build_organization()
        admin = self._ensure_admin_user()
        self._build_indicators(admin)
        self._build_form_templates(admin)
        periods = self._build_periods(weeks)
        self._build_submissions(periods)
        self._build_targets(admin)

        self.stdout.write(self.style.SUCCESS(
            '\n═══ اكتمل إنشاء البيانات بنجاح ═══'
        ))
        self._print_summary()

    # ──────────────────────────────────────────
    # الخطوات
    # ──────────────────────────────────────────

    def _ensure_system_config(self):
        config = SystemConfiguration.load()
        self.stdout.write(
            f'[1/7] إعدادات النظام: بداية الأسبوع = '
            f'{config.get_week_start_day_display()}, '
            f'auto_create = {config.auto_create_enabled}'
        )

    def _ensure_categories(self):
        """إنشاء تصنيفات المؤشرات إن لم تكن موجودة"""
        self.stdout.write('[2/7] تصنيفات المؤشرات...')
        for name in ['إداري', 'مالي', 'فني', 'أمني', 'رقابي']:
            obj, created = IndicatorCategory.objects.get_or_create(name=name)
            if created:
                self.stdout.write(f'  + {name}')

    @transaction.atomic
    def _build_organization(self):
        """بناء الهيكل التنظيمي الكامل"""
        self.stdout.write('[3/7] الهيكل التنظيمي...')
        created_count = 0

        # تأكد من قسم الإحصاء (إن لم يكن موجوداً)
        stat_qism, created = OrganizationUnit.objects.get_or_create(
            code='STAT',
            defaults={
                'name': 'قسم الإحصاء',
                'unit_type': 'qism',

            }
        )
        if created:
            created_count += 1

        for daira_data in ORGANIZATION_DATA:
            daira, created = OrganizationUnit.objects.get_or_create(
                code=daira_data['code'],
                defaults={
                    'name': daira_data['name'],
                    'unit_type': 'daira',

                },
            )
            if created:
                created_count += 1
                self.stdout.write(f'  + دائرة: {daira.name}')

            for mud_data in daira_data.get('mudiriyas', []):
                mudiriya, created = OrganizationUnit.objects.get_or_create(
                    code=mud_data['code'],
                    defaults={
                        'name': mud_data['name'],
                        'unit_type': 'mudiriya',

                        'parent': daira,
                    },
                )
                if created:
                    created_count += 1
                    self.stdout.write(f'    + مديرية: {mudiriya.name}')

                for q_code, q_name, q_role in mud_data.get('qisms', []):
                    # ملاحظة: q_role لم يَعُد محفوظاً على الوحدة. التخصيصات
                    # (planning/regular) تُنشأ منفصلاً عبر PlanningAssignment.
                    qism, created = OrganizationUnit.objects.get_or_create(
                        code=q_code,
                        defaults={
                            'name': q_name,
                            'unit_type': 'qism',
                            'parent': mudiriya,
                        },
                    )
                    if created:
                        created_count += 1

        self.stdout.write(f'  تم إنشاء {created_count} وحدة جديدة')

    def _build_indicators(self, admin):
        """إنشاء المؤشرات الأساسية"""
        self.stdout.write('[4/7] المؤشرات...')
        created_count = 0
        for name, unit_type, acc_type, cat_name, unit_label in INDICATORS_DATA:
            category = IndicatorCategory.objects.filter(name=cat_name).first()
            ind, created = Indicator.objects.get_or_create(
                name=name,
                defaults={
                    'unit_type': unit_type,
                    'accumulation_type': acc_type,
                    'category': category,
                    'unit_label': unit_label,
                    'is_active': True,
                    'created_by': admin,
                },
            )
            if created:
                created_count += 1
        self.stdout.write(f'  تم إنشاء {created_count} مؤشر جديد')

    def _ensure_admin_user(self):
        admin = User.objects.filter(role=UserRole.STATISTICS_ADMIN).first()
        if not admin:
            # admin role لا يحتاج وحدة بعد Phase F
            admin = User(
                username='admin',
                full_name='مدير النظام',
                role='statistics_admin',
                unit=None,
                is_staff=True,
                is_superuser=True,
            )
            admin.set_password('Admin@2026secure')
            admin.save()
            self.stdout.write('  + admin')
        return admin

    @transaction.atomic
    def _build_form_templates(self, admin):
        """إنشاء قالب معتمد لكل قسم عادي"""
        self.stdout.write('[5/7] قوالب الاستمارات...')
        regular_qisms = OrganizationUnit.objects.filter(
            unit_type='qism', is_active=True,
            supervisor_link__isnull=False,
        )
        created_count = 0

        # توزيع المؤشرات على الأقسام حسب التصنيف (اختيار 3-5 مؤشرات لكل قسم)
        indicators_by_category = {}
        for cat in IndicatorCategory.objects.all():
            indicators_by_category[cat.name] = list(
                Indicator.objects.filter(category=cat, is_active=True)
            )

        for qism in regular_qisms:
            existing = FormTemplate.objects.filter(qism=qism).exists()
            if existing:
                continue

            # تحديد تصنيفات المؤشرات المناسبة للقسم حسب اسمه
            relevant_cats = self._choose_categories_for_qism(qism)

            # جمع مؤشرات من تلك التصنيفات (حتى 3 لكل تصنيف)
            chosen_indicators = []
            for cat_name in relevant_cats:
                inds = indicators_by_category.get(cat_name, [])
                # فضّل الرقمية أولاً ثم أضف واحد نصي إن وجد
                numeric = [i for i in inds if i.unit_type != 'text']
                textual = [i for i in inds if i.unit_type == 'text']
                chosen_indicators.extend(numeric[:3])
                if textual:
                    chosen_indicators.append(textual[0])

            if not chosen_indicators:
                # fallback: أي 3 مؤشرات رقمية
                chosen_indicators = list(
                    Indicator.objects.filter(
                        is_active=True, unit_type__in=['number', 'hours', 'percentage']
                    )[:3]
                )

            if not chosen_indicators:
                continue

            template = FormTemplate.objects.create(
                qism=qism,
                version=1,
                status='approved',
                effective_from_year=2026,
                effective_from_week=1,
                created_by=admin,
                approved_by=admin,
                approved_at=timezone.now(),
                notes='قالب أوّلي تجريبي',
            )
            for idx, ind in enumerate(chosen_indicators):
                FormTemplateItem.objects.create(
                    form_template=template,
                    indicator=ind,
                    is_mandatory=(idx < 2),  # الأول والثاني إلزاميين
                    display_order=idx + 1,
                )
            created_count += 1

        self.stdout.write(f'  تم إنشاء {created_count} قالب جديد')

    def _choose_categories_for_qism(self, qism):
        """يختار تصنيفات مناسبة بناءً على اسم/رمز القسم"""
        code = qism.code.upper()
        name = qism.name

        mapping = [
            (['EMP', 'TRAIN', 'PAYROLL', 'SERV', 'MAIL', 'ARCH'], ['إداري']),
            (['BUDGET', 'ACC', 'PROCURE'], ['مالي', 'إداري']),
            (['DEV', 'SUPPORT', 'OPS'], ['فني', 'إداري']),
            (['CYBER', 'AUDIT_SEC'], ['أمني', 'فني']),
            (['AUDIT_INT'], ['رقابي', 'مالي']),
        ]
        for codes, cats in mapping:
            if any(c in code for c in codes):
                return cats
        return ['إداري']

    @transaction.atomic
    def _build_periods(self, weeks_back):
        """إنشاء الفترات الأسبوعية للأسابيع الماضية + الحالية"""
        self.stdout.write(f'[6/7] الفترات الأسبوعية ({weeks_back} أسابيع ماضية)...')
        config = SystemConfiguration.load()
        today = timezone.localdate()

        created_periods = []
        for weeks_ago in range(weeks_back, -1, -1):
            target_date = today - datetime.timedelta(days=weeks_ago * 7)
            year, week_num, week_start, week_end = (
                PeriodAutoService.compute_week_number_and_year(
                    target_date, config.week_start_day
                )
            )
            existing = WeeklyPeriod.objects.filter(
                year=year, week_number=week_num
            ).first()
            if existing:
                created_periods.append(existing)
                continue

            deadline = PeriodAutoService.compute_deadline(week_end, config)
            # الأسابيع الماضية تُنشأ مغلقة، الحالية مفتوحة
            is_past = week_end < today
            period = WeeklyPeriod.objects.create(
                year=year,
                week_number=week_num,
                start_date=week_start,
                end_date=week_end,
                deadline=deadline,
                status='closed' if is_past else 'open',
                created_by=None,
            )
            created_periods.append(period)

        self.stdout.write(f'  إجمالي الفترات المتوفّرة: {len(created_periods)}')
        return created_periods

    @transaction.atomic
    def _build_submissions(self, periods):
        """إنشاء منجزات واقعية للأقسام في كل فترة"""
        self.stdout.write('[7/7] المنجزات والإجابات...')
        regular_qisms = OrganizationUnit.objects.filter(
            unit_type='qism', is_active=True,
            supervisor_link__isnull=False,
        )

        created_submissions = 0
        created_answers = 0

        for qism in regular_qisms:
            template = FormTemplate.objects.filter(
                qism=qism, status='approved'
            ).first()
            if not template:
                continue
            items = list(template.items.select_related('indicator').all())
            if not items:
                continue

            # seed deterministic لكل قسم لتوليد أرقام مختلفة لكن ثابتة
            rng = random.Random(hash(qism.code) % 10_000)

            for period in periods:
                existing = WeeklySubmission.objects.filter(
                    qism=qism, weekly_period=period
                ).first()
                if existing:
                    continue

                # 85% من الفترات: المنجز معتمد بقيم عشوائية واقعية
                # 10%: مسودة أو مُرسل
                # 5%: متأخر
                rand = rng.random()
                if rand < 0.85:
                    sub_status = 'approved'
                elif rand < 0.95:
                    sub_status = 'submitted'
                else:
                    sub_status = 'late'

                submission = WeeklySubmission.objects.create(
                    qism=qism,
                    weekly_period=period,
                    form_template=template,
                    status=sub_status,
                    submitted_at=(
                        timezone.now() if sub_status != 'late' else None
                    ),
                )
                created_submissions += 1

                # لا ننشئ إجابات للمتأخر
                if sub_status == 'late':
                    continue

                for item in items:
                    ind = item.indicator

                    # المؤشرات النصية → منجز نوعي معتمد (بنسبة ~60%)
                    if ind.unit_type == 'text':
                        if rng.random() < 0.6:
                            details = rng.choice(QUALITATIVE_SAMPLES)
                            SubmissionAnswer.objects.create(
                                submission=submission,
                                form_item=item,
                                is_qualitative=True,
                                qualitative_details=details,
                                qualitative_status='approved'
                                    if sub_status == 'approved' else 'pending_statistics',
                                qualitative_approved_by=(
                                    self._get_admin_cached()
                                    if sub_status == 'approved' else None
                                ),
                                qualitative_approved_at=(
                                    timezone.now() if sub_status == 'approved' else None
                                ),
                            )
                            created_answers += 1
                        continue

                    # توليد قيمة واقعية حسب نوع المؤشر الرقمي
                    if ind.unit_type == 'percentage':
                        value = round(rng.uniform(60, 100), 1)
                    elif ind.unit_type == 'hours':
                        value = rng.randint(5, 40)
                    elif ind.accumulation_type == 'last_value':
                        value = rng.randint(20, 150)
                    else:
                        value = rng.randint(5, 50)

                    SubmissionAnswer.objects.create(
                        submission=submission,
                        form_item=item,
                        numeric_value=value,
                    )
                    created_answers += 1

        self.stdout.write(
            f'  تم إنشاء {created_submissions} منجز و '
            f'{created_answers} إجابة'
        )

    @transaction.atomic
    def _build_targets(self, admin):
        """إنشاء مستهدفات على كل المستويات"""
        self.stdout.write('[+] المستهدفات الهرمية...')
        current_year = timezone.now().year
        created_count = 0

        # مؤشرات رقمية فقط (المستهدفات)
        numeric_indicators = list(
            Indicator.objects.filter(is_active=True).exclude(unit_type='text')
        )
        if not numeric_indicators:
            return

        # 1) مستهدفات على مستوى المؤسسة (5 مؤشرات رئيسية)
        main_indicators = [
            i for i in numeric_indicators
            if i.accumulation_type != 'last_value'
        ][:5]

        for ind in main_indicators:
            if Target.objects.filter(
                scope_unit__isnull=True, indicator=ind, year=current_year
            ).exists():
                continue
            # قيمة مستهدف = متوسط × عدد أقسام × أسابيع
            if ind.accumulation_type == 'sum':
                target_value = random.randint(500, 3000)
            else:
                target_value = random.randint(80, 95)  # نسبة مئوية
            Target.objects.create(
                scope_unit=None,
                indicator=ind,
                year=current_year,
                target_value=target_value,
                set_by=admin,
                notes='مستهدف استراتيجي على مستوى المؤسسة',
            )
            created_count += 1

        # 2) مستهدفات على مستوى الدوائر
        dairas = OrganizationUnit.objects.filter(unit_type='daira', is_active=True)
        for daira in dairas:
            # 3 مؤشرات لكل دائرة
            chosen = random.sample(
                [i for i in numeric_indicators if i.accumulation_type != 'last_value'],
                min(3, len(numeric_indicators)),
            )
            for ind in chosen:
                if Target.objects.filter(
                    scope_unit=daira, indicator=ind, year=current_year
                ).exists():
                    continue
                if ind.accumulation_type == 'sum':
                    target_value = random.randint(200, 1000)
                else:
                    target_value = random.randint(75, 95)
                Target.objects.create(
                    scope_unit=daira,
                    indicator=ind,
                    year=current_year,
                    target_value=target_value,
                    set_by=admin,
                )
                created_count += 1

        # 3) مستهدفات على مستوى المديريات (اختياري لبعض المديريات)
        mudiriyas = list(OrganizationUnit.objects.filter(
            unit_type='mudiriya', is_active=True
        )[:4])
        for mud in mudiriyas:
            chosen = random.sample(
                [i for i in numeric_indicators if i.accumulation_type != 'last_value'],
                min(2, len(numeric_indicators)),
            )
            for ind in chosen:
                if Target.objects.filter(
                    scope_unit=mud, indicator=ind, year=current_year
                ).exists():
                    continue
                if ind.accumulation_type == 'sum':
                    target_value = random.randint(100, 500)
                else:
                    target_value = random.randint(75, 95)
                Target.objects.create(
                    scope_unit=mud,
                    indicator=ind,
                    year=current_year,
                    target_value=target_value,
                    set_by=admin,
                )
                created_count += 1

        self.stdout.write(f'  تم إنشاء {created_count} مستهدف جديد')

    def _print_summary(self):
        self.stdout.write('')
        self.stdout.write('── ملخص البيانات ──')
        self.stdout.write(
            f'  الدوائر: {OrganizationUnit.objects.filter(unit_type="daira").count()}'
        )
        self.stdout.write(
            f'  المديريات: {OrganizationUnit.objects.filter(unit_type="mudiriya").count()}'
        )
        self.stdout.write(
            f'  الأقسام العادية: '
            f'{OrganizationUnit.objects.filter(unit_type="qism", supervisor_link__isnull=False).count()}'
        )
        self.stdout.write(
            f'  المؤشرات: {Indicator.objects.filter(is_active=True).count()}'
        )
        self.stdout.write(
            f'  القوالب المعتمدة: {FormTemplate.objects.filter(status="approved").count()}'
        )
        self.stdout.write(
            f'  الفترات الأسبوعية: {WeeklyPeriod.objects.count()}'
        )
        self.stdout.write(
            f'  المنجزات: {WeeklySubmission.objects.count()}'
        )
        self.stdout.write(
            f'  الإجابات: {SubmissionAnswer.objects.count()}'
        )
        self.stdout.write(
            f'  المستهدفات: {Target.objects.count()}'
        )
