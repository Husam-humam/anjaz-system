"""
Base settings for Anjaz System.
"""
import os
from datetime import timedelta
from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Environment variables
env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ['localhost', '127.0.0.1']),
)
environ.Env.read_env(os.path.join(BASE_DIR.parent, '.env'))

SECRET_KEY = env('SECRET_KEY', default=None)
if not SECRET_KEY:
    raise ImproperlyConfigured("SECRET_KEY environment variable is required")

DEBUG = env('DEBUG')
ALLOWED_HOSTS = env('ALLOWED_HOSTS')

# Application definition
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_filters',
    'mptt',
    'channels',
]

LOCAL_APPS = [
    'apps.organization',
    'apps.accounts',
    'apps.indicators',
    'apps.forms',
    'apps.targets',
    'apps.submissions',
    'apps.reports',
    'apps.notifications',
    'apps.audit',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # فحص يومي خفيف لإنشاء الأسبوع الحالي تلقائياً
    'apps.submissions.middleware.PeriodAutoCheckMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env('DB_NAME', default='anjaz_db'),
        'USER': env('DB_USER', default='anjaz_user'),
        'PASSWORD': env('DB_PASSWORD'),
        'HOST': env('DB_HOST', default='db'),
        'PORT': env('DB_PORT', default='5432'),
    }
}

# Custom User Model
AUTH_USER_MODEL = 'accounts.User'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'ar'
TIME_ZONE = 'Asia/Baghdad'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_PAGINATION_CLASS': 'config.pagination.StandardResultsSetPagination',
    'PAGE_SIZE': 20,
    'EXCEPTION_HANDLER': 'apps.accounts.exceptions.custom_exception_handler',
    'NON_FIELD_ERRORS_KEY': 'detail',
    'DEFAULT_THROTTLE_RATES': {
        'anon': '20/minute',
        'user': '60/minute',
        # معدّل محاولات تسجيل الدخول لكل عنوان IP — قابل للضبط من .env.
        # القيمة بصيغة DRF: 'N/period' حيث period ∈ second/minute/hour/day.
        # مثلاً: '5/minute' = ٥ محاولات في الدقيقة لكل IP.
        'login': env('LOGIN_THROTTLE_RATE', default='5/minute'),
    },
}

# تفعيل/تعطيل rate limit على تسجيل الدخول — قابل للضبط من .env.
# اتركه True في الإنتاج. عطّله مؤقتاً في التطوير لو احتجت محاولات سريعة.
LOGIN_THROTTLE_ENABLED = env.bool('LOGIN_THROTTLE_ENABLED', default=True)

# Django cache — مطلوب لـ DRF throttling لتتبّع عداد IP عبر الطلبات.
# في الإنتاج: استخدم Redis. للتطوير: local memory cache كافٍ.
CACHES = {
    'default': {
        'BACKEND': env(
            'CACHE_BACKEND',
            default='django.core.cache.backends.locmem.LocMemCache',
        ),
        'LOCATION': env('CACHE_LOCATION', default='anjaz-default-cache'),
    },
}

# Simple JWT
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(
        minutes=env.int('JWT_ACCESS_TOKEN_LIFETIME_MINUTES', default=60)
    ),
    'REFRESH_TOKEN_LIFETIME': timedelta(
        days=env.int('JWT_REFRESH_TOKEN_LIFETIME_DAYS', default=7)
    ),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# CORS
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[])
CORS_ALLOW_CREDENTIALS = True

# CSRF
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=['http://localhost:3000'])

# Channels
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [env('REDIS_URL', default='redis://redis:6379/0')],
        },
    },
}

# External organization-structure system (source of truth for the org tree).
# Empty URL means the integration is disabled — the sync command will refuse to run.
EXTERNAL_ORG_API_URL = env('EXTERNAL_ORG_API_URL', default='')
EXTERNAL_ORG_API_KEY = env('EXTERNAL_ORG_API_KEY', default='')
EXTERNAL_ORG_API_TIMEOUT = env.int('EXTERNAL_ORG_API_TIMEOUT', default=15)
# Host header override: للحالات التي يصل فيها الـ backend إلى النظام الخارجي
# عبر hostname لا يقبله النظام الخارجي في ALLOWED_HOSTS (مثلاً
# host.docker.internal من داخل docker بينما النظام الخارجي يسمح فقط بـ localhost).
EXTERNAL_ORG_HOST_HEADER = env('EXTERNAL_ORG_HOST_HEADER', default='')

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
        },
        'audit': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps': {
            'handlers': ['console'],
            'level': 'WARNING',
        },
    },
}
