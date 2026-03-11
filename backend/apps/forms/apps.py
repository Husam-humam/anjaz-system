from django.apps import AppConfig


class FormsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.forms'
    verbose_name = 'الاستمارات'

    def ready(self):
        import apps.forms.signals  # noqa: F401
