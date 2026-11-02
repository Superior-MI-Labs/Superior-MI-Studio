"""Current release identifies one version across all user-facing entrypoints."""
from pathlib import Path
import unittest
from install_linux import BASENAME, VERSION

ROOT = Path(__file__).resolve().parents[1]

class ReleaseVersionMetadataTests(unittest.TestCase):
    def test_authoritative_version_is_consistent(self):
        self.assertEqual(ROOT.name, BASENAME)
        self.assertTrue((ROOT/'README.md').read_text().startswith(
            '# Superior MI Python Visual Programming Lab '+VERSION))
        self.assertIn('Visual Programming Lab '+VERSION.removeprefix('v'),
                      (ROOT/'studio_native/gui.py').read_text())
        self.assertIn('VERSION='+VERSION,
                      (ROOT/'INSTALL-AND-REPORT.sh').read_text())
        self.assertTrue((ROOT/'CODEX-START-HERE.md').read_text().startswith(
            '# Codex start here — Superior MI Studio '+VERSION))
        self.assertIn('**Source candidate:** '+VERSION,
                      (ROOT/'docs/agents/NEXT-TASKS.md').read_text())

if __name__ == '__main__':
    unittest.main()
