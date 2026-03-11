"""
استعلامات مخصصة لتطبيق الحسابات.
"""
from django.db import models


class UserQuerySet(models.QuerySet):
    """استعلامات مخصصة لنموذج المستخدم"""

    def active(self):
        """المستخدمون النشطون فقط"""
        return self.filter(is_active=True)

    def by_role(self, role):
        """تصفية حسب الدور"""
        return self.filter(role=role)

    def by_unit(self, unit_id):
        """تصفية حسب الوحدة التنظيمية"""
        return self.filter(unit_id=unit_id)

    def with_unit(self):
        """تحميل الوحدة التنظيمية مع المستخدم"""
        return self.select_related('unit')
