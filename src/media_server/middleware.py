import logging

from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

from media_server.maintenance import MAINTENANCE_DETAIL, is_maintenance_enabled

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


class RequestLoggingMiddleware(MiddlewareMixin):
    """HTTP access в том же формате, что AccessLogMiddleware API."""

    _access_logger = logging.getLogger('django.server')

    def __init__(self, get_response):
        super().__init__(get_response)
        _silence_wsgi_runserver_access()

    def process_response(self, request, response):
        try:
            method = request.method or '-'
            # path без query — без риска утечки токенов из query string
            path = request.path or '/'
            proto = request.META.get('SERVER_PROTOCOL', 'HTTP/1.1')
            status = getattr(response, 'status_code', '-')
            self._access_logger.info('"%s %s %s" %s', method, path, proto, status)
        except Exception:
            pass
        return response
