"""
أمر إداري لمزامنة الهيكل التنظيمي من النظام الخارجي.

الاستخدام:
    python manage.py sync_organization_units              # مزامنة فعليّة
    python manage.py sync_organization_units --dry-run    # محاكاة فقط
    python manage.py sync_organization_units --check      # فحص الاتصال فقط
"""
from django.core.management.base import BaseCommand, CommandError

from apps.organization.integrations import (
    ExternalOrgClient,
    ExternalOrgError,
    ExternalOrgNotConfigured,
)
from apps.organization.sync_service import OrganizationSyncService


class Command(BaseCommand):
    help = 'مزامنة الهيكل التنظيمي من النظام الخارجي (مصدر الحقيقة)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='محاكاة المزامنة بدون كتابة أي تغيير في قاعدة البيانات',
        )
        parser.add_argument(
            '--check',
            action='store_true',
            help='فحص الاتصال بالنظام الخارجي فقط (بدون مزامنة)',
        )

    def handle(self, *args, **options):
        client = ExternalOrgClient()

        # 1) فحص الإعدادات
        try:
            client.assert_configured()
        except ExternalOrgNotConfigured as exc:
            raise CommandError(str(exc))

        # 2) لو طُلب فحص الاتصال فقط
        if options['check']:
            self.stdout.write(self.style.NOTICE(
                f'الاتصال بـ {client.base_url} ...'
            ))
            try:
                status = client.get_status()
            except ExternalOrgError as exc:
                raise CommandError(f'فشل الاتصال: {exc}')
            self.stdout.write(self.style.SUCCESS(
                f'الاتصال ناجح ✓ — '
                f'النظام: {status.get("status", "?")}، '
                f'إجمالي الوحدات: {status.get("total_units", "?")}'
            ))
            return

        # 3) المزامنة الفعليّة (أو dry-run)
        dry = options['dry_run']
        if dry:
            self.stdout.write(self.style.WARNING('وضع DRY-RUN — لن تُكتَب تغييرات'))

        service = OrganizationSyncService(client=client)
        try:
            report = service.sync(dry_run=dry)
        except ExternalOrgError as exc:
            raise CommandError(f'فشل المزامنة: {exc}')

        # 4) عرض التقرير
        if report.errors:
            self.stdout.write(self.style.ERROR(
                f'حدثت {len(report.errors)} أخطاء أثناء المزامنة:'
            ))
            for err in report.errors[:10]:
                self.stdout.write(f'  - {err}')
            if len(report.errors) > 10:
                self.stdout.write(f'  ... و{len(report.errors) - 10} أخطاء أخرى')

        style = self.style.SUCCESS if not report.errors else self.style.WARNING
        self.stdout.write(style(report.summary()))

        if report.skipped_unknown_type:
            self.stdout.write(self.style.WARNING(
                f'تنبيه: {report.skipped_unknown_type} وحدة تجوهلت لأن نوعها '
                f'غير مُعرَّف في خريطة الأنواع. أضفها لـ DEFAULT_UNIT_TYPE_MAP.'
            ))

        if dry:
            self.stdout.write(self.style.NOTICE(
                'هذه محاكاة فقط. شغّل بدون --dry-run لتطبيق التغييرات.'
            ))
