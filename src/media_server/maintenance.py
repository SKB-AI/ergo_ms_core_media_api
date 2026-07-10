"""Проверка режима технических works (тот же флаг, что у основного API)."""

from pathlib import Path

from media_server.paths import SYSTEM_DIR

MAINTENANCE_FLAG_NAME = 'maintenance.flag'
MAINTENANCE_DETAIL = 'Система временно недоступна. Мы проводим обновление и скоро вернёмся.'


def maintenance_flag_path() -> Path:
    return SYSTEM_DIR / MAINTENANCE_FLAG_NAME


def is_maintenance_enabled() -> bool:
    return maintenance_flag_path().is_file()
