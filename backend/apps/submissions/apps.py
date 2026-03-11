from django.apps import AppConfig


class SubmissionsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.submissions'
    verbose_name = 'المنجزات'

    def ready(self):
        import apps.submissions.signals  # noqa: F401
