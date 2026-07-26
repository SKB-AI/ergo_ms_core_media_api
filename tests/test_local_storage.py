"""Юнит-тесты LocalFileStorage: sandbox и path traversal."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from media_server.storage.local import LocalFileStorage


class LocalFileStorageSandboxTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name) / 'media'
        self.root.mkdir(parents=True, exist_ok=True)
        self.storage = LocalFileStorage(str(self.root))

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_normal_relative_path(self):
        target = self.storage._resolve_path('avatars/user.jpg')
        self.assertTrue(str(target).startswith(str(self.root)))
        self.assertTrue(target.is_relative_to(self.root))

    def test_rejects_parent_segments(self):
        with self.assertRaises(PermissionError):
            self.storage._resolve_path('../secret.txt')
        with self.assertRaises(PermissionError):
            self.storage._resolve_path('avatars/../../secret.txt')

    def test_rejects_sibling_prefix_escape(self):
        # Классический обход startswith: .../media_evil при root .../media
        sibling = self.root.parent / f'{self.root.name}_evil'
        sibling.mkdir(parents=True, exist_ok=True)
        (sibling / 'secret.txt').write_text('x', encoding='utf-8')
        with self.assertRaises(PermissionError):
            self.storage._resolve_path(f'../{self.root.name}_evil/secret.txt')

    def test_rejects_absolute_path(self):
        with self.assertRaises(PermissionError):
            self.storage._resolve_path('/etc/passwd')


if __name__ == '__main__':
    unittest.main()
