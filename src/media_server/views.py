import os
import re
import time
import mimetypes
import logging
import uuid

from django.conf import settings
from django.http import (
    FileResponse,
    HttpResponse,
    JsonResponse,
    StreamingHttpResponse,
)
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from .client_ip import is_private_or_loopback, resolve_client_ip
from .content_validation import ContentValidationError, validate_upload
from .signing import verify_url, verify_upload_token
from .storage import get_storage
from .upload_quota import check_upload_quota
from core.shared.system_version import get_system_version

logger = logging.getLogger('media_server.views')

RANGE_RE = re.compile(r'bytes=(\d+)-(\d*)')


class ServeView(View):
    """Раздача файлов с проверкой подписи и поддержкой Range-запросов."""

    def get(self, request, file_path):
        signature = request.GET.get('signature')
        expires = request.GET.get('expires')

        if not signature or not expires:
            logger.warning(
                'Serve 400: отсутствуют параметры подписи, path=%s, has_signature=%s, has_expires=%s',
                file_path, bool(signature), bool(expires),
            )
            return JsonResponse(
                {'error': 'Отсутствуют параметры подписи'},
                status=400,
            )

        try:
            expires = int(expires)
        except (ValueError, TypeError):
            logger.warning('Serve 400: некорректный expires, path=%s, expires_raw=%s', file_path, request.GET.get('expires'))
            return JsonResponse(
                {'error': 'Некорректный параметр expires'},
                status=400,
            )

        verify_ok = verify_url(file_path, signature, expires, settings.SECRET_KEY)
        if not verify_ok:
            now_ts = int(time.time())
            is_expired = now_ts > expires
            logger.info(
                'Serve 403: подпись недействительна или истекла, path=%s, expires=%s, now=%s, expired=%s',
                file_path, expires, now_ts, is_expired,
            )
            return JsonResponse(
                {'error': 'Подпись недействительна или истекла'},
                status=403,
            )

        storage = get_storage()
        try:
            file_exists = storage.exists(file_path)
        except Exception as e:
            logger.exception('Serve: ошибка проверки существования файла, path=%s', file_path)
            file_exists = False
        if not file_exists:
            resolved_hint = ''
            try:
                resolved_hint = getattr(storage, 'full_path', lambda p: '')(file_path)
            except Exception:
                pass
            logger.info(
                'Serve 404: файл не найден, path=%s, storage_root=%s, resolved=%s',
                file_path, getattr(settings, 'MEDIA_STORAGE_PATH', ''), resolved_hint,
            )
            return JsonResponse(
                {'error': 'Файл не найден'},
                status=404,
            )

        content_type, _ = mimetypes.guess_type(file_path)
        if not content_type:
            content_type = 'application/octet-stream'

        file_size = storage.size(file_path)
        range_header = request.META.get('HTTP_RANGE')

        if range_header:
            return self._serve_range(storage, file_path, file_size, content_type, range_header)

        fh = storage.open(file_path)
        response = FileResponse(fh, content_type=content_type)
        response['Content-Length'] = file_size
        response['Accept-Ranges'] = 'bytes'

        filename = os.path.basename(file_path)
        force_download = request.GET.get('download', '').lower() in ('1', 'true', 'yes')
        _UNSAFE_INLINE_TYPES = ('text/html', 'text/xml', 'application/xml', 'image/svg+xml', 'application/xhtml+xml')
        if force_download or content_type in _UNSAFE_INLINE_TYPES:
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
        elif content_type.startswith(('image/', 'video/', 'audio/', 'text/')):
            response['Content-Disposition'] = f'inline; filename="{filename}"'
        else:
            response['Content-Disposition'] = f'attachment; filename="{filename}"'

        logger.debug('Serve 200: path=%s, content_type=%s, size=%s', file_path, content_type, file_size)
        return response

    def _serve_range(self, storage, file_path, file_size, content_type, range_header):
        match = RANGE_RE.match(range_header)
        if not match:
            return JsonResponse({'error': 'Некорректный Range-заголовок'}, status=416)

        start = int(match.group(1))
        end_str = match.group(2)
        end = int(end_str) if end_str else file_size - 1

        if start >= file_size or end >= file_size or start > end:
            response = HttpResponse(status=416)
            response['Content-Range'] = f'bytes */{file_size}'
            return response

        length = end - start + 1
        chunk_size = 64 * 1024

        def _iter_range():
            fh = storage.open(file_path)
            try:
                fh.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = fh.read(min(chunk_size, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk
            finally:
                fh.close()

        response = StreamingHttpResponse(
            _iter_range(),
            content_type=content_type,
            status=206,
        )
        response['Content-Length'] = length
        response['Content-Range'] = f'bytes {start}-{end}/{file_size}'
        response['Accept-Ranges'] = 'bytes'
        return response


@method_decorator(csrf_exempt, name='dispatch')
class UploadView(View):
    """Загрузка файлов с проверкой upload-токена."""

    def post(self, request):
        token = (
            request.POST.get('token')
            or request.headers.get('X-Upload-Token')
        )
        if not token:
            return JsonResponse(
                {'error': 'Отсутствует upload-токен'},
                status=400,
            )

        payload = verify_upload_token(token, settings.SECRET_KEY)
        if not payload:
            return JsonResponse(
                {'error': 'Токен недействителен или истёк'},
                status=403,
            )

        quota_denied = check_upload_quota(
            user_id=payload.get('user_id'),
            quota=str(payload.get('quota') or 'user'),
        )
        if quota_denied is not None:
            return quota_denied

        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return JsonResponse(
                {'error': 'Файл не передан'},
                status=400,
            )

        default_max = int(getattr(settings, 'MEDIA_UPLOAD_MAX_SIZE', 524288000))
        hard_max = int(getattr(settings, 'MEDIA_UPLOAD_HARD_MAX_SIZE', default_max) or default_max)
        if hard_max < default_max:
            hard_max = default_max
        token_max = payload.get('max_size', default_max)
        try:
            max_size = min(int(token_max), hard_max)
        except (TypeError, ValueError):
            max_size = default_max
        if uploaded_file.size > max_size:
            return JsonResponse(
                {'error': f'Файл превышает допустимый размер ({max_size} байт)'},
                status=413,
            )

        allowed_types = payload.get('allowed_types')
        content_mode = getattr(settings, 'MEDIA_API_CONTENT_VALIDATION', 'extension')
        try:
            validate_upload(
                uploaded_file.name,
                uploaded_file,
                allowed_types=allowed_types,
                mode=content_mode,
            )
        except ContentValidationError as exc:
            return JsonResponse({'error': exc.message}, status=exc.status_code)

        target_dir = str(payload.get('target_dir', '') or '').replace('\\', '/').strip().strip('/')
        if '..' in target_dir.split('/'):
            return JsonResponse({'error': 'Недопустимый target_dir'}, status=400)
        file_uuid = str(uuid.uuid4())
        _, ext = os.path.splitext(uploaded_file.name)
        save_name = f"{file_uuid}{ext}"
        save_path = f'{target_dir}/{save_name}' if target_dir else save_name

        storage = get_storage()
        try:
            saved_path = storage.save(save_path, uploaded_file)
        except PermissionError:
            return JsonResponse({'error': 'Недопустимый путь загрузки'}, status=400)

        logger.info(
            "Файл загружен: user_id=%s, path=%s, size=%d",
            payload.get('user_id'),
            saved_path,
            uploaded_file.size,
        )

        return JsonResponse({
            'uuid': file_uuid,
            'path': saved_path,
            'original_name': uploaded_file.name,
            'size': uploaded_file.size,
            'content_type': uploaded_file.content_type,
        }, status=201)


class HealthView(View):
    """Проверка состояния медиа-сервиса."""

    def get(self, request):
        if not getattr(settings, 'MEDIA_API_HEALTH_PUBLIC', True):
            if not _is_internal_request(request):
                return JsonResponse({'error': 'Forbidden'}, status=403)

        storage = get_storage()
        return JsonResponse({
            'status': 'ok',
            'storage_type': settings.MEDIA_STORAGE_TYPE,
            'storage_available': storage.is_available(),
            'system_version': get_system_version(),
        })


def _is_internal_request(request) -> bool:
    return is_private_or_loopback(resolve_client_ip(request))
