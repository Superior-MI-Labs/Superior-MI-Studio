"""Release metadata is a contract; no stale quick-install command in README."""
import re
import unittest
from pathlib import Path

from install_linux import BASENAME, VERSION

ROOT=Path(__file__).resolve().parents[1]


class ReleaseConsistencyTests(unittest.TestCase):
    def test_readme_installer_and_gui_title_reference_one_version(self):
        readme=(ROOT/'README.md').read_text()
        script=(ROOT/'INSTALL-AND-REPORT.sh').read_text()
        gui=(ROOT/'studio_native/gui.py').read_text()
        self.assertIn(f'Download only `{BASENAME}.zip`', readme)
        self.assertIn('There is **no separate `.sh` download**', readme)
        self.assertIn('bash <<\'BASH\'', readme)
        self.assertIn(f'VERSION="{VERSION}"', readme)
        self.assertIn('unzip -p "$ZIP" "$NAME-$VERSION/install_linux.py"', readme)
        self.assertIn('python3 "$INSTALLER" "$ZIP" --no-launch', readme)
        self.assertIn('bash "$APP/launch-linux.sh"', readme)
        self.assertIn('-newer "$REPORT_MARKER"', readme)
        self.assertNotIn(f'bash ~/Downloads/SMI-Studio-{VERSION}-install.sh', readme)



if __name__=='__main__':
    unittest.main()
