"""Linux handoff contract: native qualification gates interactive launch."""
import io
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
import zipfile


REPO = Path(__file__).resolve().parents[1]
NAME = 'Superior-MI-Python-Visual-Programming-Lab'
from install_linux import VERSION  # One release-version authority, not a copied fixture value


class DeliveryLaunchTests(unittest.TestCase):
    def run_delivery(self, installer_exit):
        with tempfile.TemporaryDirectory(prefix='studio-delivery-') as folder:
            home = Path(folder)
            downloads = home / 'Downloads'
            downloads.mkdir()
            app = home / 'Projects' / f'{NAME}-{VERSION}'
            app.mkdir(parents=True)
            # The sandboxed installer only simulates its exit status. The real
            # ZIP validation and native Qt gate remain exercised on the host.
            archive = downloads / f'{NAME}-{VERSION}.zip'
            with zipfile.ZipFile(archive, 'w') as zf:
                zf.writestr(f'{NAME}-{VERSION}/install_linux.py',
                    'import io,os,sys,tarfile\n'
                    'from pathlib import Path\n'
                    'out=Path.home()/"Downloads"/"SMI-NodeLab-Logs"/"qualification-demo.tar.gz"\n'
                    'with tarfile.open(out,"w:gz") as tf:\n'
                    '    data=b"qualification evidence retained\\n"\n'
                    '    info=tarfile.TarInfo("qualification-demo/report.txt")\n'
                    '    info.size=len(data)\n'
                    '    tf.addfile(info,io.BytesIO(data))\n'
                    'sys.exit(int(os.environ["SMI_TEST_INSTALL_EXIT"]))\n')
            launcher = app / 'launch-linux.sh'
            launcher.write_text('#!/usr/bin/env bash\n'
                                '[[ -f "$HOME/Downloads/SMI-NodeLab-Extracted/qualification-demo/qualification-demo/report.txt" ]] || exit 7\n'
                                'printf "launched\\n" > "$HOME/launched"\n')
            logdir = downloads / 'SMI-NodeLab-Logs'
            logdir.mkdir()
            data = b'qualification evidence retained\n'
            with tarfile.open(logdir / 'qualification-old.tar.gz', 'w:gz') as tf:
                info = tarfile.TarInfo('qualification-demo/report.txt')
                info.size = len(data)
                tf.addfile(info, io.BytesIO(data))
            env = os.environ.copy()
            env.update(HOME=str(home), SMI_TEST_INSTALL_EXIT=str(installer_exit))
            result = subprocess.run(['bash', str(REPO / 'INSTALL-AND-REPORT.sh')],
                                    env=env, capture_output=True, text=True, timeout=15)
            launched = (home / 'launched').exists()
            extracted = (downloads / 'SMI-NodeLab-Extracted' /
                         'qualification-demo' / 'qualification-demo' / 'report.txt').exists()
            return result, launched, extracted

    def test_native_pass_extracts_report_then_launches_existing_app(self):
        result, launched, extracted = self.run_delivery(0)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(extracted)
        self.assertTrue(launched)
        self.assertIn('Opening Superior MI Studio', result.stdout)

    def test_native_failure_preserves_report_and_does_not_launch(self):
        result, launched, extracted = self.run_delivery(17)
        self.assertEqual(result.returncode, 17, result.stderr)
        self.assertTrue(extracted)
        self.assertFalse(launched)
        self.assertNotIn('Opening Superior MI Studio', result.stdout)


if __name__ == '__main__':
    unittest.main()
