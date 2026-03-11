from django.db import models


class IndicatorQuerySet(models.QuerySet):
    """مجموعة استعلامات مخصصة للمؤشرات"""

    def active(self):
        """المؤشرات النشطة فقط"""
        return self.filter(is_active=True)

    def by_category(self, category_id):
        """المؤشرات حسب التصنيف"""
        return self.filter(category_id=category_id)

    def numeric(self):
        """المؤشرات الرقمية فقط (غير النصية)"""
        return self.exclude(unit_type='text')
