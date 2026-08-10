"""Квота частоты загрузок по user_id и классу из upload-токена."""

from __future__ import annotations

import logging
import re
import time
from collections import defaultdict
from threading import Lock

from django.conf import settings
from django.http import JsonResponse

logger = logging.getLogger('media_server.upload_quota')

_RATE_RE = re.compile(r'^(\d+)/(second|minute|hour|day)$')

_lock = Lock()
_hits: dict[str, list[float]] = defaultdict(list)


def parse_rate(rate: str) -> tuple[int, float]:
    match = _RATE_RE.match((rate or '').strip().lower())
    if not match:
        return 30, 60.0
    count = int(match.group(1))
    unit = match.group(2)
    windows = {'second': 1.0, 'minute': 60.0, 'hour': 3600.0, 'day': 86400.0}
    return count, windows.get(unit, 60.0)


def rate_for_quota(quota: str) -> str:
    quota_norm = (quota or 'user').strip().lower()
    if quota_norm == 'admin':
        return getattr(settings, 'MEDIA_API_UPLOAD_RATE_ADMIN', '120/minute')
    return getattr(settings, 'MEDIA_API_UPLOAD_RATE', '30/minute')


def check_upload_quota(*, user_id, quota: str = 'user') -> JsonResponse | None:
    """
    Учесть одну загрузку. None — можно продолжать; JsonResponse 429 — отказ.
    В DEBUG не ограничивает (как прежний middleware).
    """
    if getattr(settings, 'DEBUG', False):
        return None

    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        uid = 0
    if uid <= 0:
        return JsonResponse({'error': 'Слишком много запросов на загрузку'}, status=429)

    quota_norm = (quota or 'user').strip().lower()
    if quota_norm not in ('user', 'admin'):
        quota_norm = 'user'

    limit, window = parse_rate(rate_for_quota(quota_norm))
    key = f'{quota_norm}:{uid}'
    now = time.time()
    cutoff = now - window

    with _lock:
        bucket = _hits[key]
        _hits[key] = [ts for ts in bucket if ts > cutoff]
        if len(_hits[key]) >= limit:
            logger.warning(
                'Upload quota exceeded: user_id=%s quota=%s limit=%s',
                uid,
                quota_norm,
                limit,
            )
            return JsonResponse({'error': 'Слишком много запросов на загрузку'}, status=429)
        _hits[key].append(now)

    return None


def reset_upload_quota_for_tests() -> None:
    """Сброс счётчиков (только тесты)."""
    with _lock:
        _hits.clear()
