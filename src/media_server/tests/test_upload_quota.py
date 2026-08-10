"""Квота загрузок по user_id и классу из токена."""

from __future__ import annotations

import json
import os
import unittest

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'media_server.settings')

import django

django.setup()

from django.test import override_settings

from media_server.upload_quota import (
    check_upload_quota,
    rate_for_quota,
    reset_upload_quota_for_tests,
)


class UploadQuotaTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_upload_quota_for_tests()

    def tearDown(self) -> None:
        reset_upload_quota_for_tests()

    def test_rate_for_quota_selects_env(self) -> None:
        with override_settings(
            MEDIA_API_UPLOAD_RATE='15/minute',
            MEDIA_API_UPLOAD_RATE_ADMIN='60/minute',
        ):
            self.assertEqual(rate_for_quota('user'), '15/minute')
            self.assertEqual(rate_for_quota('admin'), '60/minute')
            self.assertEqual(rate_for_quota('other'), '15/minute')

    @override_settings(
        DEBUG=False,
        MEDIA_API_UPLOAD_RATE='2/minute',
        MEDIA_API_UPLOAD_RATE_ADMIN='5/minute',
    )
    def test_user_quota_returns_429(self) -> None:
        self.assertIsNone(check_upload_quota(user_id=7, quota='user'))
        self.assertIsNone(check_upload_quota(user_id=7, quota='user'))
        denied = check_upload_quota(user_id=7, quota='user')
        self.assertIsNotNone(denied)
        self.assertEqual(denied.status_code, 429)
        self.assertIn('загрузку', json.loads(denied.content.decode('utf-8'))['error'])

    @override_settings(
        DEBUG=False,
        MEDIA_API_UPLOAD_RATE='1/minute',
        MEDIA_API_UPLOAD_RATE_ADMIN='3/minute',
    )
    def test_admin_quota_independent_of_user(self) -> None:
        self.assertIsNone(check_upload_quota(user_id=7, quota='user'))
        denied_user = check_upload_quota(user_id=7, quota='user')
        self.assertEqual(denied_user.status_code, 429)
        # тот же user_id с admin-квотой — отдельный бакет
        self.assertIsNone(check_upload_quota(user_id=7, quota='admin'))
        self.assertIsNone(check_upload_quota(user_id=7, quota='admin'))
        self.assertIsNone(check_upload_quota(user_id=7, quota='admin'))
        denied_admin = check_upload_quota(user_id=7, quota='admin')
        self.assertEqual(denied_admin.status_code, 429)

    @override_settings(DEBUG=True, MEDIA_API_UPLOAD_RATE='1/minute')
    def test_debug_skips_quota(self) -> None:
        for _ in range(5):
            self.assertIsNone(check_upload_quota(user_id=1, quota='user'))


if __name__ == '__main__':
    unittest.main()
