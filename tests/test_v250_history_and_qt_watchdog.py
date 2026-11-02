"""v2.50: bounded source history and fail-closed Qt qualification, no Qt needed."""
from __future__ import annotations
import ast
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from studio_native.python_edit import EditProposal, SourceEditHistory
from studio_native.python_graph import PythonDocument, SourceError
from studio_native.source_editor import save_source_change

ROOT=Path(__file__).resolve().parents[1]

class SourceHistoryTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.file=self.root/'code.py'
        self.file.write_bytes(b'def f(x):\n    return x\n')
        self.history=SourceEditHistory(max_entries=2)

    def edit(self,old,new):
        original=self.file.read_bytes()
        self.assertIn(old,original)
        replacement=original.replace(old,new,1)
        return EditProposal(self.file,original,replacement,'utf-8','change source')

    def test_undo_redo_and_new_branch_invalidates_redo(self):
        a=self.edit(b'return x',b'return x + 1')
        self.history.apply(a)
        self.assertTrue(self.history.can_undo(self.file))
        self.assertFalse(self.history.can_redo(self.file))
        self.assertTrue((self.root/'code.py.smi-backup').exists())
        b=self.edit(b'return x + 1',b'return x * 2')
        self.history.apply(b)
        self.history.undo(self.file)
        self.assertEqual(self.file.read_bytes(),a.candidate)
        self.history.undo(self.file)
        self.assertEqual(self.file.read_bytes(),a.original)
        self.assertFalse(self.history.can_undo(self.file))
        self.history.redo(self.file)
        self.assertEqual(self.file.read_bytes(),a.candidate)
        self.assertTrue(self.history.can_redo(self.file))
        c=self.edit(b'return x + 1',b'return x - 1')
        self.history.apply(c)
        self.assertFalse(self.history.can_redo(self.file))
        with self.assertRaisesRegex(SourceError,'No committed'):
            self.history.redo(self.file)
        PythonDocument(self.file)

    def test_external_file_edits_refuse_undo_without_losing_history(self):
        proposal=self.edit(b'return x',b'return x + 10')
        self.history.apply(proposal)
        self.file.write_bytes(b'# external edit\n'+proposal.candidate)
        with self.assertRaisesRegex(SourceError,'externally'):
            self.history.undo(self.file)
        self.assertEqual(self.file.read_bytes(),b'# external edit\n'+proposal.candidate)
        self.assertTrue(self.history.can_undo(self.file))

    def test_failed_commit_never_enters_history(self):
        stale=self.edit(b'return x',b'return 10')
        self.file.write_text('def f(x):\n    return 30\n')
        with self.assertRaisesRegex(SourceError,'externally'):
            self.history.apply(stale)
        self.assertFalse(self.history.can_undo(self.file))

    def test_text_save_joins_same_committed_history(self):
        doc=PythonDocument(self.file)
        save_source_change(doc,'def f(x):\n    return x + 2\n',history=self.history)
        self.assertTrue(self.history.can_undo(self.file))
        self.history.undo(self.file)
        self.assertEqual(self.file.read_bytes(),doc.raw)
        self.history.redo(self.file)
        self.assertIn(b'return x + 2',self.file.read_bytes())

    def test_reversal_is_scoped_to_file(self):
        self.history.apply(self.edit(b'return x',b'return x + 1'))
        other=self.root/'other.py';other.write_bytes(b'pass\n')
        self.assertFalse(self.history.can_undo(other))
        with self.assertRaisesRegex(SourceError,'No committed'):
            self.history.undo(other)

    def test_history_bounds_limit_old_transactions(self):
        for value in (1,2,3):
            original=self.file.read_bytes()
            self.history.apply(EditProposal(self.file,original,
                 b'def f(x):\n    return x + '+str(value).encode()+b'\n',
                 'utf-8','next expression'))
        self.history.undo(self.file)
        self.history.undo(self.file)
        self.assertFalse(self.history.can_undo(self.file))
        self.assertIn(b'return x + 1',self.file.read_bytes())

    def test_history_limit_refuses_invalid_limits(self):
        with self.assertRaises(ValueError):SourceEditHistory(max_entries=0)
        with self.assertRaises(ValueError):SourceEditHistory(max_files=0)

class SmokeTimeoutTests(unittest.TestCase):
    def test_modal_type_is_imported_before_timer_callback(self):
        source=(ROOT/'studio_native/qt_smoke.py').read_text()
        tree=ast.parse(source)
        qt_imports=[x for x in tree.body if isinstance(x,ast.ImportFrom)
                    and x.module=='PyQt6.QtWidgets']
        self.assertIn('QDialog',{alias.name for item in qt_imports for alias in item.names})
        self.assertIn("modal.reject()",source)
        self.assertIn("QT_STAGE function-call-form",source)

    def test_stalled_qt_process_fails_with_report_and_no_launch(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            app=root/'app';app.mkdir()
            shutil.copy2(ROOT/'RUN-ALL.sh',app/'RUN-ALL.sh')
            (app/'doctor.sh').write_text('#!/bin/bash\necho doctor-success\n')
            (app/'test-qt-offscreen.sh').write_text('#!/bin/bash\necho QT_STAGE simulated-modal\nsleep 30\n')
            (app/'launch-linux.sh').write_text('#!/bin/bash\ntouch "$SMI_LAUNCH_SENTINEL"\n')
            env={**os.environ,'SMI_LOG_DIR':str(root/'logs'),
                 'SMI_LAUNCH_SENTINEL':str(root/'launched'),
                 'SMI_QT_SMOKE_TIMEOUT':'1s'}
            completed=subprocess.run(['bash',str(app/'RUN-ALL.sh'),'--launch'],
                 env=env,capture_output=True,text=True,timeout=12)
            self.assertEqual(completed.returncode,1,completed.stdout+completed.stderr)
            self.assertIn('QT: TIMEOUT',completed.stdout)
            self.assertIn('CHECKS_FAILED_OR_UNAVAILABLE_REVIEW_REQUIRED',completed.stdout)
            self.assertFalse((root/'launched').exists())
            reports=list((root/'logs').glob('qualification-*'))
            self.assertEqual(len([p for p in reports if p.is_dir()]),1)
            report=next(p for p in reports if p.is_dir())
            self.assertIn('QT_STAGE simulated-modal',(report/'qt.log').read_text())
            self.assertTrue(Path(str(report)+'.tar.gz').exists())

if __name__=='__main__':unittest.main()
