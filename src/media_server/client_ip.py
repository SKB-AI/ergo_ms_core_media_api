"""Клиентский IP с учётом MEDIA_API_TRUSTED_PROXIES.

X-Forwarded-For учитывается только если TCP-пир (REMOTE_ADDR) входит
в список доверенных прокси (IP или CIDR). Пустой список — всегда REMOTE_ADDR.
"""

from __future__ import annotations

import ipaddress
from typing import Iterable, Sequence

_TrustedEntry = ipaddress.IPv4Network | ipaddress.IPv6Network


def parse_trusted_proxies(raw: Iterable[str] | None) -> tuple[_TrustedEntry, ...]:
    """Разбор списка IP/CIDR. Некорректные элементы пропускаются."""
    if not raw:
        return ()
    result: list[_TrustedEntry] = []
    for item in raw:
        text = (item or '').strip()
        if not text:
            continue
        try:
            result.append(ipaddress.ip_network(text, strict=False))
        except ValueError:
            continue
    return tuple(result)


def _as_networks(
    trusted_proxies: Iterable[str] | Sequence[_TrustedEntry] | None,
) -> tuple[_TrustedEntry, ...]:
    if not trusted_proxies:
        return ()
    first = next(iter(trusted_proxies), None)
    if first is None:
        return ()
    if isinstance(first, (ipaddress.IPv4Network, ipaddress.IPv6Network)):
        return tuple(trusted_proxies)  # type: ignore[arg-type]
    return parse_trusted_proxies(trusted_proxies)  # type: ignore[arg-type]


def _ip_in_networks(ip_str: str, networks: Sequence[_TrustedEntry]) -> bool:
    if not ip_str or not networks:
        return False
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return any(addr in net for net in networks)


def is_private_or_loopback(ip: str) -> bool:
    if not ip:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return ip in ('localhost',)
    return bool(addr.is_private or addr.is_loopback or addr.is_link_local)


def resolve_client_ip(
    request,
    trusted_proxies: Iterable[str] | Sequence[_TrustedEntry] | None = None,
) -> str:
    """
    Клиентский IP для authz и rate-limit.

    Если trusted_proxies пуст или REMOTE_ADDR не в списке — XFF игнорируется.
    Если пир доверен — берётся крайний левый адрес из X-Forwarded-For (если есть).
    """
    remote = (getattr(request, 'META', {}) or {}).get('REMOTE_ADDR') or ''
    remote = str(remote).strip()

    if trusted_proxies is None:
        from django.conf import settings
        trusted_proxies = getattr(settings, 'MEDIA_API_TRUSTED_PROXIES', None) or ()

    networks = _as_networks(trusted_proxies)
    if not networks or not _ip_in_networks(remote, networks):
        return remote

    forwarded = (getattr(request, 'META', {}) or {}).get('HTTP_X_FORWARDED_FOR', '') or ''
    parts = [p.strip() for p in str(forwarded).split(',') if p.strip()]
    if parts:
        return parts[0]
    return remote
