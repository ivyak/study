from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parents[2]
SECRET_KEY = 'local-accounting-read-only-http-no-session'
DEBUG = False
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', 'testserver']
INSTALLED_APPS = ['rest_framework', 'ledger']
MIDDLEWARE = ['ledger.middleware.LocalOnlyMiddleware']
ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
DB_PATH = Path(os.environ.get('LIFE_ACCOUNTING_DB', BASE_DIR / 'data/accounting.sqlite3'))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': DB_PATH, 'OPTIONS': {'timeout': 20},
  'TEST': {'NAME': BASE_DIR / 'data/test-accounting.sqlite3'}}}
TIME_ZONE = 'Asia/Tokyo'
USE_TZ = True
LANGUAGE_CODE = 'ja'
REST_FRAMEWORK = {
  'DEFAULT_AUTHENTICATION_CLASSES': [],
  'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.AllowAny'],
  'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'],
  'UNAUTHENTICATED_USER': None,
}
