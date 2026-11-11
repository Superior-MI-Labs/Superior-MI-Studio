"""Linked Python no-op and import receipts cannot accept a graph changed during disk inspection."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio_native import python_lowering as adapter
from studio_native.program_graph import GraphConflict, ProgramGraph
from studio_native.source_editor import SourceDocumentSession

EXAMPLE=Path(__file__).resolve().parents[1]/'examples/qualified-integer-program.smi-graph'


class LinkedGraphDuringInspectionTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path=Path(temp.name)/'linked.py'
        self.graph=ProgramGraph.open(EXAMPLE)
        self.generated=adapter.preview_python(self.graph.state).source
        self.assertIsNotNone(self.generated)
        self.path.write_text(self.generated,encoding='utf-8')
        self.session=SourceDocumentSession.open(self.path)
        self.link=adapter.LinkedPythonSource.attach(self.graph,self.session)
        self.revision=self.graph.revision
        self.original_fingerprint=self.link.graph_fingerprint

    def advance_graph(self):
        self.assertTrue(self.graph.edit(self.graph.revision,'move_node',
                                        node='one',x=282,y=65))

    def inspect_after(self,call):
        original=self.session.inspect_external
        count=[0]
        def inspect():
            count[0]+=1
            state=original()
            if count[0]==call:
                self.advance_graph()
            return state
        return inspect,count

    def test_unmodified_source_and_graph_still_noop(self):
        review=self.link.review_edits()
        self.assertEqual(review.changes,())
        self.assertEqual(review.graph_revision,self.revision)
        self.assertFalse(self.link.import_edits())
        self.assertEqual(self.link.graph_revision,self.revision)
        self.assertEqual(self.link.graph_fingerprint,self.original_fingerprint)
        self.assertEqual(self.path.read_text(encoding='utf-8'),self.generated)

    def test_noop_review_refuses_graph_mutation_during_source_inspection(self):
        inspect,calls=self.inspect_after(1)
        with patch.object(self.session,'inspect_external',side_effect=inspect):
            with self.assertRaisesRegex(GraphConflict,
                                        'Graph changed during linked Python qualification'):
                self.link.review_edits()
        self.assertEqual(calls[0],1)
        self.assertEqual(self.link.graph_revision,self.revision)
        self.assertEqual(self.link.graph_fingerprint,self.original_fingerprint)

    def test_noop_import_refuses_without_restamping_graph_revision(self):
        inspect,calls=self.inspect_after(1)
        with patch.object(self.session,'inspect_external',side_effect=inspect), \
                patch.object(self.graph,'edit_many',wraps=self.graph.edit_many) as writer:
            with self.assertRaisesRegex(GraphConflict,
                                        'Graph changed during linked Python qualification'):
                self.link.import_edits()
            writer.assert_not_called()
        self.assertEqual(calls[0],1)
        self.assertEqual(self.link.graph_revision,self.revision)
        self.assertEqual(self.link.graph_fingerprint,self.original_fingerprint)
        self.assertEqual(self.path.read_text(encoding='utf-8'),self.generated)

    def test_changed_source_import_refuses_graph_edit_in_final_inspection(self):
        changed=self.generated.replace('_smi_value_0 = 1','_smi_value_0 = 23',1)
        self.assertNotEqual(changed,self.generated)
        self.session.update(changed)
        inspect,calls=self.inspect_after(2)
        with patch.object(self.session,'inspect_external',side_effect=inspect), \
                patch.object(self.graph,'edit_many',wraps=self.graph.edit_many) as writer:
            with self.assertRaisesRegex(GraphConflict,
                                        'Graph changed during linked Python qualification'):
                self.link.import_edits()
            writer.assert_not_called()
        self.assertGreaterEqual(calls[0],2)
        self.assertEqual(self.link.source_revision,0)
        self.assertEqual(self.link.graph_revision,self.revision)
        self.assertEqual(self.session.text,changed)
        self.assertEqual(self.path.read_text(encoding='utf-8'),self.generated)

    def test_trivia_only_import_refuses_graph_mutation_before_noop_receipt(self):
        self.session.update(self.generated+'\n# user-owned source note\n')
        inspect,calls=self.inspect_after(2)
        with patch.object(self.session,'inspect_external',side_effect=inspect):
            with self.assertRaisesRegex(GraphConflict,
                                        'Graph changed during linked Python qualification'):
                self.link.import_edits()
        self.assertGreaterEqual(calls[0],2)
        self.assertEqual(self.link.source_revision,0)
        self.assertEqual(self.link.graph_revision,self.revision)
        self.assertIn('user-owned source note',self.session.text)

    def test_stable_authored_source_still_imports_through_original_compiler(self):
        changed=self.generated.replace('_smi_value_0 = 1','_smi_value_0 = 29',1)
        self.session.update(changed)
        self.assertTrue(self.link.import_edits())
        self.assertEqual(self.link.graph_revision,self.graph.revision)
        self.assertEqual(self.link.source_revision,self.session.revision)
        self.assertIn('_smi_value_0 = 29',adapter.preview_python(self.graph.state).source)
        self.assertEqual(self.path.read_text(encoding='utf-8'),self.generated)

    def test_undo_to_identical_graph_fingerprint_remains_supported(self):
        self.advance_graph()
        self.assertTrue(self.graph.undo(self.graph.revision))
        self.assertNotEqual(self.graph.revision,self.revision)
        self.assertEqual(self.link._graph_fingerprint(self.graph),
                         self.original_fingerprint)
        self.assertFalse(self.link.import_edits())
        self.assertEqual(self.link.graph_revision,self.graph.revision)
        self.assertEqual(self.link.graph_fingerprint,self.original_fingerprint)


if __name__=='__main__':
    unittest.main()
