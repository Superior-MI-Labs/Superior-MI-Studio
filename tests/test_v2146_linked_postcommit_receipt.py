"""Linked-source imports publish one accepted receipt only after post-commit proof."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio_native import python_lowering as compiler
from studio_native.program_graph import GraphConflict, ProgramGraph, ProgramGraphError
from studio_native.source_editor import SourceDocumentSession

EXAMPLE=Path(__file__).resolve().parents[1]/'examples/qualified-integer-program.smi-graph'


class LinkedPostCommitReceiptTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path=Path(temp.name)/'linked.py'
        self.graph=ProgramGraph.open(EXAMPLE)
        self.base=compiler.preview_python(self.graph.state).source
        self.assertIsNotNone(self.base)
        self.path.write_text(self.base,encoding='utf-8')
        self.session=SourceDocumentSession.open(self.path)
        self.link=compiler.LinkedPythonSource.attach(self.graph,self.session)
        self.original=self.receipt()
        self.source_edit=self.base.replace('_smi_value_0 = 1','_smi_value_0 = 17',1)
        self.assertNotEqual(self.source_edit,self.base)
        self.session.update(self.source_edit)

    def receipt(self):
        return (self.link.graph_revision,self.link.graph_fingerprint,
                self.link.source_revision,self.link.base_source,
                self.link.source_text,self.link.disk_sha256)

    def after_commit_preview(self,action):
        real=compiler.preview_python
        called=[0]
        def wrapped(state):
            result=real(state)
            if self.graph.revision != self.original[0]:
                called[0]+=1
                action()
            return result
        return wrapped,called

    def assert_unaccepted_after_commit(self):
        self.assertNotEqual(self.graph.revision,self.original[0])
        self.assertEqual(self.receipt(),self.original)
        self.assertEqual(self.session.text,self.source_edit)

    def test_ordinary_import_refreshes_all_link_fields_and_reimports(self):
        self.assertTrue(self.link.import_edits())
        self.assertEqual(self.link.graph_revision,self.graph.revision)
        self.assertEqual(self.link.source_revision,self.session.revision)
        self.assertEqual(self.link.source_text,self.source_edit)
        self.assertEqual(self.link.base_source,compiler.preview_python(self.graph.state).source)
        self.assertEqual(self.path.read_text(encoding='utf-8'),self.base)
        self.assertFalse(self.link.import_edits())
        another=self.source_edit.replace('_smi_value_0 = 17','_smi_value_0 = 18',1)
        self.assertNotEqual(another,self.source_edit)
        self.session.update(another)
        self.assertTrue(self.link.import_edits())
        self.assertIn('_smi_value_0 = 18',compiler.preview_python(self.graph.state).source)

    def test_failed_postcommit_preview_does_not_partially_advance_receipt(self):
        # Only the after-write preview is intercepted; the original compiler
        # planner still uses the real lowering authority.
        real=compiler.preview_python
        def intercepted(state):
            if self.graph.revision != self.original[0]:
                raise ProgramGraphError('fixture postcommit compiler failure')
            return real(state)
        with patch.object(compiler,'preview_python',side_effect=intercepted):
            with self.assertRaisesRegex(ProgramGraphError,'postcommit compiler failure'):
                self.link.import_edits()
        self.assert_unaccepted_after_commit()
        with self.assertRaisesRegex(GraphConflict,'Graph changed since source link'):
            self.link.review_edits()

    def test_unqualified_postcommit_preview_cannot_set_none_baseline(self):
        real=compiler.preview_python
        def bad(state):
            if self.graph.revision != self.original[0]:
                return compiler.PythonPreview(None,('fixture: unqualified refreshed graph',))
            return real(state)
        with patch.object(compiler,'preview_python',side_effect=bad):
            with self.assertRaisesRegex(GraphConflict,'Committed graph cannot refresh linked Python'):
                self.link.import_edits()
        self.assert_unaccepted_after_commit()
        self.assertIsNotNone(self.link.base_source)

    def test_editor_changes_during_receipt_preview_refuse_metadata_refresh(self):
        def late_source():
            self.session.update(self.session.text+'\n# late editor update\n')
        wrapped,calls=self.after_commit_preview(late_source)
        with patch.object(compiler,'preview_python',side_effect=wrapped):
            with self.assertRaisesRegex(GraphConflict,'Source changed during linked Python receipt refresh'):
                self.link.import_edits()
        self.assertEqual(calls[0],1)
        self.assertNotEqual(self.graph.revision,self.original[0])
        self.assertEqual(self.receipt(),self.original)
        self.assertIn('late editor update',self.session.text)

    def test_external_source_write_during_receipt_preview_refuses_refresh(self):
        def disk():
            self.path.write_text('# external replacement\n',encoding='utf-8')
        wrapped,calls=self.after_commit_preview(disk)
        with patch.object(compiler,'preview_python',side_effect=wrapped):
            with self.assertRaisesRegex(GraphConflict,'Source changed on disk during linked Python receipt refresh'):
                self.link.import_edits()
        self.assertEqual(calls[0],1)
        self.assert_unaccepted_after_commit()
        self.assertEqual(self.path.read_text(encoding='utf-8'),'# external replacement\n')

    def test_graph_advances_during_receipt_preview_refuses_refresh(self):
        def concurrent_graph():
            self.assertTrue(self.graph.edit(self.graph.revision,'move_node',
                                            node='one',x=291,y=73))
        wrapped,calls=self.after_commit_preview(concurrent_graph)
        with patch.object(compiler,'preview_python',side_effect=wrapped):
            with self.assertRaisesRegex(GraphConflict,'Graph changed during linked Python receipt refresh'):
                self.link.import_edits()
        self.assertEqual(calls[0],1)
        self.assert_unaccepted_after_commit()

    def test_graph_advances_during_fingerprint_refuses_refresh(self):
        real=self.link._graph_fingerprint
        calls=[0]
        def fingerprint(graph):
            result=real(graph)
            if graph.revision!=self.original[0]:
                calls[0]+=1
                self.assertTrue(graph.edit(graph.revision,'move_node',
                                           node='one',x=301,y=77))
            return result
        with patch.object(compiler.LinkedPythonSource,'_graph_fingerprint',
                          side_effect=fingerprint):
            with self.assertRaisesRegex(GraphConflict,'Graph changed during linked Python receipt refresh'):
                self.link.import_edits()
        self.assertEqual(calls[0],1)
        self.assert_unaccepted_after_commit()

    def test_trivia_only_source_import_still_advances_accepted_source_receipt(self):
        self.session.update('# authored\n'+self.base+'\n# author note\n')
        self.assertFalse(self.link.import_edits())
        self.assertEqual(self.link.graph_revision,self.original[0])
        self.assertEqual(self.link.source_revision,self.session.revision)
        self.assertEqual(self.link.base_source,self.base)
        self.assertEqual(self.link.source_text,self.session.text)
        self.assertEqual(self.path.read_text(encoding='utf-8'),self.base)


if __name__=='__main__':
    unittest.main()
