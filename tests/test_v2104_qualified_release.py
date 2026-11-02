"""One existing verification pipeline, fail-closed ZIP publication."""
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import build_release


class QualifiedReleaseTests(unittest.TestCase):
    def test_uses_existing_gate_without_replacing_runner(self):
        with patch.object(build_release.subprocess, 'run') as run:
            build_release.qualify_headless()
        run.assert_called_once_with(
            ['bash', 'scripts/agent-verify.sh', '--headless'],
            cwd=build_release.ROOT, check=True)

    def test_failed_qualification_refuses_archive_publication(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'unqualified.zip'
            with (patch('sys.argv', ['build_release.py', '--output', str(output),
                                     '--qualify-headless']),
                  patch.object(build_release, 'qualify_headless',
                      side_effect=subprocess.CalledProcessError(9, 'agent-verify.sh'))):
                self.assertEqual(build_release.main(), 1)
            self.assertFalse(output.exists())

    def test_fails_closed_if_output_already_exists(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'release.zip'
            target.write_bytes(b'existing verified release')
            with self.assertRaises(FileExistsError):
                build_release.build(target)
            self.assertEqual(target.read_bytes(), b'existing verified release')

if __name__ == '__main__':
    unittest.main()
