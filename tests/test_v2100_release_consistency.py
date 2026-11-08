"""Release metadata is a contract; no stale quick-install command in README."""
import re
import unittest
from pathlib import Path

from install_linux import BASENAME, VERSION

ROOT=Path(__file__).resolve().parents[1]


class ReleaseConsistencyTests(unittest.TestCase):
    def test_public_documentation_links_authoritative_release_pipeline(self):
        readme=(ROOT/'README.md').read_text()
        pipeline=(ROOT/'docs/RELEASE-PIPELINE.md').read_text()
        script=(ROOT/'INSTALL-AND-REPORT.sh').read_text()
        gui=(ROOT/'studio_native/gui.py').read_text()
        self.assertIn('docs/RELEASE-PIPELINE.md', readme)
        self.assertIn('install_linux.py', pipeline)
        self.assertIn('scripts/build_release.py', pipeline)
        self.assertIn('RUN-ALL.sh', pipeline)
        self.assertIn(f'Visual Programming Lab {VERSION.removeprefix("v")}', gui)
        self.assertIn(f'VERSION={VERSION}', script)
        self.assertIn('unzip -p "$ZIP" "$NAME-$VERSION/install_linux.py"', script)
        self.assertIn('python3 "$INSTALLER" "$ZIP" --no-launch', script)
        self.assertIn('bash "$APP/launch-linux.sh"', script)
        self.assertIn('-newer "$REPORT_MARKER"', script)
        self.assertNotIn(f'bash ~/Downloads/SMI-Studio-{VERSION}-install.sh', readme)



if __name__=='__main__':
    unittest.main()
