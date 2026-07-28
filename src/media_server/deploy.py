import sys

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


def get_deploy_type() -> str:
    """ERGO_ENV; явный MEDIA_API_DEPLOY_TYPE перекрывает."""
    import os

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
