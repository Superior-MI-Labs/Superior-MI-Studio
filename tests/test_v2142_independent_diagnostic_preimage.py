"""Failure attribution cannot outrun the independent compiler's owner preimage."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio_native import python_lowering as compiler
from studio_native.program_graph import GraphConflict, ProgramGraph, ProgramGraphError
from studio_native.source_editor import SourceDocumentSession

EXAMPLE=Path(__file__).resolve().parents[1]/'examples/qualified-integer-program.smi-graph'


class IndependentDiagnosticPreimageTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path=Path(temp.name)/'independent.py'
        self.graph=ProgramGraph.open(EXAMPLE)
        self.graph_before=self.graph.state
        base=compiler.preview_python(self.graph.state).source
        self.assertIsNotNone(base)
        self.valid_edit=base.replace('_smi_value_0 = 1','_smi_value_0 = 7',1)
        self.assertNotEqual(base,self.valid_edit)
        self.path.write_text(self.valid_edit,encoding='utf-8')
        self.session=SourceDocumentSession.open(self.path)
        self.revision=self.graph.revision

    def review(self):
        return compiler.review_independent_source_functions(
            self.graph,self.session,('increment',),
            expected_graph_revision=self.revision)

    def invalid_source(self):
        self.assertTrue(self.session.update(
            self.valid_edit.replace('_smi_value_0 = 7',
                                    '_smi_value_0 = unknown_value',1)))

    def during_second_proof(self,change):
        original=compiler._qualified_source_edit_plan
        attempts=[0]
        def run(*args,**kwargs):
            attempts[0]+=1
            try:
                return original(*args,**kwargs)
            finally:
                if attempts[0]==2:
                    change()
        return run,attempts

    def test_normal_success_still_returns_an_importable_review(self):
        receipt=self.review()
        self.assertTrue(receipt.changes)
        self.assertEqual(receipt.graph_revision,self.revision)
        self.assertEqual(self.graph.state,self.graph_before)
        self.assertTrue(compiler.import_independent_source_functions(
            self.graph,self.session,receipt.functions,
            expected_graph_revision=receipt.graph_revision,
            expected_source_revision=receipt.source_revision,
            expected_source_sha256=receipt.source_sha256))
        self.assertEqual(self.path.read_text(encoding='utf-8'),self.valid_edit)

    def test_region_failure_detects_editor_change_during_isolation(self):
        self.invalid_source()
        def edit():
            self.session.update(self.session.text+'\n# updated during diagnostics\n')
        run,attempts=self.during_second_proof(edit)
        with patch.object(compiler,'_qualified_source_edit_plan',side_effect=run):
            with self.assertRaisesRegex(GraphConflict,'Source revision changed during'):
                self.review()
        self.assertGreaterEqual(attempts[0],2)
        self.assertIn('updated during diagnostics',self.session.text)
        self.assertEqual(self.graph.state,self.graph_before)

    def test_region_failure_detects_external_disk_write_during_isolation(self):
        self.invalid_source()
        def disk():
            self.path.write_text('# changed while diagnosing\n',encoding='utf-8')
        run,attempts=self.during_second_proof(disk)
        with patch.object(compiler,'_qualified_source_edit_plan',side_effect=run):
            with self.assertRaisesRegex(GraphConflict,'Source changed on disk during'):
                self.review()
        self.assertGreaterEqual(attempts[0],2)
        self.assertEqual(self.graph.state,self.graph_before)

    def test_region_failure_detects_saved_baseline_drift_without_text_edit(self):
        self.invalid_source()
        saved=self.session.saved_raw
        revision,text=self.session.revision,self.session.text
        def advance_saved_bytes():
            advanced=saved.replace(b'\n',b'\r\n')
            self.assertNotEqual(advanced,saved)
            self.path.write_bytes(advanced)
            self.session.saved_raw=advanced
        run,attempts=self.during_second_proof(advance_saved_bytes)
        with patch.object(compiler,'_qualified_source_edit_plan',side_effect=run):
            with self.assertRaisesRegex(GraphConflict,'Source saved baseline changed during'):
                self.review()
        self.assertGreaterEqual(attempts[0],2)
        self.assertEqual((self.session.revision,self.session.text),(revision,text))
        self.assertEqual(self.graph.state,self.graph_before)

    def test_region_failure_still_prefers_concurrent_graph_revision(self):
        self.invalid_source()
        def change_graph():
            self.assertTrue(self.graph.edit(self.graph.revision,'move_node',
                                            node='one',x=228,y=64))
        run,attempts=self.during_second_proof(change_graph)
        with patch.object(compiler,'_qualified_source_edit_plan',side_effect=run):
            with self.assertRaisesRegex(GraphConflict,'Graph revision changed during'):
                self.review()
        self.assertGreaterEqual(attempts[0],2)
        self.assertNotEqual(self.graph.revision,self.revision)

    def test_combined_failure_detects_source_change_after_valid_region_proof(self):
        actual=compiler._qualified_source_edit_plan
        attempts=[0]
        def combined_only(*args,**kwargs):
            attempts[0]+=1
            if attempts[0]==1:
                raise ProgramGraphError('fixture: combined-only compiler refusal')
            result=actual(*args,**kwargs)
            if attempts[0]==2:
                self.session.update(self.session.text+'\n# late source edit\n')
            return result
        with patch.object(compiler,'_qualified_source_edit_plan',side_effect=combined_only):
            with self.assertRaisesRegex(GraphConflict,'Source revision changed during'):
                self.review()
        self.assertGreaterEqual(attempts[0],2)
        self.assertEqual(self.graph.state,self.graph_before)
        self.assertIn('late source edit',self.session.text)


if __name__=='__main__':unittest.main()
