"""An exact barcode match is accepted even when MusicBrainz adds a qualifier to the title."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_audio_safety import mcc


class BarcodeTitle(unittest.TestCase):
    def test_barcode_match_ignores_title_difference(self):
        detail = {"id": "rid-1", "title": "At Mosp Here (Fujiya & Miyagi Remix)", "barcode": "00602478199370",
                  "date": "2024-10-02", "media": [{"format": "Digital Media", "track-count": 1}],
                  "label-info": [{"catalog-number": "00602478199370"}],
                  "release-group": {"primary-type": "Single", "first-release-date": "2017-10-06"}}
        def fake(path, *args, **kwargs):
            return {"releases": [detail]} if path.startswith("release/?") else detail
        folder = Path(tempfile.mkdtemp()) / "2017-11-23 - AT MOSP HERE [602478199370]"
        folder.mkdir()
        track = folder / "01 At Mosp Here.flac"
        track.write_bytes(b"x")
        with patch.object(mcc, "mb_json", side_effect=fake):
            info = mcc.release_identity(folder, [track], default_artist="Re-TROS")
        self.assertTrue(info["metadata_verified"], info["notes"])


if __name__ == "__main__":
    unittest.main()
