"""
Команда Django для development Media API (Daphne + autoreload), как у core API `dev`.
"""

import logging
import os
import subprocess
import sys

try:
    from daphne.management.commands.runserver import Command as RunserverCommand
except ImportError:
    from django.core.management.commands.runserver import Command as RunserverCommand
from django.core.management.base import CommandParser

from media_server.deploy import (
    build_daphne_command,
    get_media_bind_host,
    get_media_bind_port,
    is_production,
)
from src.core.utils.startup_timing import (
    StreamReadyWrapper,
    install_listening_ready_handler,
    remove_listening_ready_handler,
)

logger = logging.getLogger('media_server.commands')

SERVICE_NAME = 'Media API'


def _env_autoreload_enabled() -> bool:
    raw = os.environ.get('API_AUTORELOAD', 'true').strip().lower()
    return raw not in ('0', 'false', 'no', 'off')


class Command(RunserverCommand):
    help = 'Запускает Media API development server (Daphne)'

    def log_action(self, protocol, action, details):
        """HTTP access — только RequestLoggingMiddleware."""
        return

    def add_arguments(self, parser: CommandParser) -> None:
        super().add_arguments(parser)

    def handle(self, *args: tuple, **options: dict) -> None:
        if is_production():
            host = get_media_bind_host()
            port = get_media_bind_port()
            msg = f'{SERVICE_NAME} (запуск как на сервере): daphne на {host}:{port} (без autoreload)'
            logger.info(msg)
            try:
                self.stdout.write(self.style.SUCCESS(msg))
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
            cmd = build_daphne_command(sys.executable)
            raise SystemExit(subprocess.call(cmd))

        if not _env_autoreload_enabled():
            options['use_reloader'] = False
            msg = 'API_AUTORELOAD=false: runserver без autoreload'
            logger.info(msg)
            try:
                self.stdout.write(self.style.WARNING(msg))
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass

        use_reloader = bool(options.get('use_reloader', True))
        is_reloader_child = os.environ.get('RUN_MAIN') == 'true'
        if use_reloader:
            role = (
                'autoreload child (рабочий процесс)'
                if is_reloader_child
                else 'autoreload parent (launcher)'
            )
        else:
            role = 'без autoreload'
        logger.info('Запуск команды runserver (%s)', role)

        if not options['addrport']:
            addrport = f'{get_media_bind_host()}:{get_media_bind_port()}'
            logger.info('Используются настройки по умолчанию: %s', addrport)
            options['addrport'] = addrport
        else:
            logger.info('Используются пользовательские настройки: %s', options['addrport'])

        listen_handler = None
        if is_reloader_child or not use_reloader:
            listen_handler = install_listening_ready_handler(
                SERVICE_NAME,
                stream=self.stdout,
            )

        try:
            orig_stdout = self.stdout
            self.stdout = StreamReadyWrapper(orig_stdout, SERVICE_NAME)
            if listen_handler is not None:
                listen_handler._stream = self.stdout
            try:
                super().handle(*args, **options)
            finally:
                self.stdout = orig_stdout
        except Exception as exc:
            logger.error('Ошибка при запуске сервера: %s', exc)
            raise
        finally:
            remove_listening_ready_handler(listen_handler)
