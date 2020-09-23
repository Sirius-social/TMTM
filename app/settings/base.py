"""
Django settings for project.

Generated by 'django-admin startproject' using Django 2.2.

For more information on this file, see
https://docs.djangoproject.com/en/2.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.2/ref/settings/
"""

import os
import logging

logging.getLogger().setLevel(logging.WARNING)

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '7ns7(xo2h^f*%6_a#tdt_toh9$82p(+a1y_f!nref=i3my8@rw'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'channels',
    'scripts',
    'wrapper',
    'ui'
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'settings.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'templates')
        ],
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

WSGI_APPLICATION = 'settings.wsgi.application'
ASGI_APPLICATION = 'settings.routing.application'


REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 100,
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.BasicAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ]
}


# Database
# https://docs.djangoproject.com/en/2.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DATABASE_NAME') or 'postgres',
        'USER': os.environ.get('DATABASE_USER') or 'postgres',
        'PASSWORD': os.environ.get('DATABASE_PASSWORD') or 'postgres',
        'HOST': os.environ.get('DATABASE_HOST') or 'db',
        'PORT': os.environ.get('DATABASE_PORT') or 5432,
        'TEST': {
            'NAME': 'test_database',
        },
    }
}


# Password validation
# https://docs.djangoproject.com/en/2.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/2.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.2/howto/static-files/
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "static")
]
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATIC_URL = '/static/'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
MEDIA_URL = '/content/'
MEDIA_ROOT = '/tmp'

SENTRY_DSN = os.getenv('SENTRY_DSN')

AGENT = {
    'credentials': os.getenv('AGENT_CREDENTIALS'),
    'server_address': os.getenv('AGENT_SERVER_ADDRESS'),
    'entity': os.getenv('AGENT_ENTITY'),
    'my_verkey': os.getenv('AGENT_MY_VERKEY'),
    'my_secret_key': os.getenv('AGENT_MY_SECRET_KEY'),
    'agent_verkey': os.getenv('AGENT_VERKEY'),
    'is_sea': os.getenv('AGENT_IS_SEA', False) in ['1', 'on', 'yes']
}


PARTICIPANTS_META = {
    '4vEF4eHwQ1GB5s766rAYAe': {
        'label': 'ADI Smart',
        'logo': 'ady_container.png',
        'icon': 'ady_smart.jpg',
        'url': 'https://ady.socialsirius.com',
        'verkey': '38r8qU19FRYqqRQVtaWyoNP55wBJUZfBiAKBd7z9y1Qv'
    },
    'U9A6U7LZQe4dCh84t3fpTK': {
        'label': 'DKR',
        'logo': 'ktz_express.svg',
        'icon': 'dkr.png',
        'url': 'https://dkr.socialsirius.com',
        'verkey': 'FnyCacPf4R128ZwZnzzqStSwaUF54FXmhSL2ycy9aYG5'
    },
    '6jzbnVE5S6j15afcpC9yhF': {
        'label': 'GR Logistics & Terminals',
        'logo': 'gr_logistics.png',
        'icon': 'gr.jpg',
        'url': 'https://gr.socialsirius.com',
        'verkey': '48VZxo8boPPikNPGEEHfLoCtUN8g1n6veYwndRDpW9BD'
    },
    'D96GgE1PVtWeSfuAQZ9neY': {
        'label': 'KAZMORTRANSFLOT',
        'logo': 'kazmortransflot.jpg',
        'icon': 'kazmortransflot.jpg',
        'url': 'https://kazmortransflot.socialsirius.com',
        'verkey': '7ckhcwQCMV9RpYC4RQ3EgXEn4nbjgumGLL9CyWtqf5es'
    },
    'Ch4eVSWf7KXRubk5to6WFC': {
        'label': 'PMIS - PORT OF BAKU',
        'logo': 'port_of_baku.jpg',
        'icon': 'pmis_port_baku.png',
        'url': 'https://pmis.socialsirius.com',
        'verkey': '7NZuS52TEAnrD5VTme3JHbyXQHQtbstTUpdgBGxhZkMp'
    },
    'VU7c9jvBqLee9NkChXU1Kn': {
        'label': 'Solvo.tos - PORT AKTAU',
        'logo': 'port_aktau.png',
        'icon': 'solvo.tos.png',
        'url': 'https://solvotos.socialsirius.com',
        'verkey': 'GWuxzCXX3ddX9R6bX1if1Me7wz1WiiyKEdzsdB7X5npG'
    }
}
PARTICIPANTS = [
    '4vEF4eHwQ1GB5s766rAYAe', 'U9A6U7LZQe4dCh84t3fpTK',
    '6jzbnVE5S6j15afcpC9yhF', 'Ch4eVSWf7KXRubk5to6WFC', 'VU7c9jvBqLee9NkChXU1Kn'
]


ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', None)
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', None)
REDIS = os.getenv('REDIS', None)
