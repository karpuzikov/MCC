"""ffprobe tags (CJK) must be decoded as UTF-8, not with the Windows code page."""
import json
import unittest
from pathlib import Path

from test_audio_safety import mcc


class FfprobeUtf8(unittest.TestCase):
    def test_probe_track_decodes_ffprobe_output_as_utf8(self):
        seen = {}
        original = mcc.run_hidden

        def fake(cmd, **kwargs):
            seen.update(kwargs)
            payload = json.dumps({"format": {"duration": "1", "tags": {"album": "乐队的夏天2"}}, "streams": []})
            return type("Result", (), {"returncode": 0, "stdout": payload, "stderr": ""})()

        mcc.run_hidden = fake
        try:
            track = mcc.Track(path=Path("x.flac"), release_id=0, index=0)
            mcc.probe_track("ffprobe", track)
        finally:
            mcc.run_hidden = original
        self.assertEqual(seen.get("encoding"), "utf-8")
        self.assertEqual(track.album, "乐队的夏天2")


if __name__ == "__main__":
    unittest.main()
