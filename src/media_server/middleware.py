import logging
import re
import time
from collections import defaultdict
from threading import Lock

from django.conf import settings
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

from media_server.maintenance import MAINTENANCE_DETAIL, is_maintenance_enabled

logger = logging.getLogger('media_server.middleware')

_RATE_RE = re.compile(r'^(\d+)/(second|minute|hour|day)$')


def _parse_rate(rate: str) -> tuple[int, float]:
    match = _RATE_RE.match((rate or '').strip().lower())
    if not match:
        return 30, 60.0
    count = int(match.group(1))
    unit = match.group(2)
    windows = {'second': 1.0, 'minute': 60.0, 'hour': 3600.0, 'day': 86400.0}
    return count, windows.get(unit, 60.0)


class MaintenanceMiddleware(MiddlewareMixin):
    """Блокировка Media API при включённом режиме технических works."""

    def process_request(self, request):
        if not is_maintenance_enabled():
            return None
        response = JsonResponse(
            {'code': 'maintenance', 'detail': MAINTENANCE_DETAIL},
            status=503,
        )
        response['X-Maintenance-Mode'] = '1'
        response['Retry-After'] = '3600'
        return response


class SecurityHeadersMiddleware(MiddlewareMixin):
    """Добавляет заголовки безопасности к ответам."""

    def process_response(self, request, response):
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        if getattr(settings, 'MEDIA_API_STRICT_CSP', False):
            response['Content-Security-Policy'] = (
                "default-src 'none'; "
                "frame-ancestors 'none'; "
                "base-uri 'none'; "
                "form-action 'none'"
            )
            response['Permissions-Policy'] = (
                'accelerometer=(), camera=(), geolocation=(), gyroscope=(), '
                'magnetometer=(), microphone=(), payment=(), usb=()'
            )

        if settings.MEDIA_API_PROTOCOL == 'https' or getattr(settings, 'MEDIA_API_HSTS_ENABLED', False):
            response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

        return response


class UploadRateLimitMiddleware(MiddlewareMixin):
    """Ограничение частоты POST /upload/ по IP (актуально в production)."""

    _lock = Lock()
    _hits: dict[str, list[float]] = defaultdict(list)

    def process_request(self, request):
        if request.method != 'POST' or not request.path.rstrip('/').endswith('/upload'):
            return None

        if getattr(settings, 'DEBUG', False):
            return None

        client_ip = self._client_ip(request)
        limit, window = _parse_rate(getattr(settings, 'MEDIA_API_UPLOAD_RATE', '30/minute'))
        now = time.time()
        cutoff = now - window

        with self._lock:
            bucket = self._hits[client_ip]
            self._hits[client_ip] = [ts for ts in bucket if ts > cutoff]
            if len(self._hits[client_ip]) >= limit:
                logger.warning('Upload rate limit exceeded: ip=%s', client_ip)
                return JsonResponse({'error': 'Слишком много запросов на загрузку'}, status=429)
            self._hits[client_ip].append(now)

        return None

    @staticmethod
    def _client_ip(request) -> str:
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
        if forwarded:
            return forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'unknown')


class RequestLoggingMiddleware(MiddlewareMixin):
    """Логирует входящие запросы и время обработки."""

    def process_request(self, request):
        request._start_time = time.time()

    def process_response(self, request, response):
        start_time = getattr(request, '_start_time', None)
        duration_ms = 0
        if start_time:
            duration_ms = (time.time() - start_time) * 1000

        logger.info(
            "%s %s -> %d (%.1f ms)",
            request.method,
            request.get_full_path(),
            response.status_code,
            duration_ms,
        )
        return response
