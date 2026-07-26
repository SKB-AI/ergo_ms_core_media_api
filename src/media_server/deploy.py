import environ

from media_server.paths import SYSTEM_DIR

_env = environ.Env()
_env_file = SYSTEM_DIR / '.env'
if _env_file.exists():
    _env.read_env(str(_env_file))

INSECURE_SECRET_KEYS = frozenset({
    '',
    'secret-key',
    'media-api-insecure-key',
    'django-insecure',
})


def get_deploy_type() -> str:
    return _env.str('MEDIA_API_DEPLOY_TYPE', default='development').strip().lower()


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
