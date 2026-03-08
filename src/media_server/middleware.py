import time
import logging

from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger('media_server.middleware')


class SecurityHeadersMiddleware(MiddlewareMixin):
    """Добавляет заголовки безопасности к ответам."""

    def process_response(self, request, response):
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response


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
