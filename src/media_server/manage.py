import os
import sys

from media_server.deploy import get_settings_module


def main():
    # API_DIR на path — startup_timing и общий log_format.
    api_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'api'))
    if api_dir not in sys.path:
        sys.path.insert(0, api_dir)

    from src.core.utils.startup_timing import ENV_MEDIA_START_WALL, mark_start

    mark_start(env_key=ENV_MEDIA_START_WALL)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', get_settings_module())

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Не удалось импортировать Django. Убедитесь, что Django установлен и "
            "доступен в PYTHONPATH. Активировано ли виртуальное окружение?"
        ) from exc

    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
