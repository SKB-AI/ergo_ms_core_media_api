"""Пути media_api — ERGO_LOGS_DIR из корневого .env."""

from pathlib import Path

SYSTEM_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent


def _read_env(name: str, default: str = '') -> str:
    import os

    value = os.environ.get(name)
    if value is not None and str(value).strip() != '':
        return str(value).strip()
    env_path = SYSTEM_DIR / '.env'
    if not env_path.is_file():
        return default
    for line in env_path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, raw = line.partition('=')
        if key.strip() == name:
            return raw.strip().strip('"').strip("'")
    return default


def resolve_logs_dir() -> Path:
    custom = _read_env('ERGO_LOGS_DIR')
    if custom:
        path = Path(custom)
        if not path.is_absolute():
            path = SYSTEM_DIR / path
        return path
    return SYSTEM_DIR / 'logs'


LOGS_DIR = resolve_logs_dir()
