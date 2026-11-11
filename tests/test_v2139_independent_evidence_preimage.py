"""Independent-source receipt must bind the same graph and source through evidence mapping."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio_native import python_lowering as compiler
from studio_native.program_graph import GraphConflict, ProgramGraph, ProgramGraphError
from studio_native.source_editor import SourceDocumentSession

EXAMPLE=Path(__file__).resolve().parents[1]/'examples/qualified-integer-program.smi-graph'


class IndependentEvidencePreimageTests(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path=Path(directory.name)/'independent.py'
        self.graph=ProgramGraph.open(EXAMPLE)
        self.before=self.graph.state
        self.revision=self.graph.revision
        generated=compiler.preview_python(self.graph.state).source
        self.assertIsNotNone(generated)
        self.edited=generated.replace('_smi_value_0 = 1','_smi_value_0 = 7',1)
        self.assertNotEqual(self.edited,generated)
        self.path.write_text(self.edited,encoding='utf-8')
        self.session=SourceDocumentSession.open(self.path)

    def review(self):
        return compiler.review_independent_source_functions(
            self.graph,self.session,('increment',),
            expected_graph_revision=self.revision)

    def import_review(self,receipt):
        return compiler.import_independent_source_functions(
            self.graph,self.session,receipt.functions,
            expected_graph_revision=receipt.graph_revision,
            expected_source_revision=receipt.source_revision,
            expected_source_sha256=receipt.source_sha256)

    def test_unchanged_evidence_still_yields_importable_exact_receipt(self):
        real=compiler._independent_change_lines
        with patch.object(compiler,'_independent_change_lines',wraps=real) as evidence:
            receipt=self.review()
        self.assertEqual(evidence.call_count,1)
        self.assertEqual(receipt.graph_revision,self.revision)
        self.assertEqual(receipt.source_revision,self.session.revision)
        self.assertTrue(receipt.changes)
        self.assertEqual(self.graph.state,self.before)
        self.assertTrue(self.import_review(receipt))
        self.assertEqual(self.path.read_text(encoding='utf-8'),self.edited)

    def test_source_editor_change_during_evidence_refuses_receipt(self):
        real=compiler._independent_change_lines
        def edit(*args,**kwargs):
            proof=real(*args,**kwargs)
            self.session.update(self.session.text+'\n# late editor edit\n')
            return proof
        with patch.object(compiler,'_independent_change_lines',side_effect=edit):
            with self.assertRaisesRegex(GraphConflict,'Source revision changed during'):
                self.review()
        self.assertEqual(self.graph.state,self.before)
        self.assertIn('late editor edit',self.session.text)
        self.assertEqual(self.path.read_text(encoding='utf-8'),self.edited)

    def test_external_disk_write_during_evidence_refuses_receipt(self):
        real=compiler._independent_change_lines
        def disk(*args,**kwargs):
            proof=real(*args,**kwargs)
            self.path.write_text('# written by another process\n',encoding='utf-8')
            return proof
        with patch.object(compiler,'_independent_change_lines',side_effect=disk):
            with self.assertRaisesRegex(GraphConflict,'Source changed on disk during'):
                self.review()
        self.assertEqual(self.graph.state,self.before)
        self.assertEqual(self.session.text,self.edited)

    def test_graph_revision_changed_during_evidence_refuses_stale_receipt(self):
        real=compiler._independent_change_lines
        def graph_change(*args,**kwargs):
            proof=real(*args,**kwargs)
            self.graph.edit(self.graph.revision,'move_node',node='one',x=213,y=29)
            return proof
        with patch.object(compiler,'_independent_change_lines',side_effect=graph_change):
            with self.assertRaisesRegex(GraphConflict,'Graph revision changed during'):
                self.review()
        self.assertNotEqual(self.graph.revision,self.revision)
        self.assertEqual(self.session.text,self.edited)
        self.assertEqual(self.path.read_text(encoding='utf-8'),self.edited)

    def test_failed_proof_diagnostic_prefers_live_graph_conflict(self):
        def rejected(*args,**kwargs):
            self.graph.edit(self.graph.revision,'move_node',node='one',x=213,y=29)
            raise ProgramGraphError('fixture compiler refusal')
        with patch.object(compiler,'_qualified_source_edit_plan',side_effect=rejected):
            with self.assertRaisesRegex(GraphConflict,'Graph revision changed during'):
                self.review()
        self.assertEqual(self.session.text,self.edited)

    def test_import_never_calls_graph_writer_after_late_evidence_change(self):
        receipt=self.review()
        real=compiler._independent_change_lines
        def late_source(*args,**kwargs):
            proof=real(*args,**kwargs)
            self.session.update(self.session.text+'\n# late import edit\n')
            return proof
        with patch.object(compiler,'_independent_change_lines',side_effect=late_source), \
                patch.object(self.graph,'edit_many',wraps=self.graph.edit_many) as writer:
            with self.assertRaisesRegex(GraphConflict,'Source revision changed during'):
                self.import_review(receipt)
            writer.assert_not_called()
        self.assertEqual(self.graph.state,self.before)


if __name__=='__main__':unittest.main()
