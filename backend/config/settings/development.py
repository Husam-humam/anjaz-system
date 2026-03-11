"""
Development settings for Anjaz System.
"""
from .base import *  # noqa: F401, F403

DEBUG = True

# Allow all hosts in development
ALLOWED_HOSTS = ['*']

# Additional development apps
INSTALLED_APPS += [  # noqa: F405
    'debug_toolbar',
]

MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')  # noqa: F405

INTERNAL_IPS = [
    '127.0.0.1',
]

# Use console email backend in development
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# CORS - allow all in development
CORS_ALLOW_ALL_ORIGINS = True

# Simplified static file storage for development
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
