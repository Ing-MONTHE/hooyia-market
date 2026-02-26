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

# Clé secrète lue depuis .env (jamais en dur dans le code)
SECRET_KEY = config('SECRET_KEY')

# True en local → affiche les erreurs détaillées
DEBUG = config('DEBUG', default=True, cast=bool)

# Hôtes autorisés à accéder au site
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0'] + config('ALLOWED_HOSTS', default='', cast=lambda v: [s.strip() for s in v.split(',') if s.strip()])


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
# Couches qui traitent chaque requête HTTP dans l'ordre
# ═══════════════════════════════════════════════

MIDDLEWARE = [
    #'debug_toolbar.middleware.DebugToolbarMiddleware', # Barre debug (dev)
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Servir les fichiers statiques en prod
    'corsheaders.middleware.CorsMiddleware',           # CORS pour les appels JS
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.audit.middleware.AuditLogMiddleware',        # Log automatique des actions
]


# ═══════════════════════════════════════════════
# URLS & WSGI / ASGI
# ═══════════════════════════════════════════════

ROOT_URLCONF = 'config.urls'

# ASGI = Daphne gère HTTP + WebSocket
ASGI_APPLICATION = 'config.asgi.application'

# ═══════════════════════════════════════════════
# TEMPLATES (HTML)
# ═══════════════════════════════════════════════

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',

        # Django cherche les templates dans ce dossier global
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                # Injecte le nombre d'articles du panier dans tous les templates
                #'apps.cart.context_processors.cart_count',
                # Injecte le nombre de notifications non lues
                #'apps.notifications.context_processors.notif_count',
            ],
        },
    },
]


# ═══════════════════════════════════════════════
# BASE DE DONNÉES (PostgreSQL)
# ═══════════════════════════════════════════════

# Supporte DATABASE_URL (Render) ou config individuelle (local)
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

# Modèle utilisateur personnalisé (on le créera dans apps/users/)
AUTH_USER_MODEL = 'users.CustomUser'


# ═══════════════════════════════════════════════

# ═══════════════════════════════════════════════
# CACHE — En mémoire (pas de Redis)
# ═══════════════════════════════════════════════

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'hooYia-cache',
        'TIMEOUT': 300,
    }
}

# Sessions stockées en base de données PostgreSQL
SESSION_ENGINE = 'django.contrib.sessions.backends.db'


# ═══════════════════════════════════════════════
# DJANGO CHANNELS — WebSockets (Chat + Notifications)
# InMemoryChannelLayer : fonctionne sans Redis
# Limitation : ne supporte pas multi-process (ok sur Render free tier)
# ═══════════════════════════════════════════════

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    }
}


# DJANGO REST FRAMEWORK
# ═══════════════════════════════════════════════

REST_FRAMEWORK = {
    # Authentification JWT + Session Django (pour les pages HTML)
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    # Par défaut : lecture publique, écriture authentifiée
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    # Filtres activés sur tous les ViewSets
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    # Pagination : 12 produits par page
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 12,
}

# Configuration des tokens JWT
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME':  timedelta(minutes=60),  # Token valide 1h
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),       # Refresh valide 7 jours
    'ROTATE_REFRESH_TOKENS':  True,                    # Nouveau refresh à chaque usage
    'BLACKLIST_AFTER_ROTATION': True,                  # Invalide l'ancien refresh
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

# Dis a SimpleJWT d'utiliser l'email
AUTHENTIFICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]


# ═══════════════════════════════════════════════
# CORS — Autorise JavaScript à appeler l'API
# ═══════════════════════════════════════════════

# En local, on autorise toutes les origines (uniquement en développement)
CORS_ALLOW_ALL_ORIGINS = True


# ═══════════════════════════════════════════════
# EMAILS — Console en local (affiche dans le terminal)
# Pour utiliser SMTP réel : définir EMAIL_BACKEND dans .env
# ═══════════════════════════════════════════════

EMAIL_BACKEND   = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST      = config('EMAIL_HOST',      default='smtp.gmail.com')
EMAIL_PORT      = config('EMAIL_PORT',      default=587, cast=int)
EMAIL_USE_TLS   = config('EMAIL_USE_TLS',   default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL  = config('DEFAULT_FROM_EMAIL', default=f'HooYia Market <{config("EMAIL_HOST_USER", default="")}>')


# ═══════════════════════════════════════════════
# FICHIERS STATIQUES & MEDIA
# ═══════════════════════════════════════════════

STATIC_URL = '/static/'
# Django cherche les fichiers statiques dans ce dossier
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
# Les images uploadées (photos produits) sont stockées ici
MEDIA_ROOT = BASE_DIR / 'media'


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

LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Africa/Douala'
USE_I18N = True
USE_TZ = True


# ═══════════════════════════════════════════════
# DEBUG TOOLBAR (uniquement en développement)
# ═══════════════════════════════════════════════

INTERNAL_IPS = ['127.0.0.1']


# ═══════════════════════════════════════════════
# DIVERS
# ═══════════════════════════════════════════════

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Redirige vers cette page après connexion
LOGIN_REDIRECT_URL = '/'
LOGIN_URL = '/compte/connexion/'

# ═══════════════════════════════════════════════
# AVIS CLIENTS
# ═══════════════════════════════════════════════

# En production (DEBUG=False), mettre True pour exiger une commande LIVREE.
# En développement, False permet de tester les avis sans avoir passé commande.
AVIS_ACHAT_REQUIS = config('AVIS_ACHAT_REQUIS', default=False, cast=bool)
# ═══════════════════════════════════════════════════════════
# GOOGLE OAUTH2
# Créez vos credentials sur : https://console.cloud.google.com
# Ajoutez dans votre .env : GOOGLE_CLIENT_ID et GOOGLE_CLIENT_SECRET
# URI de redirection à configurer dans Google Console :
#   https://hooyia-market-wpsp.onrender.com/compte/google/callback/
# ═══════════════════════════════════════════════════════════
GOOGLE_CLIENT_ID     = config('GOOGLE_CLIENT_ID',     default='')
GOOGLE_CLIENT_SECRET = config('GOOGLE_CLIENT_SECRET', default='')
GOOGLE_REDIRECT_URI  = config('GOOGLE_REDIRECT_URI',  default='https://hooyia-market-wpsp.onrender.com/compte/google/callback/')