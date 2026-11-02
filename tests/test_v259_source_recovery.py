"""Crash-recovery negatives and source authority invariants (no PyQt required)."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from studio_native.draft_recovery import DraftRecoveryStore
from studio_native.source_editor import SourceDocumentSession
from studio_native.python_graph import SourceError


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / 'program.py'
        self.path.write_bytes(b'def value(a):\n    return a + 1\n')
        self.store = DraftRecoveryStore(self.root / 'recovery')

    def session(self):
        return SourceDocumentSession.open(self.path)

    def draft(self, text='def value(a):\n    return a + 2\n'):
        session = self.session()
        session.update(text)
        self.assertTrue(session.snapshot_recovery(self.store))
        return session

    def test_clean_document_does_not_create_journal(self):
        session = self.session()
        self.assertFalse(session.snapshot_recovery(self.store))
        self.assertIsNone(self.store.latest(self.path))
        self.assertFalse(self.store.root.exists())

    def test_roundtrip_explicit_only_no_disk_mutation(self):
        old = self.path.read_bytes()
        original = self.draft()
        record = self.store.latest(self.path)
        self.assertIsNotNone(record)
        recovered = self.session()
        self.assertEqual(recovered.text, old.decode())
        self.assertTrue(recovered.restore_recovery(record))
        self.assertEqual(recovered.text, original.text)
        self.assertTrue(recovered.graph_ready)
        self.assertTrue(recovered.dirty)
        self.assertEqual(old, self.path.read_bytes())
        self.assertEqual(recovered._recovery_token, record.token)

    def test_incomplete_python_survives(self):
        broken='def value(:\n  ??\n'
        self.draft(broken)
        recovered=self.session()
        self.assertTrue(recovered.restore_recovery(self.store.latest(self.path)))
        self.assertEqual(recovered.text, broken)
        self.assertFalse(recovered.graph_ready)
        self.assertIsNotNone(recovered.diagnostic)
        self.assertEqual(self.path.read_bytes(), b'def value(a):\n    return a + 1\n')

    def test_recovery_never_executes_project_code(self):
        marker=self.root/'MUST_NOT_EXECUTE'
        expression=f"__import__('pathlib').Path({str(marker)!r}).touch()\n"
        self.draft(expression)
        restored=self.session()
        restored.restore_recovery(self.store.latest(self.path))
        self.assertFalse(marker.exists())

    def test_source_conflict_preserves_journal(self):
        self.draft()
        record=self.store.latest(self.path)
        self.path.write_bytes(b'replaced by another process\n')
        target=self.session()
        with self.assertRaisesRegex(SourceError,'Recovery base differs'):
            target.restore_recovery(record)
        self.assertEqual(target.text, 'replaced by another process\n')
        self.assertEqual(record, self.store.latest(self.path))

    def test_cross_document_recovery_refused(self):
        self.draft()
        other=self.root/'other.py'
        other.write_bytes(self.path.read_bytes())
        target=SourceDocumentSession.open(other)
        with self.assertRaises(SourceError):
            target.restore_recovery(self.store.latest(self.path))

    def test_dirty_document_cannot_be_overwritten(self):
        self.draft()
        target=self.session()
        target.update('def value(a):\n    return a * 9\n')
        with self.assertRaisesRegex(SourceError,'existing unsaved'):
            target.restore_recovery(self.store.latest(self.path))

    def test_recovered_changes_can_be_saved_with_guarded_writer(self):
        self.draft()
        target=self.session()
        target.restore_recovery(self.store.latest(self.path))
        target.commit()
        target.clear_recovery(self.store)
        self.assertEqual(self.path.read_text(), 'def value(a):\n    return a + 2\n')
        self.assertIsNone(self.store.latest(self.path))

    def test_unicode_newline_preserved(self):
        original='def greet(name):\r\n    return "🦊" + name\r\n'
        self.path.write_bytes(original.encode('utf-8'))
        doc=self.session()
        text='def greet(name):\n    return "🦊✨" + name\n'
        doc.update(text)
        doc.snapshot_recovery(self.store)
        restored=self.session()
        restored.restore_recovery(self.store.latest(self.path))
        self.assertEqual(restored.text,text)
        restored.commit()
        self.assertEqual(self.path.read_bytes(),text.replace('\n','\r\n').encode('utf-8'))

    def test_two_process_records_do_not_overwrite_each_other(self):
        a=self.draft('def value(a):\n    return a + 3\n')
        b=self.draft('def value(a):\n    return a + 4\n')
        self.assertNotEqual(a._recovery_token,b._recovery_token)
        self.assertEqual(len(list(self.store.root.glob('*.json'))),2)
        b.clear_recovery(self.store)
        self.assertEqual(self.store.latest(self.path).text,a.text)

    def test_permissions_are_private(self):
        self.draft()
        self.assertEqual(stat.S_IMODE(self.store.root.stat().st_mode),0o700)
        record=next(self.store.root.glob('*.json'))
        self.assertEqual(stat.S_IMODE(record.stat().st_mode),0o600)

    def test_symlinked_record_ignored(self):
        source=self.draft()
        name=self.store._record_path(source.path,source._recovery_token)
        target=self.root/'symlink-target'
        name.rename(target)
        name.symlink_to(target)
        self.assertIsNone(self.store.latest(self.path))
        self.assertTrue(target.exists())

    def test_symlinked_recovery_directory_refused(self):
        other=self.root/'private'
        other.mkdir(mode=0o700)
        self.store.root.symlink_to(other, target_is_directory=True)
        with self.assertRaises(OSError):
            self.draft()

    def test_world_readable_directory_refused(self):
        self.store.root.mkdir(mode=0o755)
        self.store.root.chmod(0o755)
        with self.assertRaisesRegex(OSError,'other users'):
            self.draft()

    def test_corrupted_payload_rejected_by_digest(self):
        session=self.draft()
        path=self.store._record_path(session.path,session._recovery_token)
        payload=json.loads(path.read_text())
        payload['text']='def poisoned():\n    pass\n'
        path.write_text(json.dumps(payload))
        self.assertIsNone(self.store.latest(self.path))
        self.assertEqual(self.path.read_bytes(),session.saved_raw)

    def test_corrupt_or_partial_record_never_replaces_source(self):
        session=self.draft()
        path=self.store._record_path(session.path,session._recovery_token)
        path.write_text('{incomplete')
        self.assertIsNone(self.store.latest(self.path))
        self.assertEqual(self.session().text, 'def value(a):\n    return a + 1\n')
        self.assertTrue(path.exists())

    def test_oversized_journal_rejected_without_touching_source(self):
        source=self.session()
        original=self.path.read_bytes()
        with self.assertRaisesRegex(ValueError,'size limit'):
            self.store.write(source.path,source.saved_raw,'x'*(5*1024*1024),1,token=source._recovery_token)
        self.assertEqual(self.path.read_bytes(),original)

    def test_no_path_crossing_from_fake_token(self):
        with self.assertRaises(ValueError):
            self.store.write(self.path,b'base','data',1,token='../other')

    def test_default_directory_respects_explicit_env(self):
        with patch.dict(os.environ,{'SMI_RECOVERY_DIR':str(self.root/'custom')},clear=False):
            self.assertEqual(DraftRecoveryStore().root,self.root/'custom')

    def test_ui_dispatch_integrity(self):
        ui=(Path(__file__).resolve().parents[1]/'studio_native'/'gui.py').read_text()
        self.assertIn('session.restore_recovery(record)',ui)
        self.assertIn('self._draft_recovery_timer.start()',ui)
        self.assertIn('session.clear_recovery(self._draft_recovery)',ui)
        self.assertIn('self._flush_source_recovery()',ui)
        self.assertNotIn('self._draft_recovery.write(',ui)


if __name__ == '__main__':
    unittest.main()
