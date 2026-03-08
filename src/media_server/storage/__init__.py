from django.conf import settings

from .local import LocalFileStorage

_storage_instance = None


def get_storage():
    global _storage_instance
    if _storage_instance is not None:
        return _storage_instance

    storage_type = getattr(settings, 'MEDIA_STORAGE_TYPE', 'local')

    if storage_type == 'local':
        _storage_instance = LocalFileStorage(
            root_path=getattr(settings, 'MEDIA_STORAGE_PATH', 'media')
        )
    else:
        raise ValueError(f"Неизвестный тип хранилища: {storage_type}")

    return _storage_instance


def reset_storage():
    global _storage_instance
    _storage_instance = None
