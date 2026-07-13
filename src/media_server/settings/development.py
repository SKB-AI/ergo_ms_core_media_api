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

from media_server.logging_config import build_media_logging_config
from media_server.paths import LOGS_DIR, SYSTEM_DIR

LOGGING = build_media_logging_config(LOGS_DIR, SYSTEM_DIR / '.env')
