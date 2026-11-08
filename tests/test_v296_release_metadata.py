"""Current release identifies one version across all user-facing entrypoints."""
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile
from install_linux import BASENAME, VERSION, validate_archive
from scripts.build_release import build

ROOT = Path(__file__).resolve().parents[1]

class ReleaseVersionMetadataTests(unittest.TestCase):
    def test_authoritative_version_is_consistent(self):
        # A source checkout has no packaging-specific directory-name contract.
        self.assertTrue((ROOT/'README.md').read_text().startswith('# Superior MI Studio'))
        self.assertIn('Visual Programming Lab '+VERSION.removeprefix('v'),
                      (ROOT/'studio_native/gui.py').read_text())
        self.assertIn('VERSION='+VERSION,
                      (ROOT/'INSTALL-AND-REPORT.sh').read_text())
        self.assertTrue((ROOT/'CODEX-START-HERE.md').read_text().startswith(
            '# Codex start here — Superior MI Studio '+VERSION))
        self.assertIn('**Source candidate:** '+VERSION,
                      (ROOT/'docs/agents/NEXT-TASKS.md').read_text())

    def test_arbitrarily_named_checkout_produces_exact_versioned_archive(self):
        # Positive proof for GitHub source checkouts AND a negative version
        # mismatch proof, without weakening the installer validation itself.
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'Superior-MI-Studio'
            source.mkdir()
            for name in ('install_linux.py','RUN-ALL.sh','launch-linux.sh',
                         'studio_native/navigation.py'):
                target=source/name
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(ROOT/name,target)
            output=Path(folder)/'candidate.zip'
            count,_=build(output,root=source)
            self.assertEqual(count,5)  # four source files plus manifest
            with zipfile.ZipFile(output) as archive:
                validate_archive(archive)
                self.assertIn(BASENAME+'/install_linux.py',archive.namelist())
                self.assertFalse(any(name.startswith(source.name+'/')
                                     for name in archive.namelist()))
                self.assertIn('install_linux.py',archive.read(
                    BASENAME+'/REPOSITORY-SHA256SUMS.txt').decode())
            # Source-folder spelling must not override the installer VERSION.
            installer=source/'install_linux.py'
            installer.write_text(installer.read_text().replace(
                "VERSION = '"+VERSION+"'", "VERSION = 'v999.99'"))
            with self.assertRaisesRegex(ValueError,'installer version'):
                build(Path(folder)/'wrong-version.zip',root=source)
            self.assertFalse((Path(folder)/'wrong-version.zip').exists())

if __name__ == '__main__':
    unittest.main()
