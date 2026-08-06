import os
import sys

import environ

from media_server.paths import LOGS_DIR, SYSTEM_DIR

env = environ.Env()
_env_file = SYSTEM_DIR / '.env'
if _env_file.exists():
    env.read_env(str(_env_file))

_DEPLOYMENT_DIR = SYSTEM_DIR / 'core' / 'deployment'
if str(_DEPLOYMENT_DIR) not in sys.path:
    sys.path.insert(0, str(_DEPLOYMENT_DIR))

from security.profile_defaults import merge_security_profile_defaults  # noqa: E402


def _media_security_merged() -> dict[str, str]:
    subset: dict[str, str] = {}
    for key in ('ERGO_SECURITY', 'MEDIA_URL_EXPIRATION', 'MEDIA_API_UPLOAD_RATE'):
        raw = os.environ.get(key)
        if raw is not None and str(raw).strip() != '':
            subset[key] = str(raw).strip()
    return merge_security_profile_defaults(subset)


_security_merged = _media_security_merged()

# Обязателен и должен совпадать с API_SECRET_KEY в core/api — им подписываются/проверяются
# media-URL и upload-токены (см. signing.py). Без общего ключа подписи не сойдутся,
# поэтому небезопасный дефолт недопустим (fail-fast, как в core/api).
SECRET_KEY = env.str('API_SECRET_KEY')

MEDIA_API_HOST = env.str('MEDIA_API_HOST', default='localhost')
MEDIA_API_PORT = env.int('MEDIA_API_PORT', default=8003)
MEDIA_API_PROTOCOL = env.str('MEDIA_API_PROTOCOL', default='http')

MEDIA_STORAGE_TYPE = env.str('MEDIA_STORAGE_TYPE', default='local')
MEDIA_STORAGE_PATH = env.str('MEDIA_STORAGE_PATH', default='') or str(SYSTEM_DIR / 'media')

try:
    MEDIA_URL_EXPIRATION = int(_security_merged.get('MEDIA_URL_EXPIRATION', '3600'))
except ValueError:
    MEDIA_URL_EXPIRATION = 3600
MEDIA_UPLOAD_MAX_SIZE = env.int('MEDIA_UPLOAD_MAX_SIZE', default=524288000)
MEDIA_UPLOAD_HARD_MAX_SIZE = env.int(
    'MEDIA_UPLOAD_HARD_MAX_SIZE',
    default=5 * 1024 * 1024 * 1024,
)
if MEDIA_UPLOAD_HARD_MAX_SIZE < MEDIA_UPLOAD_MAX_SIZE:
    MEDIA_UPLOAD_HARD_MAX_SIZE = MEDIA_UPLOAD_MAX_SIZE
MEDIA_UPLOAD_TOKEN_EXPIRATION = env.int('MEDIA_UPLOAD_TOKEN_EXPIRATION', default=300)

# Служебный ключ для internal API (core/api в режиме MEDIA_ACCESS_MODE=remote)
MEDIA_API_INTERNAL_KEY = env.str('MEDIA_API_INTERNAL_KEY', default='').strip()

# Доверенные прокси (IP/CIDR через запятую). Пустой список — X-Forwarded-For
# игнорируется, клиентский IP = REMOTE_ADDR (безопасно при прямом доступе).
MEDIA_API_TRUSTED_PROXIES = env.list('MEDIA_API_TRUSTED_PROXIES', default=[])

MEDIA_API_BIND_HOST = env.str('MEDIA_API_BIND_HOST', default='')

MEDIA_API_HEALTH_PUBLIC = env.bool('MEDIA_API_HEALTH_PUBLIC', default=False)

MEDIA_API_UPLOAD_RATE = _security_merged.get('MEDIA_API_UPLOAD_RATE', '30/minute')

# Макс. размер тела запроса — hard max (модули могут быть выше MEDIA_UPLOAD_MAX_SIZE).
# FILE_* — порог сброса на диск, не потолок размера файла.
DATA_UPLOAD_MAX_MEMORY_SIZE = MEDIA_UPLOAD_HARD_MAX_SIZE
FILE_UPLOAD_MAX_MEMORY_SIZE = min(MEDIA_UPLOAD_MAX_SIZE, 10 * 1024 * 1024)

INSTALLED_APPS = [
    'corsheaders',
    'media_server',  # management commands (dev)
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'media_server.middleware.MaintenanceMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'media_server.middleware.SecurityHeadersMiddleware',
    'media_server.middleware.UploadRateLimitMiddleware',
    'media_server.middleware.RequestLoggingMiddleware',
]

ROOT_URLCONF = 'media_server.urls'
ASGI_APPLICATION = 'media_server.asgi.application'
WSGI_APPLICATION = 'media_server.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

CORS_ALLOW_ALL_ORIGINS = False

CORS_ALLOW_CREDENTIALS = True

USE_TZ = True
TIME_ZONE = 'UTC'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
