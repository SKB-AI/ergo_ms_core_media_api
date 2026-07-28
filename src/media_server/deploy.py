import os
import sys
from typing import List

import environ

from media_server.paths import SYSTEM_DIR

_DEPLOYMENT_DIR = SYSTEM_DIR / 'core' / 'deployment'
if str(_DEPLOYMENT_DIR) not in sys.path:
    sys.path.insert(0, str(_DEPLOYMENT_DIR))

from env_file_loader import apply_project_env_to_environ  # noqa: E402

_env = environ.Env()
apply_project_env_to_environ(SYSTEM_DIR, override_existing=False)

INSECURE_SECRET_KEYS = frozenset({
    '',
    'secret-key',
    'media-api-insecure-key',
    'django-insecure',
})

ASGI_APPLICATION = 'media_server.asgi:application'


def get_deploy_type() -> str:
    """ERGO_ENV; явный MEDIA_API_DEPLOY_TYPE перекрывает."""
    from ergo_modes import effective_deploy_type

    return effective_deploy_type(os.environ, override_key='MEDIA_API_DEPLOY_TYPE')


def is_production() -> bool:
    return get_deploy_type() == 'production'


def get_settings_module() -> str:
    if is_production():
        return 'media_server.settings.production'
    return 'media_server.settings.development'


def get_default_bind_host() -> str:
    return '127.0.0.1' if is_production() else '0.0.0.0'


def get_media_bind_host(default: str | None = None) -> str:
    """Хост процесса Media API с учётом nginx (localhost)."""
    explicit = os.environ.get('MEDIA_API_BIND_HOST', '').strip()
    if explicit:
        return explicit
    scripts_dir = SYSTEM_DIR / 'core' / 'deployment' / 'scripts'
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    try:
        from deployment_env import is_nginx_enabled  # noqa: WPS433

        if is_nginx_enabled() or is_production():
            return '127.0.0.1'
    except Exception:
        if is_production():
            return '127.0.0.1'
    return default if default is not None else get_default_bind_host()


def get_media_bind_port(default: str = '8003') -> str:
    """Порт процесса: MEDIA_API_BIND_PORT, иначе MEDIA_API_PORT (не 80/443 в production)."""
    port = (
        os.environ.get('MEDIA_API_BIND_PORT', '').strip()
        or os.environ.get('MEDIA_API_PORT', '').strip()
        or default
    )
    if is_production() and port in ('80', '443'):
        port = os.environ.get('MEDIA_API_BIND_PORT', '').strip() or default
    return port


def build_daphne_command(python_executable: str | None = None) -> List[str]:
    """Production Media API через daphne (ASGI, без autoreload)."""
    api_dir = SYSTEM_DIR / 'core' / 'api'
    if str(api_dir) not in sys.path:
        sys.path.insert(0, str(api_dir))
    from src.config.log_format import DAPHNE_LOG_FMT

    exe = python_executable or sys.executable
    return [
        exe,
        '-m',
        'daphne',
        '-b',
        get_media_bind_host(),
        '-p',
        get_media_bind_port(),
        '--access-log',
        os.devnull,
        '--log-fmt',
        DAPHNE_LOG_FMT,
        ASGI_APPLICATION,
    ]


def build_dev_command(python_executable: str | None = None) -> List[str]:
    """Development: Daphne runserver через management-команду `dev`."""
    exe = python_executable or sys.executable
    return [exe, '-m', 'media_server.manage', 'dev']


def validate_production_config(*, secret_key: str, allowed_hosts: list) -> None:
    """
    Проверяет небезопасную production-конфигурацию media_api.

    Небезопасный API_SECRET_KEY и hosts 0.0.0.0/* — предупреждение в консоль (без остановки).
    """
    import warnings

    if secret_key in INSECURE_SECRET_KEYS:
        warnings.warn(
            'MEDIA_API_DEPLOY_TYPE=production: задан небезопасный API_SECRET_KEY '
            '(значение по умолчанию). Укажите надёжный API_SECRET_KEY в .env.',
            UserWarning,
            stacklevel=2,
        )

    unsafe_hosts = {'0.0.0.0', '*'}
    if unsafe_hosts.intersection(set(allowed_hosts)):
        warnings.warn(
            'MEDIA_API_DEPLOY_TYPE=production: MEDIA_API_ALLOWED_HOSTS содержит '
            '0.0.0.0 или * — в production укажите конкретные хосты.',
            UserWarning,
            stacklevel=2,
        )
