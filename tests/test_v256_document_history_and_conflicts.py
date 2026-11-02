"""v2.56: one document owns draft undo; conflicts never destroy text."""
import ast
from pathlib import Path
import tempfile
import unittest

from studio_native.python_graph import SourceError
from studio_native.source_editor import SourceDocumentSession

ROOT=Path(__file__).resolve().parents[1]


class DocumentHistoryTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path=Path(temp.name)/'work.py'
        self.initial='def work(x):\n    return x + 1\n'
        self.path.write_text(self.initial)
        self.session=SourceDocumentSession.open(self.path)

    def test_draft_undo_across_view_aliases_and_redo(self):
        views={'first':self.session,'second':self.session}
        self.session.update('def work(x):\n    return x + 4\n')
        self.session.update('def work(x):\n    return x + 42\n',parse=False)
        self.assertFalse(self.session.graph_ready)
        self.assertTrue(views['second'].undo_draft())
        self.assertTrue(self.session.graph_ready)
        self.assertIn('x + 4',views['first'].parsed.source)
        self.assertTrue(self.session.undo_draft())
        self.assertEqual(self.session.text,self.initial)
        self.assertFalse(self.session.dirty)
        self.assertTrue(self.session.redo_draft())
        self.assertIn('x + 4',self.session.text)
        self.assertEqual(self.path.read_text(),self.initial)

    def test_redo_invalidated_by_new_edit_and_history_does_not_double_record(self):
        self.session.update('answer = 1\n')
        self.session.update('answer = 12\n')
        self.session.undo_draft()
        self.assertEqual(len(self.session._draft_undo),1)
        self.session.update('answer = 13\n')
        self.assertFalse(self.session.redo_draft())
        self.assertEqual(self.session.text,'answer = 13\n')

    def test_save_is_checkpoint_not_undo_history_authority(self):
        self.session.update('value = 10\n')
        self.session.commit()
        self.assertFalse(self.session.dirty)
        self.session.undo_draft()
        self.assertEqual(self.session.text,self.initial)
        self.assertTrue(self.session.dirty)
        self.assertEqual(self.path.read_text(),'value = 10\n')
        self.session.redo_draft()
        self.assertFalse(self.session.dirty)
        self.assertEqual(self.path.read_text(),'value = 10\n')

    def test_incomplete_python_can_be_undone_without_disk_write(self):
        self.session.update('def work(:\n')
        self.assertFalse(self.session.graph_ready)
        self.assertTrue(self.session.undo_draft())
        self.assertTrue(self.session.graph_ready)
        self.assertEqual(self.path.read_text(),self.initial)

    def test_history_is_bounded_by_count_and_payload(self):
        self.session.MAX_DRAFT_EDITS=3
        self.session.MAX_DRAFT_CHARS=15
        for value in ('x\n','xy\n','xyz\n','xyzz\n','xyzzz\n'):
            self.session.update(value,parse=False)
        self.assertLessEqual(len(self.session._draft_undo),3)
        self.assertLessEqual(sum(d.weight for d in self.session._draft_undo),15)
        self.assertTrue(self.session.undo_draft())

    def test_reloaded_session_clears_history_and_preserves_identity(self):
        same=self.session
        self.session.update('draft=1\n')
        self.path.write_text('other=2\n')
        self.session.discard_and_reload(discard_unsaved=True)
        self.assertIs(self.session,same)
        self.assertEqual(self.session.text,'other=2\n')
        self.assertFalse(self.session.undo_draft())
        self.assertFalse(self.session.redo_draft())

    def test_externally_modified_dirty_document_remains_intact(self):
        self.session.update('draft=3\n')
        self.path.write_text('external=5\n')
        self.assertEqual(self.session.inspect_external(),'modified')
        self.assertIn('draft=3',self.session.text)
        with self.assertRaisesRegex(SourceError,'changed externally'):
            self.session.commit()
        self.assertEqual(self.path.read_text(),'external=5\n')
        self.assertTrue(self.session.dirty)
        self.assertEqual(self.session.external_state,'modified')
        self.session.undo_draft()
        self.assertEqual(self.session.text,self.initial)
        self.assertEqual(self.path.read_text(),'external=5\n')

    def test_missing_or_symlink_disk_path_never_publishes(self):
        self.session.update('draft=3\n')
        self.path.unlink()
        self.assertEqual(self.session.inspect_external(),'unavailable')
        with self.assertRaisesRegex(SourceError,'changed externally'):
            self.session.commit()
        self.path.symlink_to(Path(self.path.parent)/'different.py')
        self.assertEqual(self.session.inspect_external(),'unavailable')
        self.assertEqual(self.session.text,'draft=3\n')

    def test_crlf_normalized_editor_text_does_not_create_false_dirty_state(self):
        self.path.write_bytes(b'def work():\r\n    return 1\r\n')
        session=SourceDocumentSession.open(self.path)
        self.assertEqual(session.text,'def work():\n    return 1\n')
        self.assertFalse(session.update(session.text))
        self.assertFalse(session.dirty)
        session.update('def work():\n    return 2\n')
        session.undo_draft()
        self.assertFalse(session.dirty)
        self.assertEqual(self.path.read_bytes(),b'def work():\r\n    return 1\r\n')

    def test_unicode_deltas_use_python_character_offsets(self):
        self.session.update('label="🐈"\n')
        self.session.update('label="🐈🐈"\n')
        self.assertTrue(self.session.undo_draft())
        self.assertEqual(self.session.text,'label="🐈"\n')
        self.assertTrue(self.session.redo_draft())
        self.assertEqual(self.session.text,'label="🐈🐈"\n')

    def test_qt_references_session_owned_history_not_qtext_document(self):
        source=(ROOT/'studio_native/gui.py').read_text()
        tree=ast.parse(source)
        lab=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='NativeLab')
        methods={x.name:x for x in lab.body if isinstance(x,ast.FunctionDef)}
        for name in ('undo_source_draft','redo_source_draft','check_python_external_change'):
            self.assertIn(name,methods)
        build=ast.get_source_segment(source,methods['_build_source_editor'])
        self.assertIn('setUndoRedoEnabled(False)',build)
        self.assertIn('PythonSourceTextEdit',build)
        self.assertIn('undo=self.undo_source_draft',build)
        self.assertIn('redo=self.redo_source_draft',build)
        self.assertNotIn('QShortcut(',build)

if __name__=='__main__':unittest.main()
