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
_QUOTA_SLUG_RE = re.compile(r'^[a-z][a-z0-9_]{0,62}$')
_RESERVED = frozenset({'user', 'admin'})
_WINDOWS = {'second': 1.0, 'minute': 60.0, 'hour': 3600.0, 'day': 86400.0}

_lock = Lock()
_hits: dict[str, list[float]] = defaultdict(list)


def parse_rate(rate: str) -> tuple[int, float]:
    match = _RATE_RE.match((rate or '').strip().lower())
    if not match:
        return 30, 60.0
    count = int(match.group(1))
    unit = match.group(2)
    return count, _WINDOWS.get(unit, 60.0)


def _rate_per_second(rate: str) -> float:
    limit, window = parse_rate(rate)
    if window <= 0:
        return 0.0
    return limit / window


def upload_rate_ceiling() -> str:
    raw = str(getattr(settings, 'MEDIA_API_UPLOAD_RATE_CEILING', '1000/minute') or '').strip()
    if _RATE_RE.match(raw.lower()):
        return raw
    return '1000/minute'


def cap_rate_to_ceiling(rate: str) -> str:
    ceiling = upload_rate_ceiling()
    if not _RATE_RE.match((rate or '').strip().lower()):
        return ceiling
    if _rate_per_second(rate) > _rate_per_second(ceiling):
        return ceiling
    return rate.strip()


def rate_for_quota(quota: str) -> str:
    quota_norm = (quota or 'user').strip().lower()
    if quota_norm == 'admin':
        return getattr(settings, 'MEDIA_API_UPLOAD_RATE_ADMIN', '120/minute')
    return getattr(settings, 'MEDIA_API_UPLOAD_RATE', '30/minute')


def _quota_denied_response(retry_after: float | int) -> JsonResponse:
    response = JsonResponse({'error': 'Слишком много запросов на загрузку'}, status=429)
    response['Retry-After'] = str(max(int(retry_after), 1))
    return response


def check_upload_quota(
    *,
    user_id,
    quota: str = 'user',
    rate: str | None = None,
) -> JsonResponse | None:
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

    quota_norm = (quota or 'user').strip().lower()
    if quota_norm in _RESERVED:
        limit, window = parse_rate(rate_for_quota(quota_norm))
    elif _QUOTA_SLUG_RE.match(quota_norm) and rate:
        limit, window = parse_rate(cap_rate_to_ceiling(str(rate)))
    else:
        quota_norm = 'user'
        limit, window = parse_rate(rate_for_quota('user'))

    if uid <= 0:
        return _quota_denied_response(window)
    key = f'{quota_norm}:{uid}'
    now = time.time()
    cutoff = now - window

    with _lock:
        bucket = _hits[key]
        _hits[key] = [ts for ts in bucket if ts > cutoff]
        if len(_hits[key]) >= limit:
            oldest = min(_hits[key])
            retry_after = max(int(oldest + window - now) + 1, 1)
            logger.warning(
                'Upload quota exceeded: user_id=%s quota=%s limit=%s',
                uid,
                quota_norm,
                limit,
            )
            return _quota_denied_response(retry_after)
        _hits[key].append(now)

    return None


def reset_upload_quota_for_tests() -> None:
    """Сброс счётчиков (только тесты)."""
    with _lock:
        _hits.clear()
