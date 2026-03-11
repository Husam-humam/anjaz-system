from django.apps import AppConfig


class ReportsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.reports'
    verbose_name = 'التقارير'

    def ready(self):
        import apps.reports.signals  # noqa: F401
