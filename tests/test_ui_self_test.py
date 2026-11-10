"""The embedded --ui-self-test contract of the latest app file must pass."""
import subprocess
import sys
import unittest

from test_audio_safety import SOURCE, ROOT


class UiSelfTest(unittest.TestCase):
    def test_embedded_ui_parity_contract_passes(self):
        result = subprocess.run(
            [sys.executable, str(SOURCE), '--ui-self-test'],
            cwd=ROOT, capture_output=True, text=True, timeout=300, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('UI parity contract passed', result.stdout)


if __name__ == '__main__':
    unittest.main()
