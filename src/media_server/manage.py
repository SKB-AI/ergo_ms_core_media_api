import os
import sys

from media_server.deploy import get_settings_module


def main():
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
