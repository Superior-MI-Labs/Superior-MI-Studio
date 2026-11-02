"""Regression for v2.71's unowned dirty-graph close modal and stage pipe."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]

class QtStageOwnershipTests(unittest.TestCase):
    def test_last_program_stage_saves_incomplete_fixture_before_window_close(self):
        script=(ROOT/'studio_native/qt_smoke.py').read_text()
        region=script.split("print('QT_STAGE program-qualified-sequential-require'",1)[1].split('def main():',1)[0]
        self.assertIn('assert fresh_guard.save(path=incomplete_file)',region)
        self.assertIn('ProgramGraph.open(incomplete_file).state==fresh_guard.document.state',region)
        self.assertIn("if panel.document.dirty",region)
        self.assertIn('assert not pending',region)
        self.assertLess(region.index('assert not pending'),region.index('assert w.close()'))

    def test_stage_output_is_file_backed_not_pipe_backed(self):
        source=(ROOT/'test-qt-offscreen.sh').read_text()
        self.assertIn('> "$stage_log" 2>&1',source)
        self.assertIn('cat "$stage_log"',source)
        self.assertNotIn('| tee "$stage_log"',source)
        self.assertIn('QT_STAGE_FAILED',source)

    def test_detached_child_stdout_cannot_keep_stage_gate_open(self):
        # A subprocess can exit while an unrelated detached child still has
        # inherited stdout. The old tee pipeline waited for that child. The
        # new file-backed runner must return once all four stages exit.
        with tempfile.TemporaryDirectory() as directory:
            home=Path(directory)
            shutil.copy2(ROOT/'test-qt-offscreen.sh',home/'test-qt-offscreen.sh')
            (home/'launch-linux.sh').write_text('''#!/usr/bin/env bash
if [[ "${SMI_QT_RECOVERY_ONLY:-}" == 1 ]]; then
 echo NATIVE_QT_RECOVERY_PASS
elif [[ "${SMI_QT_DOCUMENT_ONLY:-}" == 1 ]]; then
 echo NATIVE_QT_DOCUMENT_PASS
elif [[ "${SMI_QT_PROGRAM_ONLY:-}" == 1 ]]; then
 # Deliberately retain stdout in a detached child after the stage exits.
 (sleep 3) </dev/null &
 echo NATIVE_QT_PROGRAM_PASS
else
 echo NATIVE_QT_SMOKE_PASS
fi
''')
            started=time.monotonic()
            run=subprocess.run(['bash',str(home/'test-qt-offscreen.sh')],
                               cwd=home,text=True,capture_output=True,
                               env={**os.environ,'SMI_RECOVERY_DIR':str(home/'recovery')},timeout=6)
            elapsed=time.monotonic()-started
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            self.assertLess(elapsed,2.6,run.stdout+run.stderr)
            self.assertIn('NATIVE_QT_PROGRAM_PASS',run.stdout)
            self.assertIn('NATIVE_QT_SMOKE_PASS',run.stdout)

if __name__=='__main__':unittest.main()
