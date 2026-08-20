"""
Django settings for produce_market.

Values that change between machines (secret key, debug flag, database) are read
from environment variables so the same code runs locally and in production.
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


# --- Core -------------------------------------------------------------------

SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-35^=19c$#plk+1pwiiop0kjx6#kwm54#6xvbkbud0b*gc#*40*',
)

DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'

# Refuse to start in production still using the throwaway development key.
# Failing loudly at boot beats discovering it after sessions and password
# reset tokens have been signed with a key that is public on GitHub.
if not DEBUG and SECRET_KEY.startswith('django-insecure-'):
    raise ImproperlyConfigured(
        'DJANGO_SECRET_KEY must be set to a real secret when DEBUG is off.'
    )

ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')


# --- Applications -----------------------------------------------------------

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Local apps
    'accounts',
    'listings',
    'orders',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'produce_market.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # Project-wide templates (base.html, home.html) live here; app-specific
        # ones live in <app>/templates/<app>/.
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                # Makes the cart item count available in every template.
                'orders.context_processors.cart_summary',
                # Stamps static URLs so edited CSS/JS is picked up on a
                # normal refresh instead of a hard one.
                'produce_market.context_processors.asset_version',
            ],
        },
    },
]

WSGI_APPLICATION = 'produce_market.wsgi.application'


# --- Database ---------------------------------------------------------------

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# --- Authentication ---------------------------------------------------------

# Swapped in before the first migration so Django uses our User model, which
# carries the farmer/buyer role. Changing this later is painful.
AUTH_USER_MODEL = 'accounts.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'listings:list'
LOGOUT_REDIRECT_URL = 'listings:list'


# --- Internationalization ---------------------------------------------------

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Lagos'
USE_I18N = True
USE_TZ = True


# --- Static and media files -------------------------------------------------

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Uploaded produce photos. media/ is deliberately kept out of version control
# (see .gitignore): the demo photos are ~4 MB of binaries that
# "manage.py fetch_images" rebuilds from Wikimedia Commons on demand, and real
# uploads belong on object storage rather than in a repository. A fresh clone
# therefore shows placeholder letters until that command has been run once --
# the README says so, and seed_demo prints a reminder.
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'


# --- Messages ---------------------------------------------------------------

from django.contrib.messages import constants as message_constants

# Map Django's message levels onto the CSS class names used in base.html.
MESSAGE_TAGS = {
    message_constants.DEBUG: 'debug',
    message_constants.INFO: 'info',
    message_constants.SUCCESS: 'success',
    message_constants.WARNING: 'warning',
    message_constants.ERROR: 'error',
}


# --- Email ------------------------------------------------------------------

if DEBUG:
    # Development: print messages to the runserver console instead of sending.
    MAILERS = {
        'default': {'BACKEND': 'django.core.mail.backends.console.EmailBackend'},
    }
else:
    MAILERS = {
        'default': {
            'BACKEND': 'django.core.mail.backends.smtp.EmailBackend',
            'HOST': os.environ.get('EMAIL_HOST', ''),
            'PORT': int(os.environ.get('EMAIL_PORT', '587')),
            'USER': os.environ.get('EMAIL_HOST_USER', ''),
            'PASSWORD': os.environ.get('EMAIL_HOST_PASSWORD', ''),
            'USE_TLS': True,
        },
    }

DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@farmlink.local')


# --- Security ----------------------------------------------------------------

# All off in development, because the dev server speaks plain HTTP and
# secure-only cookies would simply never be sent back.
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # Tells browsers to reach this host over HTTPS for the next year, without
    # asking first. Start low (e.g. 3600) when enabling this for real: the
    # header is cached by the browser and cannot be taken back early.
    SECURE_HSTS_SECONDS = int(os.environ.get('DJANGO_HSTS_SECONDS', '31536000'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    # Behind a reverse proxy Django only sees the internal HTTP hop, so it
    # needs the proxy's header to know the original request was HTTPS --
    # otherwise SECURE_SSL_REDIRECT loops forever.
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

    CSRF_TRUSTED_ORIGINS = [
        origin for origin in
        os.environ.get('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',') if origin
    ]

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
