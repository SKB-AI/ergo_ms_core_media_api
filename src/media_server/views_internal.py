"""Служебные эндпоинты media_api для core/api (режим MEDIA_ACCESS_MODE=remote)."""

import hmac
import ipaddress
import logging
import mimetypes
import os

from django.conf import settings
from django.http import FileResponse, HttpResponse, JsonResponse
from django.views import View

from .storage import get_storage

logger = logging.getLogger('media_server.internal')

_UNSAFE_INLINE_TYPES = (
    'text/html', 'text/xml', 'application/xml', 'image/svg+xml', 'application/xhtml+xml',
)


def _client_ip(request) -> str:
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return (request.META.get('REMOTE_ADDR') or '').strip()


def _is_private_or_loopback(ip: str) -> bool:
    if not ip:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return bool(addr.is_private or addr.is_loopback or addr.is_link_local)


def _is_internal_authorized(request) -> bool:
    expected = getattr(settings, 'MEDIA_API_INTERNAL_KEY', '') or ''
    if not expected:
        return False
    # Internal API только из private/loopback сети (defense-in-depth к shared secret).
    if not _is_private_or_loopback(_client_ip(request)):
        return False
    provided = request.headers.get('X-Media-Internal-Key', '')
    return hmac.compare_digest(provided, expected)


def _forbidden():
    return JsonResponse({'error': 'Forbidden'}, status=403)


def _not_configured():
    return JsonResponse(
        {'error': 'Internal API отключён: не задан MEDIA_API_INTERNAL_KEY'},
        status=503,
    )


class InternalMetaView(View):
    """GET /internal/meta/<path> — exists + size."""

    def get(self, request, file_path):
        if not getattr(settings, 'MEDIA_API_INTERNAL_KEY', ''):
            return _not_configured()
        if not _is_internal_authorized(request):
            return _forbidden()

        storage = get_storage()
        if not storage.exists(file_path):
            return JsonResponse({'exists': False}, status=404)

        return JsonResponse({
            'exists': True,
            'path': file_path,
            'size': storage.size(file_path),
        })


class InternalReadView(View):
    """GET /internal/read/<path> — чтение файла для core/api."""

    def get(self, request, file_path):
        if not getattr(settings, 'MEDIA_API_INTERNAL_KEY', ''):
            return _not_configured()
        if not _is_internal_authorized(request):
            return _forbidden()

        storage = get_storage()
        if not storage.exists(file_path):
            return JsonResponse({'error': 'Файл не найден'}, status=404)

        content_type, _ = mimetypes.guess_type(file_path)
        if not content_type:
            content_type = 'application/octet-stream'

        fh = storage.open(file_path)
        response = FileResponse(fh, content_type=content_type)
        response['Content-Length'] = storage.size(file_path)
        filename = os.path.basename(file_path)
        if content_type in _UNSAFE_INLINE_TYPES:
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
        else:
            response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response


class InternalWriteView(View):
    """PUT /internal/write/<path> — запись файла из core/api."""

    def put(self, request, file_path):
        if not getattr(settings, 'MEDIA_API_INTERNAL_KEY', ''):
            return _not_configured()
        if not _is_internal_authorized(request):
            return _forbidden()

        default_max = int(getattr(settings, 'MEDIA_UPLOAD_MAX_SIZE', 524288000))
        hard_max = int(getattr(settings, 'MEDIA_UPLOAD_HARD_MAX_SIZE', default_max) or default_max)
        max_size = max(hard_max, default_max)
        content_length = request.META.get('CONTENT_LENGTH')
        if content_length is not None and str(content_length).strip() != '':
            try:
                declared = int(content_length)
            except (TypeError, ValueError):
                declared = None
            if declared is not None and declared > max_size:
                return JsonResponse(
                    {'error': f'Файл превышает допустимый размер ({max_size} байт)'},
                    status=413,
                )

        body = request.body
        if not body:
            return JsonResponse({'error': 'Пустое тело запроса'}, status=400)
        if len(body) > max_size:
            return JsonResponse(
                {'error': f'Файл превышает допустимый размер ({max_size} байт)'},
                status=413,
            )

        storage = get_storage()
        from io import BytesIO
        try:
            saved_path = storage.save(file_path, BytesIO(body))
        except PermissionError:
            return JsonResponse({'error': 'Недопустимый путь'}, status=400)

        logger.info('Internal write: path=%s, size=%d', saved_path, len(body))
        return JsonResponse({'path': saved_path, 'size': len(body)}, status=201)


class InternalDeleteView(View):
    """DELETE /internal/delete/<path> — удаление файла."""

    def delete(self, request, file_path):
        if not getattr(settings, 'MEDIA_API_INTERNAL_KEY', ''):
            return _not_configured()
        if not _is_internal_authorized(request):
            return _forbidden()

        storage = get_storage()
        deleted = storage.delete(file_path)
        if not deleted:
            return JsonResponse({'deleted': False}, status=404)
        return JsonResponse({'deleted': True, 'path': file_path})
