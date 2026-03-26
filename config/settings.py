"""
HooYia Market — settings.py
Fichier central de configuration Django (Mode Local)
"""
from pathlib import Path
from decouple import config
from datetime import timedelta

# Racine du projet (dossier hooYia_market/)
BASE_DIR = Path(__file__).resolve().parent.parent


# ═══════════════════════════════════════════════
# SÉCURITÉ
# ═══════════════════════════════════════════════

SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0'] + config('ALLOWED_HOSTS', default='', cast=lambda v: [s.strip() for s in v.split(',') if s.strip()])

# URL de base du site — utilisée pour les liens dans les emails
# Dev  : http://localhost:8000
# Prod : https://tondomaine.com
SITE_URL = config('SITE_URL', default='https://hooyiamarket.site')


# ═══════════════════════════════════════════════
# APPLICATIONS INSTALLÉES
# ═══════════════════════════════════════════════

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'daphne',
    'django.contrib.staticfiles',

    # API REST
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_filters',

    # WebSockets & Chat temps réel
    'channels',

    # Fonctionnalités métier
    'mptt',           # Catégories en arbre
    'django_fsm',     # Statuts commande (machine à états)

    # Débogage en développement
    #'debug_toolbar',

    # Nos applications HooYia Market
    'apps.users',
    'apps.products',
    'apps.cart',
    'apps.orders',
    'apps.reviews',
    'apps.chat',
    'apps.notifications',
    'apps.audit',
]


# ═══════════════════════════════════════════════
# MIDDLEWARE
# ═══════════════════════════════════════════════

MIDDLEWARE = [
    #'debug_toolbar.middleware.DebugToolbarMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.audit.middleware.AuditLogMiddleware',
]


# ═══════════════════════════════════════════════
# URLS & ASGI
# ═══════════════════════════════════════════════

ROOT_URLCONF = 'config.urls'
ASGI_APPLICATION = 'config.asgi.application'


# ═══════════════════════════════════════════════
# TEMPLATES (HTML)
# ═══════════════════════════════════════════════

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                #'apps.cart.context_processors.cart_count',
                #'apps.notifications.context_processors.notif_count',
            ],
        },
    },
]


# ═══════════════════════════════════════════════
# BASE DE DONNÉES (PostgreSQL)
# ═══════════════════════════════════════════════

import dj_database_url as _dj_db_url

_db_url = config('DATABASE_URL', default='')
if _db_url:
    DATABASES = {'default': _dj_db_url.parse(_db_url, conn_max_age=600)}
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME':     config('DB_NAME',     default='hooYia_db'),
            'USER':     config('DB_USER',     default='postgres'),
            'PASSWORD': config('DB_PASSWORD', default='postgres'),
            'HOST':     config('DB_HOST',     default='localhost'),
            'PORT':     config('DB_PORT',     default='5432'),
        }
    }

AUTH_USER_MODEL = 'users.CustomUser'


# ═══════════════════════════════════════════════
# CACHE — En mémoire
# ═══════════════════════════════════════════════

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'hooYia-cache',
        'TIMEOUT': 300,
    }
}

SESSION_ENGINE = 'django.contrib.sessions.backends.db'


# ═══════════════════════════════════════════════
# DJANGO CHANNELS — WebSockets via Redis
# ═══════════════════════════════════════════════

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [config('REDIS_URL', default='redis://redis:6379/0')],
        },
    }
}


# ═══════════════════════════════════════════════
# DJANGO REST FRAMEWORK
# ═══════════════════════════════════════════════

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 12,
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME':    timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME':   timedelta(days=7),
    'ROTATE_REFRESH_TOKENS':    True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES':        ('Bearer',),
    'USER_ID_FIELD':            'id',
    'USER_ID_CLAIM':            'user_id',
}

AUTHENTIFICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]


# ═══════════════════════════════════════════════
# CORS & CSRF
# ═══════════════════════════════════════════════

CORS_ALLOW_ALL_ORIGINS = DEBUG  # True uniquement en dev

CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:8000',
    cast=lambda v: [s.strip() for s in v.split(',') if s.strip()]
)

CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default='http://localhost:8000',
    cast=lambda v: [s.strip() for s in v.split(',') if s.strip()]
)

# ═══════════════════════════════════════════════
# SÉCURITÉ HTTPS — Activé uniquement en prod
# ═══════════════════════════════════════════════

if not DEBUG:
    SECURE_PROXY_SSL_HEADER   = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT        = True
    SESSION_COOKIE_SECURE      = True
    CSRF_COOKIE_SECURE         = True
    SECURE_HSTS_SECONDS        = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD        = True


# ═══════════════════════════════════════════════
# EMAILS — SMTP
# ═══════════════════════════════════════════════

EMAIL_BACKEND       = config('EMAIL_BACKEND',       default='django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST          = config('EMAIL_HOST',          default='smtp.gmail.com')
EMAIL_PORT          = config('EMAIL_PORT',          default=587, cast=int)
EMAIL_USE_TLS       = config('EMAIL_USE_TLS',       default=True, cast=bool)
EMAIL_HOST_USER     = config('EMAIL_HOST_USER',     default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL  = config('DEFAULT_FROM_EMAIL',  default=f'HooYia Market <{config("EMAIL_HOST_USER", default="")}>')
ADMIN_EMAIL         = config('ADMIN_EMAIL', default=config('EMAIL_HOST_USER', default=''))  # Email qui reçoit les alertes remboursement


# ═══════════════════════════════════════════════
# FICHIERS STATIQUES & MEDIA
# ═══════════════════════════════════════════════

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'mediafiles'  # Aligné avec le volume Docker
DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'


# ═══════════════════════════════════════════════
# VALIDATION DES MOTS DE PASSE
# ═══════════════════════════════════════════════

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ═══════════════════════════════════════════════
# INTERNATIONALISATION
# ═══════════════════════════════════════════════
from django.utils.translation import gettext_lazy as _

LANGUAGE_CODE = 'fr'
TIME_ZONE = 'Africa/Douala'
USE_I18N = True
USE_L10N = True
USE_TZ = True

LANGUAGES = [
    ('fr', _('Français')),
    ('en', _('English')),
]

LOCALE_PATHS = [BASE_DIR / 'locale']


# ═══════════════════════════════════════════════
# DIVERS
# ═══════════════════════════════════════════════

INTERNAL_IPS = ['127.0.0.1']
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_REDIRECT_URL = '/'
LOGIN_URL = '/compte/connexion/'


# ═══════════════════════════════════════════════
# AVIS CLIENTS
# ═══════════════════════════════════════════════

AVIS_ACHAT_REQUIS = config('AVIS_ACHAT_REQUIS', default=False, cast=bool)


# ═══════════════════════════════════════════════
# GOOGLE OAUTH2
# ═══════════════════════════════════════════════

GOOGLE_CLIENT_ID     = config('GOOGLE_CLIENT_ID',     default='')
GOOGLE_CLIENT_SECRET = config('GOOGLE_CLIENT_SECRET', default='')
GOOGLE_REDIRECT_URI  = config('GOOGLE_REDIRECT_URI',  default='https://hooyiamarket.site/compte/google/callback/')


# ═══════════════════════════════════════════════
# PAYUNIT — Paiements Mobile Money (OM & MTN MoMo)
# ═══════════════════════════════════════════════
# Dev  : PAYUNIT_APP_TOKEN=sand_xxx + PAYUNIT_MODE=test
# Prod : PAYUNIT_APP_TOKEN=live_xxx + PAYUNIT_MODE=live
# api_user et api_password sont identiques en dev et prod.

PAYUNIT_API_USER     = config('PAYUNIT_API_USER',     default='')
PAYUNIT_API_PASSWORD = config('PAYUNIT_API_PASSWORD', default='')
PAYUNIT_APP_TOKEN    = config('PAYUNIT_APP_TOKEN',    default='')
PAYUNIT_MODE         = config('PAYUNIT_MODE',         default='test')


# ═══════════════════════════════════════════════
# CELERY — Tâches asynchrones
# ═══════════════════════════════════════════════

CELERY_BROKER_URL                         = config('REDIS_URL', default='redis://redis:6379/0')
CELERY_RESULT_BACKEND                     = config('REDIS_URL', default='redis://redis:6379/0')
CELERY_TASK_SERIALIZER                    = 'json'
CELERY_RESULT_SERIALIZER                  = 'json'
CELERY_ACCEPT_CONTENT                     = ['json']
CELERY_TIMEZONE                           = TIME_ZONE
CELERY_TASK_SOFT_TIME_LIMIT               = 300
CELERY_TASK_TIME_LIMIT                    = 360
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_ALWAYS_EAGER = config('CELERY_TASK_ALWAYS_EAGER', default=False, cast=bool)  # True en dev pour exécuter sans worker