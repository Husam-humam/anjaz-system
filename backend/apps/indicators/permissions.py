# استيراد الصلاحيات من تطبيق الهيكل التنظيمي لإعادة الاستخدام
from apps.organization.permissions import (  # noqa: F401
    IsStatisticsAdmin,
    IsStatisticsAdminOrReadOnly,
)
