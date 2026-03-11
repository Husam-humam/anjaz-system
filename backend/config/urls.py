"""
URL configuration for Anjaz System.
"""
from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('apps.accounts.urls')),
    path('api/organization/', include('apps.organization.urls')),
    path('api/indicators/', include('apps.indicators.urls')),
    path('api/forms/', include('apps.forms.urls')),
    path('api/targets/', include('apps.targets.urls')),
    path('api/periods/', include('apps.submissions.urls_periods')),
    path('api/submissions/', include('apps.submissions.urls')),
    path('api/qualitative/', include('apps.submissions.urls_qualitative')),
    path('api/reports/', include('apps.reports.urls')),
    path('api/notifications/', include('apps.notifications.urls')),
    path('api/users/', include('apps.accounts.urls_users')),
]

if settings.DEBUG:
    try:
        import debug_toolbar
        urlpatterns = [
            path('__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns
    except ImportError:
        pass
