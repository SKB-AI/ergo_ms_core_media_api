"""Юнит-тесты content_validation (С5)."""

from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

MEDIA_SRC = Path(__file__).resolve().parents[1] / 'src'
if str(MEDIA_SRC) not in sys.path:
    sys.path.insert(0, str(MEDIA_SRC))

from media_server.content_validation import (  # noqa: E402
    MODE_EXTENSION,
    MODE_EXTENSION_AND_MAGIC,
    MODE_EXTENSION_MAGIC_AV,
    ContentValidationError,
    scan_av,
    validate_bytes,
    validate_upload,
)

# Минимальный валидный PNG (сигнатура + IHDR + IEND).
_PNG = (
    b'\x89PNG\r\n\x1a\n'
    b'\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde'
    b'\x00\x00\x00\x00IEND\xaeB`\x82'
)
_HTML = b'<!DOCTYPE html><html><body>x</body></html>'
_PE = b'MZ' + b'\x00' * 60 + b'\x80\x00\x00\x00' + b'\x00' * 100


class ExtensionModeTests(unittest.TestCase):
    def test_allows_known_extension(self):
        result = validate_upload('photo.png', _HTML, mode=MODE_EXTENSION)
        self.assertTrue(result.ok)
        self.assertIsNone(result.sniffed)

    def test_rejects_unknown_extension(self):
        with self.assertRaises(ContentValidationError) as ctx:
            validate_upload('malware.exe', _PE, mode=MODE_EXTENSION)
        self.assertEqual(ctx.exception.status_code, 415)

    def test_allowed_types_subset(self):
        with self.assertRaises(ContentValidationError):
            validate_upload(
                'photo.png',
                _PNG,
                allowed_types=['jpg'],
                mode=MODE_EXTENSION,
            )

    def test_extension_mode_does_not_call_filetype(self):
        with patch('media_server.content_validation._sniff_extension') as sniff:
            validate_upload('a.png', _HTML, mode=MODE_EXTENSION)
            sniff.assert_not_called()


class MagicModeTests(unittest.TestCase):
    def test_real_png_ok(self):
        result = validate_upload('a.png', _PNG, mode=MODE_EXTENSION_AND_MAGIC)
        self.assertTrue(result.ok)
        self.assertEqual(result.sniffed, 'png')

    def test_html_as_png_rejected(self):
        with self.assertRaises(ContentValidationError) as ctx:
            validate_upload('a.png', _HTML, mode=MODE_EXTENSION_AND_MAGIC)
        self.assertEqual(ctx.exception.status_code, 415)

    def test_pe_as_png_rejected(self):
        with self.assertRaises(ContentValidationError):
            validate_bytes('uploads/a.png', _PE, mode=MODE_EXTENSION_AND_MAGIC)

    def test_fileobj_seek_restored(self):
        buf = io.BytesIO(_PNG)
        validate_upload('a.png', buf, mode=MODE_EXTENSION_AND_MAGIC)
        self.assertEqual(buf.tell(), 0)

    def test_svg_requires_svg_or_xml_sniff(self):
        svg = b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"></svg>'
        result = validate_bytes('icon.svg', svg, mode=MODE_EXTENSION_AND_MAGIC)
        self.assertTrue(result.ok)
        with self.assertRaises(ContentValidationError):
            validate_bytes('icon.svg', _HTML, mode=MODE_EXTENSION_AND_MAGIC)


class AvStubTests(unittest.TestCase):
    def test_av_mode_rejects_without_scanner(self):
        with self.assertLogs('media_server.content_validation', level='WARNING'):
            with self.assertRaises(ContentValidationError) as ctx:
                validate_bytes('a.png', _PNG, mode=MODE_EXTENSION_MAGIC_AV)
        self.assertEqual(ctx.exception.status_code, 503)

    def test_scan_av_returns_none(self):
        with self.assertLogs('media_server.content_validation', level='WARNING'):
            self.assertIsNone(scan_av(_PNG))


if __name__ == '__main__':
    unittest.main()
