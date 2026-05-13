"""
أمر الإدارة التلقائية للأسابيع.
يُنفَّذ يومياً عبر cron / Windows Task Scheduler لضمان وجود الأسبوع الحالي.

الاستخدام:
    python manage.py ensure_current_period
    python manage.py ensure_current_period --verbose
"""
import sys

from django.core.management.base import BaseCommand

from apps.submissions.services import PeriodAutoService


class Command(BaseCommand):
    help = 'يضمن وجود الأسبوع الحالي ويُغلق الأسابيع المنتهية تلقائياً'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='إظهار تفاصيل إضافية',
        )

    def handle(self, *args, **options):
        # ضمان أن stdout يدعم UTF-8 (مهم على Windows مع النص العربي)
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except (AttributeError, Exception):
            pass
        verbose = options.get('verbose', False)

        result = PeriodAutoService.ensure_current_period()

        if result.get('skipped') == 'disabled':
            self.stdout.write(
                self.style.WARNING(
                    'الإدارة التلقائية معطّلة في إعدادات النظام — لم يتم أي إجراء.'
                )
            )
            return

        logical = result.get('logical_period', {})
        if result['created']:
            period = result['created']
            self.stdout.write(
                self.style.SUCCESS(
                    f'[OK] تم إنشاء الأسبوع {period.week_number}/{period.year} '
                    f'({period.start_date} → {period.end_date})'
                )
            )
            if verbose:
                self.stdout.write(f'  الموعد النهائي: {period.deadline}')
        else:
            if verbose and logical:
                self.stdout.write(
                    f'- الأسبوع الحالي موجود مسبقاً: '
                    f'{logical.get("week_number")}/{logical.get("year")}'
                )

        closed_count = len(result.get('closed', []))
        if closed_count:
            self.stdout.write(
                self.style.SUCCESS(
                    f'[OK] تم إغلاق {closed_count} فترة منتهية'
                )
            )
            if verbose:
                for period_id in result['closed']:
                    self.stdout.write(f'  - فترة #{period_id}')
        elif verbose:
            self.stdout.write('- لا توجد فترات منتهية للإغلاق')
