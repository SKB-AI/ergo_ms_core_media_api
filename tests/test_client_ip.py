"""Юнит-тесты resolve_client_ip / trusted proxies (С3)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

MEDIA_SRC = Path(__file__).resolve().parents[1] / 'src'
if str(MEDIA_SRC) not in sys.path:
    sys.path.insert(0, str(MEDIA_SRC))

from media_server.client_ip import (  # noqa: E402
    is_private_or_loopback,
    parse_trusted_proxies,
    resolve_client_ip,
)


class _Req:
    def __init__(self, remote: str, xff: str = ''):
        self.META = {'REMOTE_ADDR': remote}
        if xff:
            self.META['HTTP_X_FORWARDED_FOR'] = xff


def _internal_ip_allowed(remote: str, xff: str, trusted: list[str]) -> bool:
    """Тот же критерий IP, что в _is_internal_authorized (ключ считаем валидным)."""
    return is_private_or_loopback(resolve_client_ip(_Req(remote, xff), trusted_proxies=trusted))


class ResolveClientIpTests(unittest.TestCase):
    def test_empty_trusted_ignores_xff(self):
        req = _Req('8.8.8.8', xff='10.0.0.1')
        self.assertEqual(resolve_client_ip(req, trusted_proxies=[]), '8.8.8.8')

    def test_untrusted_peer_ignores_xff(self):
        req = _Req('8.8.8.8', xff='10.0.0.1')
        self.assertEqual(
            resolve_client_ip(req, trusted_proxies=['10.0.0.5']),
            '8.8.8.8',
        )

    def test_trusted_peer_uses_leftmost_xff(self):
        req = _Req('10.0.0.5', xff='10.0.0.1, 10.0.0.5')
        self.assertEqual(
            resolve_client_ip(req, trusted_proxies=['10.0.0.5']),
            '10.0.0.1',
        )

    def test_trusted_cidr(self):
        req = _Req('192.168.1.10', xff='10.0.0.1')
        self.assertEqual(
            resolve_client_ip(req, trusted_proxies=['192.168.0.0/16']),
            '10.0.0.1',
        )

    def test_trusted_peer_without_xff_uses_remote(self):
        req = _Req('10.0.0.5')
        self.assertEqual(
            resolve_client_ip(req, trusted_proxies=['10.0.0.5']),
            '10.0.0.5',
        )

    def test_parse_skips_invalid(self):
        nets = parse_trusted_proxies(['10.0.0.1', 'not-an-ip', '10.0.0.0/8'])
        self.assertEqual(len(nets), 2)

    def test_is_private_or_loopback(self):
        self.assertTrue(is_private_or_loopback('10.0.0.1'))
        self.assertTrue(is_private_or_loopback('127.0.0.1'))
        self.assertTrue(is_private_or_loopback('::1'))
        self.assertFalse(is_private_or_loopback('8.8.8.8'))
        self.assertFalse(is_private_or_loopback(''))


class InternalAuthzSpoofTests(unittest.TestCase):
    """Прямой запрос с подделанным XFF и валидным ключом → отказ по IP."""

    def test_spoof_xff_from_public_remote_denied(self):
        # Acceptance: XFF=10.0.0.1 + valid key, untrusted REMOTE_ADDR → 403
        self.assertFalse(_internal_ip_allowed('8.8.8.8', '10.0.0.1', trusted=[]))

    def test_private_remote_allowed_when_xff_ignored(self):
        self.assertTrue(_internal_ip_allowed('10.0.0.8', '8.8.8.8', trusted=[]))

    def test_trusted_proxy_allows_private_xff_client(self):
        self.assertTrue(_internal_ip_allowed('10.0.0.5', '10.0.0.1', trusted=['10.0.0.5']))

    def test_trusted_proxy_denies_public_xff_client(self):
        self.assertFalse(
            _internal_ip_allowed('10.0.0.5', '8.8.8.8', trusted=['10.0.0.5']),
        )


if __name__ == '__main__':
    unittest.main()
