import environ
from pathlib import Path

SYSTEM_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent

env = environ.Env()
_env_file = SYSTEM_DIR / '.env'
if _env_file.exists():
    env.read_env(str(_env_file))

SECRET_KEY = env.str('API_SECRET_KEY', default='media-api-insecure-key')

DEBUG = env.str('API_DEPLOY_TYPE', default='development') == 'development'

ALLOWED_HOSTS = env.list(
    'MEDIA_API_ALLOWED_HOSTS',
    default=['localhost', '127.0.0.1', '0.0.0.0'],
)

MEDIA_API_HOST = env.str('MEDIA_API_HOST', default='localhost')
MEDIA_API_PORT = env.int('MEDIA_API_PORT', default=8003)

MEDIA_STORAGE_TYPE = env.str('MEDIA_STORAGE_TYPE', default='local')
MEDIA_STORAGE_PATH = env.str('MEDIA_STORAGE_PATH', default='') or str(SYSTEM_DIR / 'media')

MEDIA_URL_EXPIRATION = env.int('MEDIA_URL_EXPIRATION', default=3600)
MEDIA_UPLOAD_MAX_SIZE = env.int('MEDIA_UPLOAD_MAX_SIZE', default=104857600)
MEDIA_UPLOAD_TOKEN_EXPIRATION = env.int('MEDIA_UPLOAD_TOKEN_EXPIRATION', default=300)

DATA_UPLOAD_MAX_MEMORY_SIZE = MEDIA_UPLOAD_MAX_SIZE
FILE_UPLOAD_MAX_MEMORY_SIZE = MEDIA_UPLOAD_MAX_SIZE

INSTALLED_APPS = [
    'corsheaders',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'media_server.middleware.SecurityHeadersMiddleware',
    'media_server.middleware.RequestLoggingMiddleware',
]

ROOT_URLCONF = 'media_server.urls'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

CORS_ALLOW_ALL_ORIGINS = False

CORS_ALLOWED_ORIGINS = env.list(
    'CORS_ALLOWED_ORIGINS',
    default=[
        'http://localhost:5173',
        'http://127.0.0.1:5173',
        'http://localhost:8001',
        'http://127.0.0.1:8001',
        'http://localhost:8000',
        'http://127.0.0.1:8000',
    ],
)

CORS_ALLOW_CREDENTIALS = True

LOGS_DIR = SYSTEM_DIR / 'logs'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': str(LOGS_DIR / 'media_api.log'),
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'media_server': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
    },
}

USE_TZ = True
TIME_ZONE = 'UTC'
