"""WEB releases fall back to Spotify artwork found by Harmony's barcode lookup."""
import threading
import unittest
from pathlib import Path
from unittest import mock
import tempfile

from test_audio_safety import mcc

HARMONY_PAGE = ('<html><head><title>The Radio Kid – Harmony</title></head><body>'
                '<a href="https://open.spotify.com/album/0vE03CNfZiYeF0qrdUhoQ1">x</a>'
                '<tr><th>GTIN</th><td>859704466090</td></tr>'
                '<figure class="cover-image"><a href="https://i.scdn.co/image/ab67616d0000b27305872d86729c8d72641ac0fd">'
                '</a></figure></body></html>').encode()
JPEG = b"\xff\xd8\xff\xc0\x00\x11\x08\x05\xa0\x05\xa0\x03\x01\x22\x00\x02\x11\x01\x03\x11\x01" + b"\x00" * 60 + b"\xff\xd9"


class HarmonyCover(unittest.TestCase):
    def test_largest_spotify_cover_for_matching_barcode_and_title(self):
        requested = []

        def respond(url, hosts, maximum=None):
            requested.append(url)
            return HARMONY_PAGE if "harmony" in url else JPEG

        with mock.patch.object(mcc, "_cover_request", respond):
            cover, _ = mcc._cover_spotify_harmony("859704466090", "The Radio Kid", threading.Event())
        self.assertEqual(cover["provider"], "Spotify via Harmony")
        self.assertEqual(cover["size"], "1440x1440")
        self.assertEqual(requested[1], "https://i.scdn.co/image/ab67616d000082c105872d86729c8d72641ac0fd")

    def test_other_title_is_rejected(self):
        with mock.patch.object(mcc, "_cover_request", lambda url, hosts, maximum=None: HARMONY_PAGE):
            cover, _ = mcc._cover_spotify_harmony("859704466090", "Something Else Entirely", threading.Event())
        self.assertIsNone(cover)

    def test_cd_release_is_recognised(self):
        with tempfile.TemporaryDirectory() as folder:
            release = Path(folder) / "2004 - Album [859704466090]"
            release.mkdir()
            self.assertFalse(mcc._folder_is_cd_release(release))
            (release / "Album.cue").write_text("FILE x")
            self.assertTrue(mcc._folder_is_cd_release(release))


if __name__ == "__main__":
    unittest.main()
