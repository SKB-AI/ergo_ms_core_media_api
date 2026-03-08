from abc import ABC, abstractmethod
from typing import BinaryIO, Optional


class BaseStorage(ABC):

    @abstractmethod
    def save(self, path: str, content: BinaryIO) -> str:
        """Сохранить файл по указанному пути. Возвращает итоговый путь."""

    @abstractmethod
    def open(self, path: str) -> BinaryIO:
        """Открыть файл для чтения."""

    @abstractmethod
    def delete(self, path: str) -> bool:
        """Удалить файл. Возвращает True если файл был удалён."""

    @abstractmethod
    def exists(self, path: str) -> bool:
        """Проверить существование файла."""

    @abstractmethod
    def size(self, path: str) -> int:
        """Получить размер файла в байтах."""

    @abstractmethod
    def full_path(self, path: str) -> str:
        """Получить абсолютный путь к файлу."""

    @abstractmethod
    def is_available(self) -> bool:
        """Проверить доступность хранилища."""
