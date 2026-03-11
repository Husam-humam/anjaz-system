"""
اختبارات نماذج تطبيق التقارير.
تطبيق التقارير لا يحتوي على نماذج بيانات خاصة — يبني تقاريره من بيانات التطبيقات الأخرى.
"""
import pytest


@pytest.mark.django_db
class TestReportsNoModels:
    """تطبيق التقارير لا يملك نماذج بيانات"""

    def test_reports_app_has_no_custom_models(self):
        """التأكد من أن تطبيق التقارير لا يحتوي على نماذج مسجلة"""
        from django.apps import apps
        report_models = apps.get_app_config('reports').get_models()
        assert list(report_models) == []
