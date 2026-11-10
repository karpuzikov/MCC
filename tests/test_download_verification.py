"""Pinned dependency downloads are refused unless their SHA-256 matches."""
import hashlib
from pathlib import Path
import tempfile
import unittest

from test_audio_safety import mcc


class DownloadVerification(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / 'source.zip'
        self.source.write_bytes(b'pinned dependency archive')
        self.destination = Path(self.temp.name) / 'downloaded.zip'

    def test_matching_hash_keeps_the_download(self):
        expected = hashlib.sha256(self.source.read_bytes()).hexdigest()
        mcc._download_verified_archive(self.source.as_uri(), self.destination, expected)
        self.assertEqual(self.destination.read_bytes(), self.source.read_bytes())

    def test_mismatched_hash_raises_and_deletes_the_download(self):
        with self.assertRaisesRegex(RuntimeError, 'SHA-256 mismatch'):
            mcc._download_verified_archive(self.source.as_uri(), self.destination, '0' * 64)
        self.assertFalse(self.destination.exists())

    def test_pinned_hashes_are_well_formed_sha256_values(self):
        for name in ('CHROMAPRINT_ZIP_SHA256', 'FFMPEG_ZIP_SHA256'):
            with self.subTest(pin=name):
                value = getattr(mcc, name)
                self.assertRegex(value, r'^[0-9a-f]{64}$')


if __name__ == '__main__':
    unittest.main()
