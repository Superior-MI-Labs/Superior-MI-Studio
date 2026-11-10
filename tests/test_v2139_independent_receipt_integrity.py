"""One source-owned receipt must survive proof, disk inspection and final graph commit.

The saved-byte baseline can advance through SourceDocumentSession.commit() without
incrementing the editor revision. That is a different source preimage, even if
the visible text and its UTF-8 hash are unchanged.
"""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio_native import python_lowering as adapter
from studio_native.program_graph import ProgramGraph, GraphConflict, ProgramGraphError
from studio_native.source_editor import SourceDocumentSession

EXAMPLE=Path(__file__).resolve().parents[1]/'examples/qualified-integer-program.smi-graph'


class IndependentSourceReceiptTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path=Path(temporary.name)/'review.py'
        self.graph=ProgramGraph.open(EXAMPLE)
        self.initial_graph=self.graph.state
        baseline=adapter.preview_python(self.graph.state)
        self.assertIsNotNone(baseline.source)
        self.baseline=baseline.source
        self.edit=self.baseline.replace('_smi_value_0 = 1','_smi_value_0 = 7',1)
        self.assertNotEqual(self.edit,self.baseline)
        self.path.write_text(self.baseline,encoding='utf-8')
        self.session=SourceDocumentSession.open(self.path)
        self.assertTrue(self.session.update(self.edit))
        self.assertTrue(self.session.dirty)
        self.revision=self.graph.revision

    def review(self):
        return adapter.review_independent_source_functions(
            self.graph,self.session,('increment',),expected_graph_revision=self.revision)

    def import_receipt(self,receipt):
        return adapter.import_independent_source_functions(
            self.graph,self.session,receipt.functions,
            expected_graph_revision=receipt.graph_revision,
            expected_source_revision=receipt.source_revision,
            expected_source_sha256=receipt.source_sha256)

    def test_valid_unsaved_source_still_reviews_and_imports(self):
        receipt=self.review()
        self.assertEqual(receipt.source_sha256,hashlib.sha256(
            self.edit.encode('utf-8')).hexdigest())
        self.assertTrue(self.import_receipt(receipt))
        self.assertEqual(self.graph.revision,self.revision+1)
        self.assertEqual(self.session.text,self.edit)
        self.assertEqual(self.path.read_text(encoding='utf-8'),self.baseline)

    def test_successful_review_refuses_save_during_compiler_proof(self):
        real=adapter._qualified_source_edit_plan
        def save_late(*args,**kwargs):
            result=real(*args,**kwargs)
            self.session.commit()
            return result
        with patch.object(adapter,'_qualified_source_edit_plan',side_effect=save_late):
            with self.assertRaisesRegex(GraphConflict,'Source saved baseline changed during'):
                self.review()
        self.assertEqual(self.session.revision,1)
        self.assertFalse(self.session.dirty)
        self.assertEqual(self.graph.state,self.initial_graph)

    def test_failed_review_prefers_baseline_conflict_to_stale_diagnostic(self):
        self.session.update(self.edit.replace(
            '_smi_value_0 = 7','_smi_value_0 = unqualified_value',1))
        real=adapter._qualified_source_edit_plan
        def save_even_on_refusal(*args,**kwargs):
            try:
                return real(*args,**kwargs)
            finally:
                self.session.commit()
        with patch.object(adapter,'_qualified_source_edit_plan',
                          side_effect=save_even_on_refusal):
            with self.assertRaisesRegex(GraphConflict,'Source saved baseline changed during'):
                self.review()
        self.assertEqual(self.graph.state,self.initial_graph)

    def test_import_refuses_saved_baseline_change_after_proof(self):
        receipt=self.review()
        real=adapter._independent_functions_plan
        def save_after_plan(*args,**kwargs):
            result=real(*args,**kwargs)
            self.session.commit()
            return result
        with patch.object(adapter,'_independent_functions_plan',side_effect=save_after_plan):
            with self.assertRaisesRegex(GraphConflict,'Source saved baseline changed before graph import'):
                self.import_receipt(receipt)
        self.assertEqual(self.graph.state,self.initial_graph)

    def test_noop_import_also_checks_saved_baseline(self):
        self.session.update(self.baseline+'\n# outside selected function\n')
        receipt=self.review()
        self.assertEqual(receipt.changes,())
        real=adapter._independent_functions_plan
        def save_after_plan(*args,**kwargs):
            result=real(*args,**kwargs)
            self.session.commit()
            return result
        with patch.object(adapter,'_independent_functions_plan',side_effect=save_after_plan):
            with self.assertRaisesRegex(GraphConflict,'Source saved baseline changed before graph import'):
                self.import_receipt(receipt)
        self.assertEqual(self.graph.state,self.initial_graph)

    def test_external_inspection_reentrancy_is_not_a_receipt(self):
        revision,text,saved=self.session.revision,self.session.text,self.session.saved_raw
        inspect=self.session.inspect_external
        def inspect_and_edit():
            value=inspect()
            self.session.update(self.session.text+'\n# changed during inspection\n')
            return value
        with patch.object(self.session,'inspect_external',side_effect=inspect_and_edit):
            with self.assertRaisesRegex(GraphConflict,'Source revision changed before graph import'):
                adapter._assert_independent_source_snapshot(
                    self.session,revision,text,saved,stage='before graph import')
        self.assertEqual(self.graph.state,self.initial_graph)

    def test_unencodable_import_refuses_using_compiler_error(self):
        self.session.update(self.session.text+'\n# surrogate \ud800\n')
        with self.assertRaisesRegex(ProgramGraphError,'cannot be encoded as UTF-8'):
            adapter.import_independent_source_functions(
                self.graph,self.session,('increment',),
                expected_graph_revision=self.graph.revision,
                expected_source_revision=self.session.revision,
                expected_source_sha256='0'*64)
        self.assertEqual(self.graph.state,self.initial_graph)


if __name__=='__main__':
    unittest.main()
