from django.apps import AppConfig


class TargetsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.targets'
    verbose_name = 'المستهدفات'

    def ready(self):
        import apps.targets.signals  # noqa: F401
