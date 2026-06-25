from media_server.deploy import get_default_bind_host
from media_server.settings.base import *  # noqa: F403

DEBUG = True

ALLOWED_HOSTS = env.list(  # noqa: F405
    'MEDIA_API_ALLOWED_HOSTS',
    default=['localhost', '127.0.0.1', '0.0.0.0'],
)

if not MEDIA_API_BIND_HOST:  # noqa: F405
    MEDIA_API_BIND_HOST = get_default_bind_host()  # noqa: F405

CORS_ALLOWED_ORIGINS = env.list(  # noqa: F405
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

MEDIA_API_HEALTH_PUBLIC = True

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
            'filename': str(LOGS_DIR / 'media_api.log'),  # noqa: F405
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
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}
