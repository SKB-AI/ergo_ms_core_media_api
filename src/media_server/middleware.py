import logging
import time

from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

from media_server.maintenance import MAINTENANCE_DETAIL, is_maintenance_enabled
from media_server.request_id import apply_response_header, get_request_id, request_id_from_meta

logger = logging.getLogger('media_server.middleware')


def _silence_wsgi_runserver_access() -> None:
    """Отключает встроенный access Django runserver — остаётся RequestLoggingMiddleware."""
    try:
        from django.core.servers.basehttp import WSGIRequestHandler
    except Exception:
        return
    if getattr(WSGIRequestHandler, '_ergo_access_silenced', False):
        return
    WSGIRequestHandler.log_message = lambda self, format, *args: None  # noqa: ARG005
    WSGIRequestHandler._ergo_access_silenced = True  # type: ignore[attr-defined]


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
        from django.conf import settings

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
    """Устарело: квота загрузки считается в UploadView (upload_quota по user_id).

    Оставлено как no-op для совместимости импортов; IP-потолок — nginx ergo_upload.
    """

    def process_request(self, request):
        return None


class RequestIdMiddleware(MiddlewareMixin):
    """Проставляет и возвращает X-Request-ID."""

    def process_request(self, request):
        request_id_from_meta(getattr(request, 'META', {}) or {})

    def process_response(self, request, response):
        apply_response_header(response)
        return response


class RequestLoggingMiddleware(MiddlewareMixin):
    """HTTP access в том же формате, что AccessLogMiddleware API."""

    _access_logger = logging.getLogger('django.server')

    def __init__(self, get_response):
        super().__init__(get_response)
        _silence_wsgi_runserver_access()

    def process_request(self, request):
        request._ergo_access_started = time.perf_counter()

    def process_response(self, request, response):
        try:
            method = request.method or '-'
            # path без query — без риска утечки токенов из query string
            path = request.path or '/'
            proto = request.META.get('SERVER_PROTOCOL', 'HTTP/1.1')
            status = getattr(response, 'status_code', '-')
            started = getattr(request, '_ergo_access_started', None)
            elapsed_ms = int((time.perf_counter() - started) * 1000) if started else 0
            request_id = get_request_id() or '-'
            self._access_logger.info(
                '"%s %s %s" %s %dms request_id=%s',
                method,
                path,
                proto,
                status,
                elapsed_ms,
                request_id,
            )
        except Exception:
            pass
        return response
