import logging
import os
from pathlib import Path, PurePosixPath
from typing import BinaryIO

from .base import BaseStorage

logger = logging.getLogger('media_server.storage')


class LocalFileStorage(BaseStorage):

    def __init__(self, root_path: str):
        self._root = Path(root_path).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    def _normalize_relative(self, path: str) -> str:
        """Нормализует относительный путь; отклоняет абсолютные и ``..``."""
        if path is None:
            raise PermissionError('Путь не задан')
        raw = str(path).replace('\\', '/').strip()
        if not raw or raw.startswith('/') or (len(raw) >= 2 and raw[1] == ':'):
            raise PermissionError(f'Попытка выхода за пределы хранилища: {path}')
        posix = PurePosixPath(raw)
        if posix.is_absolute() or '..' in posix.parts:
            raise PermissionError(f'Попытка выхода за пределы хранилища: {path}')
        normalized = str(PurePosixPath(*[p for p in posix.parts if p not in ('', '.')]))
        if normalized in ('', '.'):
            raise PermissionError(f'Попытка выхода за пределы хранилища: {path}')
        return normalized

    def _resolve_path(self, path: str) -> Path:
        relative = self._normalize_relative(path)
        resolved = (self._root / relative).resolve()
        if not resolved.is_relative_to(self._root):
            raise PermissionError(f'Попытка выхода за пределы хранилища: {path}')
        return resolved

    def save(self, path: str, content: BinaryIO) -> str:
        target = self._resolve_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)

        with open(target, 'wb') as f:
            while True:
                chunk = content.read(8192)
                if not chunk:
                    break
                f.write(chunk)

        logger.info("Файл сохранён: %s (%d байт)", path, target.stat().st_size)
        return path

    def open(self, path: str) -> BinaryIO:
        target = self._resolve_path(path)
        return open(target, 'rb')

    def delete(self, path: str) -> bool:
        target = self._resolve_path(path)
        if target.exists():
            target.unlink()
            logger.info("Файл удалён: %s", path)
            return True
        return False

    def exists(self, path: str) -> bool:
        target = self._resolve_path(path)
        return target.is_file()

    def size(self, path: str) -> int:
        target = self._resolve_path(path)
        return target.stat().st_size

    def full_path(self, path: str) -> str:
        return str(self._resolve_path(path))

    def is_available(self) -> bool:
        try:
            return self._root.exists() and os.access(self._root, os.R_OK | os.W_OK)
        except OSError:
            return False
