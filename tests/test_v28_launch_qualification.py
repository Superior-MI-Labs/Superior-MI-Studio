"""Regression checks for the Linux wrapper and failure evidence protocol.

No PyQt6, package manager, or desktop display required. The test substitutes
only shell entrypoints in a disposable application directory, never production
source or user files.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1]


class LinuxQualificationShellTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='smi-launch-tests-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.app = self.root / 'app with spaces'
        self.app.mkdir()
        shutil.copy2(PROJECT / 'RUN-ALL.sh', self.app / 'RUN-ALL.sh')
        self.logs = self.root / 'logs with spaces'
        self.env = os.environ.copy()
        self.env['SMI_LOG_DIR'] = str(self.logs)
        self.env['SMI_LAUNCH_SENTINEL'] = str(self.root / 'launched')

    def stub(self, name: str, body: str):
        (self.app / name).write_text('#!/usr/bin/env bash\n' + body, encoding='utf-8')

    def run_all(self, *args: str):
        return subprocess.run(['bash', str(self.app / 'RUN-ALL.sh'), *args],
                              env=self.env, text=True, capture_output=True, timeout=15)

    def reports(self):
        return sorted(x for x in self.logs.glob('qualification-*') if x.is_dir())

    def test_success_writes_both_logs_and_screenshots_without_launch(self):
        self.stub('doctor.sh', 'echo doctor-success\n')
        self.stub('test-qt-offscreen.sh',
                  'echo qt-success\nprintf image > "$1"\n'
                  'printf return-image > "$SMI_QT_RETURN_SCREENSHOT"\n'
                  'printf nested-image > "$SMI_QT_NESTED_SCREENSHOT"\n'
                  'printf early-image > "$SMI_QT_EARLY_EXIT_SCREENSHOT"\n')
        self.stub('launch-linux.sh', 'touch "$SMI_LAUNCH_SENTINEL"\n')
        result = self.run_all()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('CHECKS_PASS', result.stdout)
        self.assertFalse((self.root / 'launched').exists())
        report, = self.reports()
        self.assertIn('doctor-success', (report / 'doctor.log').read_text())
        self.assertIn('qt-success', (report / 'qt.log').read_text())
        self.assertTrue((report / 'qt-smoke.png').exists())
        self.assertTrue((report / 'return-boundary.png').exists())
        self.assertTrue((report / 'nested-boundary.png').exists())
        self.assertTrue((report / 'early-exit.png').exists())
        self.assertTrue(Path(str(report) + '.tar.gz').exists())

    def test_launch_only_after_complete_qualification(self):
        self.stub('doctor.sh', 'echo ok\n')
        self.stub('test-qt-offscreen.sh', 'echo ok\n')
        self.stub('launch-linux.sh', 'touch "$SMI_LAUNCH_SENTINEL"\n')
        result = self.run_all('--launch')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.root / 'launched').exists())

    def test_failure_keeps_logs_and_parent_shell_alive(self):
        self.stub('doctor.sh', 'echo failure-from-doctor >&2\nexit 23\n')
        self.stub('test-qt-offscreen.sh', 'echo failure-from-qt >&2\nexit 24\n')
        self.stub('launch-linux.sh', 'touch "$SMI_LAUNCH_SENTINEL"\n')
        # A caller can protect the failure; RUN-ALL does not modify its shell.
        # The first test deliberately exercises both failures for diagnostic coverage.
        result = self.run_all('--launch')
        self.assertEqual(result.returncode, 1)
        self.assertIn('CHECKS_FAILED_OR_UNAVAILABLE_REVIEW_REQUIRED', result.stdout)
        self.assertIn('failure-from-doctor', result.stdout)
        self.assertIn('failure-from-qt', result.stdout)
        self.assertFalse((self.root / 'launched').exists())
        report, = self.reports()
        self.assertEqual((report / 'doctor.log').read_text().strip(), 'failure-from-doctor')
        self.assertEqual((report / 'qt.log').read_text().strip(), 'failure-from-qt')
        self.assertTrue(Path(str(report) + '.tar.gz').exists())
        caller = subprocess.run(['bash', '-c', 'set -e; bash "$1" --launch || :; echo SHELL_ALIVE',
                                 'outer', str(self.app / 'RUN-ALL.sh')],
                                env=self.env, capture_output=True, text=True, timeout=15)
        self.assertEqual(caller.returncode, 0)
        self.assertIn('SHELL_ALIVE', caller.stdout)

    def test_qt_traceback_refuses_false_success_and_preserves_evidence(self):
        self.stub('doctor.sh', 'echo doctor-success\n')
        # Reproduce v2.42: PyQt prints an uncaught slot traceback but the
        # subprocess still returns zero and prints a misleading PASS marker.
        self.stub('test-qt-offscreen.sh',
                  "printf '%s\\n' 'Traceback (most recent call last):' "
                  "'AttributeError: missing canvas contract' 'NATIVE_QT_SMOKE_PASS' >&2\n"
                  'exit 0\n')
        self.stub('launch-linux.sh', 'touch "$SMI_LAUNCH_SENTINEL"\n')
        result=self.run_all('--launch')
        self.assertEqual(result.returncode,1,result.stdout+result.stderr)
        self.assertIn('QT: Uncaught Python callback traceback detected',result.stdout)
        self.assertIn('CHECKS_FAILED_OR_UNAVAILABLE_REVIEW_REQUIRED',result.stdout)
        self.assertFalse((self.root/'launched').exists())
        report,=self.reports()
        self.assertIn('Traceback (most recent call last):',(report/'qt.log').read_text())
        self.assertTrue(Path(str(report)+'.tar.gz').exists())

    def test_headless_mode_skips_qt_and_unknown_flags_refuse(self):
        self.stub('doctor.sh', 'echo doctor-success\n')
        self.stub('test-qt-offscreen.sh', 'echo should-not-run\nexit 33\n')
        self.stub('launch-linux.sh', 'exit 0\n')
        result = self.run_all('--headless')
        self.assertEqual(result.returncode, 0)
        self.assertIn('QT: SKIPPED', result.stdout)
        report, = self.reports()
        self.assertFalse((report / 'qt.log').exists())
        invalid = self.run_all('--oops')
        self.assertEqual(invalid.returncode, 2)
        self.assertEqual(len(self.reports()), 1)

    def test_scripts_have_valid_bash_syntax_and_onesource_qt_selection(self):
        for name in ('RUN-ALL.sh', 'launch-linux.sh', 'test-qt-offscreen.sh',
                     'doctor.sh', 'install-desktop-shortcut.sh'):
            result = subprocess.run(['bash', '-n', str(PROJECT / name)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, (name, result.stderr))
        smoke_script = (PROJECT / 'test-qt-offscreen.sh').read_text()
        self.assertIn('launch-linux.sh', smoke_script)
        self.assertNotIn('from PyQt6 import', smoke_script)
        self.assertNotIn('exec python', (PROJECT / 'launch-linux.sh').read_text())


if __name__ == '__main__':
    unittest.main()
