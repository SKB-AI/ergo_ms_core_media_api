from media_server.deploy import get_default_bind_host, validate_production_config
from media_server.settings.base import *  # noqa: F403

DEBUG = False

ALLOWED_HOSTS = env.list(  # noqa: F405
    'MEDIA_API_ALLOWED_HOSTS',
    default=['localhost', '127.0.0.1'],
)

validate_production_config(secret_key=SECRET_KEY, allowed_hosts=ALLOWED_HOSTS)  # noqa: F405

if not MEDIA_API_BIND_HOST:  # noqa: F405
    MEDIA_API_BIND_HOST = get_default_bind_host()  # noqa: F405

CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[])  # noqa: F405

SECURE_SSL_REDIRECT = env.bool('MEDIA_API_SECURE_SSL_REDIRECT', default=False)  # noqa: F405
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

MEDIA_API_HSTS_ENABLED = env.bool('MEDIA_API_HSTS_ENABLED', default=False)  # noqa: F405
if MEDIA_API_HSTS_ENABLED:
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

MEDIA_API_STRICT_CSP = env.bool('MEDIA_API_STRICT_CSP', default=True)  # noqa: F405

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
            'level': 'INFO',
            'propagate': False,
        },
    },
}
