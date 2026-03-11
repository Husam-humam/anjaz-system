from django.apps import AppConfig


class OrganizationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.organization'
    verbose_name = 'الهيكل التنظيمي'

    def ready(self):
        import apps.organization.signals  # noqa: F401
