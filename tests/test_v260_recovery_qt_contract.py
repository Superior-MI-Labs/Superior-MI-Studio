"""Guard the host regression without pretending headless tests can execute Qt.

This catches stale modal automation, accidental re-integration into the
stateful smoke process, and divergence between the shell and Python stage
selection. The actual native click and source publication remain host gates.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def function_source(path: Path, function_name: str) -> str:
    source = path.read_text(encoding='utf-8')
    tree = ast.parse(source)
    matches = [node for node in tree.body
               if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
               and node.name == function_name]
    if len(matches) != 1:
        raise AssertionError(f'Expected one function named {function_name}')
    return ast.get_source_segment(source, matches[0]) or ''


class RecoveryQtContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.smoke = ROOT / 'studio_native' / 'qt_smoke.py'
        cls.shell = ROOT / 'test-qt-offscreen.sh'
        cls.gui = ROOT / 'studio_native' / 'gui.py'

    def test_recovery_automation_uses_real_qmessagebox_buttons(self):
        body = function_source(self.smoke, 'exercise_source_recovery')
        # Calling QDialog.done(Yes.value) bypasses the QMessageBox button path;
        # the previous host test could report a visible prompt without proving
        # that QMessageBox.question() received a Yes selection.
        self.assertIn('dialog.button(QMessageBox.StandardButton.Yes)', body)
        self.assertIn('dialog.button(QMessageBox.StandardButton.Ok)', body)
        self.assertGreaterEqual(body.count('button.click()'), 2)
        self.assertNotIn('dialog.done(', body)
        self.assertNotIn('dialog.accept()', body)

    def test_recovery_isolation_has_a_separate_process_and_pass_gate(self):
        shell = self.shell.read_text(encoding='utf-8')
        main = function_source(self.smoke, 'main')
        self.assertIn('env SMI_QT_RECOVERY_ONLY=1 bash', shell)
        self.assertIn('bash "$APP/launch-linux.sh" --qt-smoke', shell)
        self.assertIn('NATIVE_QT_DOCUMENT_PASS', shell)
        self.assertIn('NATIVE_QT_SMOKE_PASS', shell)
        self.assertIn('SMI_QT_RECOVERY_ONLY', main)
        self.assertIn('NATIVE_QT_RECOVERY_PASS', main)
        self.assertIn('NATIVE_QT_SMOKE_PASS', main)
        self.assertEqual(main.count('exercise_source_recovery(app)'), 1)

    def test_source_recovery_policy_checks_the_document_revision(self):
        body = self.gui.read_text(encoding='utf-8')
        tree = ast.parse(body)
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'NativeLab')
        fn = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == '_new_source_document')
        method = ast.get_source_segment(body, fn) or ''
        self.assertIn('session.restore_recovery(record)', method)
        self.assertIn('session.text!=record.text', method)
        self.assertIn('session.dirty', method)
        self.assertIn('decision==QMessageBox.StandardButton.Yes', method)

    def test_modal_supervisor_uses_active_modal_not_global_widget_scan(self):
        body = function_source(self.smoke, 'exercise_modal')
        self.assertIn('app.activeModalWidget()', body)
        self.assertNotIn('app.topLevelWidgets()', body)

    def _run_shell_with_fake_launcher(self, *, fail_recovery: bool, fail_document: bool = False, no_document_marker: bool = False):
        # Exercise the actual shell orchestrator, replacing only the Qt
        # launcher with a deterministic stub. No PyQt dependency is required.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copy2(self.shell, root / 'test-qt-offscreen.sh')
            launcher = root / 'launch-linux.sh'
            launcher.write_text("""#!/usr/bin/env bash
if [[ "${SMI_QT_RECOVERY_ONLY:-}" == 1 ]]; then
  echo 'FAKE_RECOVERY_PROCESS'
  echo 'NATIVE_QT_RECOVERY_PASS'
  if [[ "${SIMULATE_RECOVERY_FAILURE:-}" == 1 ]]; then exit 17; fi
elif [[ "${SMI_QT_DOCUMENT_ONLY:-}" == 1 ]]; then
  echo 'FAKE_DOCUMENT_PROCESS'
  if [[ "${SIMULATE_DOCUMENT_NO_MARKER:-}" != 1 ]]; then echo 'NATIVE_QT_DOCUMENT_PASS'; fi
  if [[ "${SIMULATE_DOCUMENT_FAILURE:-}" == 1 ]]; then exit 19; fi
elif [[ "${SMI_QT_PROGRAM_ONLY:-}" == 1 ]]; then
  echo 'FAKE_PROGRAM_PROCESS'
  echo 'NATIVE_QT_PROGRAM_PASS'
else
  echo 'FAKE_INTEGRATION_PROCESS' 
  echo 'NATIVE_QT_SMOKE_PASS'
fi
""", encoding='utf-8')
            env = dict(os.environ)
            env.pop('SMI_RECOVERY_DIR', None)
            env['SIMULATE_RECOVERY_FAILURE'] = '1' if fail_recovery else '0'
            env['SIMULATE_DOCUMENT_FAILURE'] = '1' if fail_document else '0'
            env['SIMULATE_DOCUMENT_NO_MARKER'] = '1' if no_document_marker else '0'
            return subprocess.run(['bash', str(root / 'test-qt-offscreen.sh')],
                                  cwd=root, env=env, text=True,
                                  capture_output=True, check=False)

    def test_shell_runs_both_isolated_stages_in_order(self):
        run = self._run_shell_with_fake_launcher(fail_recovery=False)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn('FAKE_RECOVERY_PROCESS', run.stdout)
        self.assertIn('FAKE_DOCUMENT_PROCESS', run.stdout)
        self.assertIn('FAKE_PROGRAM_PROCESS', run.stdout)
        self.assertIn('FAKE_INTEGRATION_PROCESS', run.stdout)
        self.assertLess(run.stdout.index('FAKE_RECOVERY_PROCESS'),
                        run.stdout.index('FAKE_DOCUMENT_PROCESS'))
        self.assertLess(run.stdout.index('FAKE_DOCUMENT_PROCESS'),
                        run.stdout.index('FAKE_PROGRAM_PROCESS'))
        self.assertLess(run.stdout.index('FAKE_PROGRAM_PROCESS'),
                        run.stdout.index('FAKE_INTEGRATION_PROCESS'))

    def test_shell_blocks_integration_after_recovery_failure(self):
        run = self._run_shell_with_fake_launcher(fail_recovery=True)
        self.assertEqual(run.returncode, 17, run.stderr)
        self.assertIn('FAKE_RECOVERY_PROCESS', run.stdout)
        self.assertNotIn('FAKE_INTEGRATION_PROCESS', run.stdout)
        self.assertNotIn('FAKE_DOCUMENT_PROCESS', run.stdout)

    def test_document_failure_blocks_integration(self):
        run=self._run_shell_with_fake_launcher(fail_recovery=False,fail_document=True)
        self.assertEqual(run.returncode,19,run.stdout+run.stderr)
        self.assertIn('FAKE_RECOVERY_PROCESS',run.stdout)
        self.assertIn('FAKE_DOCUMENT_PROCESS',run.stdout)
        self.assertNotIn('FAKE_INTEGRATION_PROCESS',run.stdout)

    def test_missing_pass_marker_refuses_zero_exit(self):
        run=self._run_shell_with_fake_launcher(fail_recovery=False,no_document_marker=True)
        self.assertEqual(run.returncode,1,run.stdout+run.stderr)
        self.assertIn('QT_STAGE_FAILED document-subprocess missing=NATIVE_QT_DOCUMENT_PASS',run.stderr)
        self.assertNotIn('FAKE_INTEGRATION_PROCESS',run.stdout)

    def test_shell_keeps_recovery_private_and_retains_subprocess_failure(self):
        shell = self.shell.read_text(encoding='utf-8')
        self.assertIn('SMI_RECOVERY_DIR', shell)
        self.assertIn('mktemp -d', shell)
        self.assertIn('trap', shell)
        self.assertIn('|| exit $?', shell)


if __name__ == '__main__':
    unittest.main()
