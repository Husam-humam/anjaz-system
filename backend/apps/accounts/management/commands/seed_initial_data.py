"""
أمر لتهيئة البيانات الأولية للنظام
"""
import os

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from apps.indicators.models import IndicatorCategory
from apps.organization.models import OrganizationUnit

User = get_user_model()


class Command(BaseCommand):
    help = 'تهيئة البيانات الأولية لنظام أنجز'

    def add_arguments(self, parser):
        parser.add_argument(
            '--with-sample',
            action='store_true',
            help='إنشاء بيانات تجريبية للتطوير',
        )

    def handle(self, *args, **options):
        self.stdout.write('جارٍ تهيئة البيانات الأولية...')

        # 1. إنشاء تصنيفات المؤشرات
        categories = ['إداري', 'مالي', 'فني', 'أمني', 'رقابي']
        for cat_name in categories:
            obj, created = IndicatorCategory.objects.get_or_create(name=cat_name)
            if created:
                self.stdout.write(f'  ✓ تم إنشاء تصنيف: {cat_name}')

        # 2. إنشاء الهيكل التنظيمي الأساسي (قسم الإحصاء)
        stat_qism, created = OrganizationUnit.objects.get_or_create(
            code='STAT',
            defaults={
                'name': 'قسم الإحصاء',
                'unit_type': 'qism',
                'qism_role': 'statistics',
            }
        )
        if created:
            self.stdout.write('  ✓ تم إنشاء قسم الإحصاء')

        # 3. إنشاء مستخدم مدير الإحصاء
        admin_username = os.environ.get('ADMIN_USERNAME', 'admin')
        admin_password = os.environ.get('ADMIN_PASSWORD', 'admin123456')
        admin_full_name = os.environ.get('ADMIN_FULL_NAME', 'مدير النظام')

        if not User.objects.filter(username=admin_username).exists():
            admin = User.objects.create_superuser(
                username=admin_username,
                password=admin_password,
                full_name=admin_full_name,
                role='statistics_admin',
                unit=stat_qism,
            )
            self.stdout.write(f'  ✓ تم إنشاء مدير النظام: {admin_username}')
        else:
            self.stdout.write(f'  - مدير النظام موجود مسبقاً: {admin_username}')

        # 4. بيانات تجريبية (اختياري)
        if options['with_sample']:
            self._create_sample_data()

        self.stdout.write(self.style.SUCCESS('✓ تمت تهيئة البيانات الأولية بنجاح'))

    def _create_sample_data(self):
        """إنشاء بيانات تجريبية"""
        self.stdout.write('جارٍ إنشاء البيانات التجريبية...')

        # دائرة الشؤون الإدارية
        daira_admin, _ = OrganizationUnit.objects.get_or_create(
            code='ADMIN',
            defaults={
                'name': 'دائرة الشؤون الإدارية',
                'unit_type': 'daira',
                'qism_role': 'regular',
            }
        )

        # مديرية الموارد البشرية
        mudiriya_hr, _ = OrganizationUnit.objects.get_or_create(
            code='HR',
            defaults={
                'name': 'مديرية الموارد البشرية',
                'unit_type': 'mudiriya',
                'qism_role': 'regular',
                'parent': daira_admin,
            }
        )

        # أقسام تحت مديرية الموارد البشرية
        sample_qisms = [
            ('EMP', 'قسم التوظيف', 'regular'),
            ('TRAIN', 'قسم التدريب', 'regular'),
            ('PLAN_HR', 'قسم التخطيط والمتابعة', 'planning'),
        ]
        for code, name, role in sample_qisms:
            OrganizationUnit.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'unit_type': 'qism',
                    'qism_role': role,
                    'parent': mudiriya_hr,
                }
            )
            self.stdout.write(f'  ✓ تم إنشاء: {name}')

        # مديرية تقنية المعلومات (مستقلة)
        mudiriya_it, _ = OrganizationUnit.objects.get_or_create(
            code='IT',
            defaults={
                'name': 'مديرية تقنية المعلومات',
                'unit_type': 'mudiriya',
                'qism_role': 'regular',
            }
        )

        it_qisms = [
            ('DEV', 'قسم التطوير', 'regular'),
            ('SUPPORT', 'قسم الدعم الفني', 'regular'),
            ('PLAN_IT', 'قسم تخطيط المتابعة', 'planning'),
        ]
        for code, name, role in it_qisms:
            OrganizationUnit.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'unit_type': 'qism',
                    'qism_role': role,
                    'parent': mudiriya_it,
                }
            )
            self.stdout.write(f'  ✓ تم إنشاء: {name}')

        # إنشاء مستخدمين تجريبيين
        planning_unit = OrganizationUnit.objects.filter(code='PLAN_HR').first()
        if planning_unit and not User.objects.filter(username='planner1').exists():
            User.objects.create_user(
                username='planner1',
                password='planner123',
                full_name='أحمد المخطط',
                role='planning_section',
                unit=planning_unit,
            )
            self.stdout.write('  ✓ تم إنشاء مستخدم قسم التخطيط: planner1')

        emp_unit = OrganizationUnit.objects.filter(code='EMP').first()
        if emp_unit and not User.objects.filter(username='manager1').exists():
            User.objects.create_user(
                username='manager1',
                password='manager123',
                full_name='محمد المدير',
                role='section_manager',
                unit=emp_unit,
            )
            self.stdout.write('  ✓ تم إنشاء مدير قسم: manager1')

        self.stdout.write(self.style.SUCCESS('  ✓ تم إنشاء البيانات التجريبية'))
