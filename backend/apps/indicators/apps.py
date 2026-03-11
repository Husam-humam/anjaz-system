from django.apps import AppConfig


class IndicatorsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.indicators'
    verbose_name = 'المؤشرات'

    def ready(self):
        import apps.indicators.signals  # noqa: F401
