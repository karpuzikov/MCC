"""Scan evidence survives an app update; only a schema change discards it."""
import json
import tempfile
import unittest
from pathlib import Path

from test_audio_safety import mcc


class ScanCacheAcrossVersions(unittest.TestCase):
    def test_older_app_version_cache_is_reused(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "scan-analysis.json"
            payload = {"schema": mcc._SCAN_EVIDENCE_SCHEMA, "version": "0.0.1",
                       "releases": {"r": {"attributes": {}, "tracks": {}, "rip_logs": {}}}, "pairs": {}}
            path.write_text(json.dumps(payload), encoding="utf-8")
            self.assertIn("r", mcc.ScanCache(path=path).saved_releases)
            payload["schema"] += 1
            path.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(mcc.ScanCache(path=path).saved_releases, {})


if __name__ == "__main__":
    unittest.main()
