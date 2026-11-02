"""Guarded history publication -> exact session revision, with no second authority."""
from __future__ import annotations
import ast
from pathlib import Path
import tempfile
import unittest

from studio_native.python_edit import EditProposal, SourceEditHistory, apply_proposal
from studio_native.python_graph import SourceError
from studio_native.source_editor import SourceDocumentSession

ROOT=Path(__file__).resolve().parents[1]


class CommittedRevisionSyncTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path=Path(temp.name)/'program.py'
        self.original=b'def f(x):\n    return x\n'
        self.next=b'def f(x):\n    return x + 2\n'
        self.path.write_bytes(self.original)
        self.session=SourceDocumentSession.open(self.path)
        self.history=SourceEditHistory()

    def proposal(self,old,new):
        return EditProposal(self.path,old,new,'utf-8','qualified edit')

    def test_commit_adoption_preserves_shared_session_identity(self):
        first=self.session
        tab_one={'document':first}
        tab_two={'document':first}
        self.history.apply(self.proposal(self.original,self.next))
        first.adopt_committed_revision(self.original,self.next)
        self.assertIs(tab_one['document'],tab_two['document'])
        self.assertIs(first,tab_one['document'])
        self.assertEqual(first.text,self.next.decode())
        self.assertTrue(first.graph_ready)
        self.assertFalse(first.dirty)
        self.assertEqual(first.saved_raw,self.next)
        self.assertEqual(first.revision,1)

    def test_intervening_write_refused_without_losing_clean_snapshot(self):
        self.history.apply(self.proposal(self.original,self.next))
        self.path.write_bytes(b'other=7\n')
        with self.assertRaisesRegex(SourceError,'changed externally'):
            self.session.adopt_committed_revision(self.original,self.next)
        self.assertEqual(self.session.saved_raw,self.original)
        self.assertEqual(self.session.text,self.original.decode())
        self.assertEqual(self.session.revision,0)
        self.assertEqual(self.path.read_bytes(),b'other=7\n')

    def test_dirty_draft_cannot_be_replaced_after_other_commit(self):
        self.session.update('def f(x):\n    return x + 10\n')
        self.history.apply(self.proposal(self.original,self.next))
        with self.assertRaisesRegex(SourceError,'Unsaved document'):
            self.session.adopt_committed_revision(self.original,self.next)
        self.assertTrue(self.session.dirty)
        self.assertIn('return x + 10',self.session.text)

    def test_wrong_preimage_cannot_be_adopted(self):
        self.history.apply(self.proposal(self.original,self.next))
        with self.assertRaisesRegex(SourceError,'preimage differs'):
            self.session.adopt_committed_revision(b'no',self.next)
        self.assertEqual(self.session.saved_raw,self.original)

    def test_expected_revision_check_does_not_discard_history(self):
        self.session.update('def f(x):\n    return x + 20\n')
        current_revision=self.session.revision
        self.path.write_bytes(self.next)
        with self.assertRaisesRegex(SourceError,'changed externally'):
            self.session.discard_and_reload(discard_unsaved=True,expected_raw=b'anything')
        self.assertEqual(self.session.revision,current_revision)
        self.assertEqual(len(self.session._draft_undo),1)
        self.assertIn('x + 20',self.session.text)

    def test_undo_redo_transition_returns_published_bytes(self):
        self.history.apply(self.proposal(self.original,self.next))
        self.session.adopt_committed_revision(self.original,self.next)
        backup,expected=self.history.transition(self.path,redo=False)
        self.assertEqual(expected,self.original)
        self.assertEqual(backup.read_bytes(),self.next)
        self.session.adopt_committed_revision(self.next,expected)
        self.assertEqual(self.session.saved_raw,self.original)
        _,expected=self.history.transition(self.path,redo=True)
        self.assertEqual(expected,self.next)
        self.session.adopt_committed_revision(self.original,expected)
        self.assertEqual(self.session.saved_raw,self.next)
        self.assertEqual(self.session.revision,3)

    def test_failed_transition_preserves_undo_stack(self):
        self.history.apply(self.proposal(self.original,self.next))
        self.path.write_bytes(b'external=9\n')
        with self.assertRaisesRegex(SourceError,'externally'):
            self.history.transition(self.path,redo=False)
        self.assertTrue(self.history.can_undo(self.path))
        self.assertFalse(self.history.can_redo(self.path))
        self.assertEqual(self.path.read_bytes(),b'external=9\n')

    def test_invalid_python_commit_remains_valid_document_transaction(self):
        invalid=b'def f(x):\n    return (\n'
        self.history.apply(self.proposal(self.original,invalid))
        self.session.adopt_committed_revision(self.original,invalid)
        self.assertFalse(self.session.graph_ready)
        self.assertFalse(self.session.dirty)
        self.assertIn('return (',self.session.text)
        _,expected=self.history.transition(self.path,redo=False)
        self.session.adopt_committed_revision(invalid,expected)
        self.assertTrue(self.session.graph_ready)

    def test_production_ui_does_not_reload_unverified_source_after_history(self):
        source=(ROOT/'studio_native/gui.py').read_text()
        parsed=ast.parse(source)
        lab=next(n for n in parsed.body if isinstance(n,ast.ClassDef) and n.name=='NativeLab')
        methods={n.name:ast.get_source_segment(source,n)
                 for n in lab.body if isinstance(n,ast.FunctionDef)}
        for method in ('_navigate_source_history','review_source_proposal'):
            self.assertIn('_publish_source_view_revision',methods[method])
            self.assertNotIn('reload_python_source(',methods[method])
        self.assertIn('session.adopt_committed_revision',methods['_publish_source_view_revision'])


if __name__=='__main__':
    unittest.main()

class EncodingChangeAuthorityTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path=Path(temp.name)/'encoding.py'

    def test_compatible_encoding_cookie_updates_future_session_writes(self):
        self.path.write_bytes(b'# coding: utf-8\nname = "ascii"\n')
        session=SourceDocumentSession.open(self.path)
        session.update('# coding: latin-1\nname = "ascii"\n')
        self.assertTrue(session.graph_ready)
        session.commit()
        self.assertIn(session.encoding.lower().replace('_','-'),('iso-8859-1','latin-1'))
        session.update('# coding: latin-1\nname = "caf\u00e9"\n')
        self.assertTrue(session.graph_ready)
        session.commit()
        self.assertEqual(self.path.read_bytes(),b'# coding: latin-1\nname = "caf\xe9"\n')

    def test_reinterpreting_existing_unicode_bytes_refused_without_disk_write(self):
        old='# coding: utf-8\nname = "caf\u00e9"\n'
        self.path.write_bytes(old.encode('utf-8'))
        session=SourceDocumentSession.open(self.path)
        session.update('# coding: latin-1\nname = "caf\u00e9"\n')
        self.assertFalse(session.graph_ready)
        self.assertIn('encoding declaration',session.diagnostic)
        with self.assertRaisesRegex(SourceError,'encoding'):
            session.commit()
        self.assertEqual(self.path.read_bytes(),old.encode('utf-8'))
