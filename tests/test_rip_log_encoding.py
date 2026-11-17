"""A legacy ANSI rip log that the checker cannot decode is retried from a UTF-8 copy."""
import tempfile
import unittest
from pathlib import Path

from test_audio_safety import mcc


def fake_score_log(path):
    try:
        path.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        return {"unrecognized": "Could not decode log file.", "flagged": False}
    return {"score": 100, "ripper": "EAC", "flagged": False, "unrecognized": False}


class RipLogEncoding(unittest.TestCase):
    def test_ansi_log_is_scored_after_reencoding(self):
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / "rip.log"
            log.write_bytes(b"Exact Audio Copy V1.3\r\nC:\\\xf0\xe8\xef\xfb\\01.wav\r\n")
            self.assertEqual(mcc.score_rip_log_file(fake_score_log, log)["score"], 100)


if __name__ == "__main__":
    unittest.main()
