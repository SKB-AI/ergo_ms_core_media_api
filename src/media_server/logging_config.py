"""Логирование Media API — env ERGO_LOG_* и MEDIA_API_LOG_*."""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def _load_log_env():
    scripts = Path(__file__).resolve().parents[4] / 'core' / 'deployment' / 'scripts'
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import log_env

    return log_env


def build_media_logging_config(logs_dir: Path, env_file: Path) -> dict:
    project_root = env_file.parent
    le = _load_log_env()
    file_level, console_level, console_enabled = le.service_levels('media_api', project_root)
    rotation = le.rotation_settings(project_root)
    log_path = str(logs_dir / le.log_basename('MEDIA_API', project_root))

    handlers: dict = {
        'media_file': {
            'level': file_level,
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': log_path,
            'formatter': 'verbose',
            'encoding': 'utf-8',
            'maxBytes': rotation['max_bytes'],
            'backupCount': rotation['backup_count'],
            'delay': True,
        },
    }
    media_handlers = ['media_file']
    root_handlers = ['media_file']

    if console_enabled:
        handlers['console'] = {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
            'level': console_level,
        }
        media_handlers.append('console')
        root_handlers.append('console')

    return {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'verbose': {
                'format': '[{levelname}] {asctime} {name} {module} {message}',
                'style': '{',
                'datefmt': '%Y-%m-%d %H:%M:%S',
            },
            'simple': {
                'format': '[{levelname}] {name}: {message}',
                'style': '{',
            },
        },
        'handlers': handlers,
        'root': {
            'handlers': root_handlers,
            'level': 'INFO',
        },
        'loggers': {
            'django': {
                'handlers': media_handlers,
                'level': 'INFO',
                'propagate': False,
            },
            'media_server': {
                'handlers': media_handlers,
                'level': file_level,
                'propagate': False,
            },
        },
    }
