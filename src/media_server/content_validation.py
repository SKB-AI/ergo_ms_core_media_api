"""Проверка расширения и сигнатуры содержимого загружаемых файлов (С5).

Режимы MEDIA_API_CONTENT_VALIDATION:
- extension — только расширение (дефолт кода / open)
- extension_and_magic — расширение + sniff (filetype), standard / hardened
- extension_magic_av — magic + антивирус (phase 2 stub; без сканера — отказ)

SVG: разрешён только при расширении .svg и sniff svg/xml (не «голый» html).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import BinaryIO, Iterable

logger = logging.getLogger('media_server.content_validation')

MODE_EXTENSION = 'extension'
MODE_EXTENSION_AND_MAGIC = 'extension_and_magic'
MODE_EXTENSION_MAGIC_AV = 'extension_magic_av'

VALID_MODES = frozenset({
    MODE_EXTENSION,
    MODE_EXTENSION_AND_MAGIC,
    MODE_EXTENSION_MAGIC_AV,
})

MODE_RANK: dict[str, int] = {
    MODE_EXTENSION: 0,
    MODE_EXTENSION_AND_MAGIC: 1,
    MODE_EXTENSION_MAGIC_AV: 2,
}

# Зеркало core/api media_upload_validation._DEFAULT_ALLOWED_EXTENSIONS (без импорта API).
_DEFAULT_ALLOWED_EXTENSIONS = frozenset({
    'jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'ico',
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'odt', 'ods', 'txt', 'csv', 'rtf',
    'parquet',
    'zip', '7z', 'rar', 'tar', 'gz',
    'mp3', 'wav', 'ogg', 'mp4', 'webm', 'mov', 'avi',
    'json', 'xml', 'yaml', 'yml', 'md',
    'epub', 'fb2',
})

# Расширения без устойчивой magic-сигнатуры — sniff=None допустим.
_SOFT_EXTENSIONS = frozenset({
    'txt', 'csv', 'md', 'json', 'yaml', 'yml', 'rtf', 'xml',
})

# Sniffed типы, которые никогда не принимаем как «безобидный» файл.
_DANGEROUS_SNIFF_EXTS = frozenset({
    'html', 'htm', 'js', 'mjs', 'exe', 'dll', 'elf', 'macho', 'wasm',
})

# Sniffed filetype.extension → допустимые заявленные расширения.
_SNIFF_ALLOWED_DECLARED: dict[str, frozenset[str]] = {
    'jpg': frozenset({'jpg', 'jpeg'}),
    'jpeg': frozenset({'jpg', 'jpeg'}),
    'png': frozenset({'png'}),
    'gif': frozenset({'gif'}),
    'webp': frozenset({'webp'}),
    'ico': frozenset({'ico'}),
    'bmp': frozenset({'bmp'}),
    'tif': frozenset({'tif', 'tiff'}),
    'tiff': frozenset({'tif', 'tiff'}),
    'svg': frozenset({'svg'}),
    'pdf': frozenset({'pdf'}),
    'zip': frozenset({'zip', 'docx', 'xlsx', 'pptx', 'odt', 'ods', 'epub', 'jar'}),
    'gz': frozenset({'gz', 'tar'}),
    'tar': frozenset({'tar'}),
    'rar': frozenset({'rar'}),
    '7z': frozenset({'7z'}),
    'mp3': frozenset({'mp3'}),
    'wav': frozenset({'wav'}),
    'ogg': frozenset({'ogg'}),
    'mp4': frozenset({'mp4', 'mov', 'm4v'}),
    'webm': frozenset({'webm'}),
    'avi': frozenset({'avi'}),
    'mkv': frozenset({'mkv'}),
    'xml': frozenset({'xml', 'svg', 'fb2'}),
    'json': frozenset({'json'}),
    'doc': frozenset({'doc'}),
    'xls': frozenset({'xls'}),
    'ppt': frozenset({'ppt'}),
    'rtf': frozenset({'rtf'}),
    'parquet': frozenset({'parquet'}),
}

_HEAD_BYTES = 8192


class ContentValidationError(Exception):
    """Отклонение загрузки; status_code подсказка для HTTP (обычно 415)."""

    def __init__(self, message: str, *, status_code: int = 415):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    message: str = ''
    status_code: int = 200
    extension: str = ''
    sniffed: str | None = None


def normalize_mode(mode: str | None) -> str:
    raw = (mode or MODE_EXTENSION).strip().lower()
    if raw not in VALID_MODES:
        return MODE_EXTENSION
    return raw


def mode_rank(mode: str | None) -> int:
    return MODE_RANK.get(normalize_mode(mode), 0)


def default_allowed_extensions() -> frozenset[str]:
    return _DEFAULT_ALLOWED_EXTENSIONS


def extension_of(filename_or_path: str) -> str:
    return os.path.splitext(filename_or_path or '')[1].lower().lstrip('.')


def _resolve_allowed(
    allowed_types: Iterable[str] | None,
) -> frozenset[str]:
    if allowed_types:
        return frozenset(str(x).lower().lstrip('.') for x in allowed_types if str(x).strip())
    return _DEFAULT_ALLOWED_EXTENSIONS


def _peek_bytes(file_obj_or_bytes: bytes | bytearray | BinaryIO, limit: int = _HEAD_BYTES) -> bytes:
    if isinstance(file_obj_or_bytes, (bytes, bytearray)):
        return bytes(file_obj_or_bytes[:limit])
    fh = file_obj_or_bytes
    if hasattr(fh, 'seek') and hasattr(fh, 'tell'):
        try:
            pos = fh.tell()
        except Exception:
            pos = None
        head = fh.read(limit)
        if pos is not None:
            try:
                fh.seek(pos)
            except Exception:
                try:
                    fh.seek(0)
                except Exception:
                    pass
        elif hasattr(fh, 'seek'):
            try:
                fh.seek(0)
            except Exception:
                pass
        return head if isinstance(head, (bytes, bytearray)) else b''
    # Django UploadedFile без tell — читаем через chunks и не можем откатить;
    # вызывающий должен передать bytes либо файл с seek.
    chunk = fh.read(limit)
    return chunk if isinstance(chunk, (bytes, bytearray)) else b''


def _sniff_extension(head: bytes) -> str | None:
    if not head:
        return None
    try:
        import filetype
    except ImportError:
        logger.error('Пакет filetype не установлен — magic-проверка недоступна')
        raise ContentValidationError(
            'Проверка содержимого недоступна: не установлен filetype',
            status_code=503,
        )
    kind = filetype.guess(head)
    if kind is None:
        return None
    return str(kind.extension or '').lower() or None


def _looks_like_svg(head: bytes) -> bool:
    """filetype часто не распознаёт SVG — эвристика по разметке."""
    text = head.lstrip()[:4096].lower()
    if b'<!doctype html' in text or b'<html' in text:
        return False
    return b'<svg' in text


def _check_magic(declared_ext: str, head: bytes) -> str | None:
    """Возвращает sniffed extension или None; бросает ContentValidationError при отказе."""
    sniffed = _sniff_extension(head)

    if sniffed in _DANGEROUS_SNIFF_EXTS:
        raise ContentValidationError(
            f'Обнаружен опасный тип содержимого ({sniffed}), загрузка отклонена',
        )

    if declared_ext == 'svg':
        if sniffed in ('svg', 'xml'):
            return sniffed
        if sniffed is None and _looks_like_svg(head):
            return 'svg'
        raise ContentValidationError(
            'Файл .svg не соответствует сигнатуре SVG/XML',
        )

    if sniffed is None:
        if declared_ext in _SOFT_EXTENSIONS:
            return None
        raise ContentValidationError(
            f'Не удалось определить тип содержимого для .{declared_ext}',
        )

    allowed_declared = _SNIFF_ALLOWED_DECLARED.get(sniffed)
    if allowed_declared is None:
        # Неизвестный sniff — требуем точное совпадение с расширением.
        if sniffed != declared_ext:
            raise ContentValidationError(
                f'Содержимое ({sniffed}) не соответствует расширению .{declared_ext}',
            )
        return sniffed

    if declared_ext not in allowed_declared:
        raise ContentValidationError(
            f'Содержимое ({sniffed}) не соответствует расширению .{declared_ext}',
        )
    return sniffed


def scan_av(body: bytes | bytearray | None = None, *, path: str | None = None) -> bool | None:
    """
    Phase 2 stub антивирусной проверки.

    Returns:
        True — чисто, False — угроза, None — сканер не настроен.
    """
    _ = body, path
    logger.warning(
        'MEDIA_API_CONTENT_VALIDATION=extension_magic_av, но AV-сканер не настроен '
        '(phase 2 stub); загрузка отклонена',
    )
    return None


def av_scanner_configured() -> bool:
    """Пока всегда False — реальный ClamAV не подключён."""
    return False


def validate_bytes(
    path_or_name: str,
    body: bytes | bytearray,
    *,
    mode: str | None = None,
    allowed_types: Iterable[str] | None = None,
) -> ValidationResult:
    """Проверка по имени/пути и полному телу (InternalWrite)."""
    mode_n = normalize_mode(mode)
    ext = extension_of(path_or_name)
    allowed = _resolve_allowed(allowed_types)

    if not ext:
        raise ContentValidationError('Отсутствует расширение файла')
    if ext not in allowed:
        raise ContentValidationError(f'Тип файла .{ext} не разрешён')

    sniffed: str | None = None
    if mode_rank(mode_n) >= MODE_RANK[MODE_EXTENSION_AND_MAGIC]:
        sniffed = _check_magic(ext, bytes(body[:_HEAD_BYTES]))

    if mode_n == MODE_EXTENSION_MAGIC_AV:
        if not av_scanner_configured():
            scan_av(body, path=path_or_name)
            raise ContentValidationError(
                'Антивирусная проверка недоступна (сканер не настроен)',
                status_code=503,
            )
        verdict = scan_av(body, path=path_or_name)
        if verdict is False:
            raise ContentValidationError('Файл отклонён антивирусной проверкой', status_code=415)
        if verdict is None:
            raise ContentValidationError(
                'Антивирусная проверка недоступна (сканер не настроен)',
                status_code=503,
            )

    return ValidationResult(ok=True, extension=ext, sniffed=sniffed)


def validate_upload(
    filename: str,
    file_obj_or_bytes: bytes | bytearray | BinaryIO,
    *,
    allowed_types: Iterable[str] | None = None,
    mode: str | None = None,
) -> ValidationResult:
    """Проверка пользовательской загрузки (UploadView)."""
    mode_n = normalize_mode(mode)
    ext = extension_of(filename)
    allowed = _resolve_allowed(allowed_types)

    if not ext:
        raise ContentValidationError('Отсутствует расширение файла')
    if ext not in allowed:
        raise ContentValidationError(f'Тип файла .{ext} не разрешён')

    sniffed: str | None = None
    if mode_rank(mode_n) >= MODE_RANK[MODE_EXTENSION_AND_MAGIC]:
        head = _peek_bytes(file_obj_or_bytes)
        sniffed = _check_magic(ext, head)

    if mode_n == MODE_EXTENSION_MAGIC_AV:
        if not av_scanner_configured():
            # Не читаем весь файл повторно — stub только логирует.
            body_hint: bytes | None
            if isinstance(file_obj_or_bytes, (bytes, bytearray)):
                body_hint = bytes(file_obj_or_bytes)
            else:
                body_hint = None
            scan_av(body_hint, path=filename)
            raise ContentValidationError(
                'Антивирусная проверка недоступна (сканер не настроен)',
                status_code=503,
            )

    return ValidationResult(ok=True, extension=ext, sniffed=sniffed)
