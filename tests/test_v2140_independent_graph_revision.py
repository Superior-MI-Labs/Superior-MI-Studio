"""Independent function receipts cannot adopt graph revisions from later callbacks."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio_native import python_lowering as adapter
from studio_native.program_graph import ProgramGraph, GraphConflict
from studio_native.source_editor import SourceDocumentSession

EXAMPLE=Path(__file__).resolve().parents[1]/'examples/qualified-integer-program.smi-graph'


class IndependentGraphRevisionTests(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path=Path(folder.name)/'independent.py'
        self.graph=ProgramGraph.open(EXAMPLE)
        self.generated=adapter.preview_python(self.graph.state).source
        self.assertIsNotNone(self.generated)
        self.edited=self.generated.replace('_smi_value_0 = 1',
                                            '_smi_value_0 = 29',1)
        self.assertNotEqual(self.generated,self.edited)
        self.path.write_text(self.edited,encoding='utf-8')
        self.source=SourceDocumentSession.open(self.path)
        self.original_revision=self.graph.revision

    def review(self):
        return adapter.review_independent_source_functions(
            self.graph,self.source,('increment',),
            expected_graph_revision=self.original_revision)

    def mutate_layout(self):
        self.assertTrue(self.graph.edit(self.graph.revision,'move_node',
                                        node='one',x=337,y=129))

    def test_clean_graph_retains_original_proof_revision(self):
        review=self.review()
        self.assertEqual(review.graph_revision,self.original_revision)
        self.assertTrue(review.changes)
        self.assertTrue(adapter.import_independent_source_functions(
            self.graph,self.source,review.functions,
            expected_graph_revision=review.graph_revision,
            expected_source_revision=review.source_revision,
            expected_source_sha256=review.source_sha256))
        self.assertEqual(self.graph.revision,self.original_revision+1)

    def test_graph_mutation_after_successful_compiler_proof_refuses_receipt(self):
        proof=adapter._qualified_source_edit_plan
        def mutate(*args,**kwargs):
            result=proof(*args,**kwargs)
            self.mutate_layout()
            return result
        with patch.object(adapter,'_qualified_source_edit_plan',side_effect=mutate):
            with self.assertRaisesRegex(GraphConflict,'Graph revision changed during independent function review'):
                self.review()
        self.assertEqual(self.graph.revision,self.original_revision+1)
        self.assertEqual(next(n for n in self.graph.state['nodes']
                              if n['id']=='one')['properties']['value'],1)

    def test_graph_mutation_during_failed_proof_supersedes_stale_diagnostic(self):
        self.source.update(self.edited.replace('_smi_value_0 = 29',
                                               '_smi_value_0 = unknown',1))
        proof=adapter._qualified_source_edit_plan
        def mutate_even_on_refusal(*args,**kwargs):
            try:
                return proof(*args,**kwargs)
            finally:
                self.mutate_layout()
        with patch.object(adapter,'_qualified_source_edit_plan',
                          side_effect=mutate_even_on_refusal):
            with self.assertRaisesRegex(GraphConflict,'Graph revision changed during independent function review'):
                self.review()

    def test_graph_mutation_during_evidence_mapping_refuses_receipt(self):
        evidence=adapter._independent_change_lines
        def mutate_after_evidence(*args,**kwargs):
            result=evidence(*args,**kwargs)
            self.mutate_layout()
            return result
        with patch.object(adapter,'_independent_change_lines',
                          side_effect=mutate_after_evidence):
            with self.assertRaisesRegex(GraphConflict,'Graph revision changed during independent function review'):
                self.review()

    def test_graph_mutation_after_planner_refuses_import_without_partial_edit(self):
        review=self.review()
        plan=adapter._independent_functions_plan
        def mutate_after_plan(*args,**kwargs):
            result=plan(*args,**kwargs)
            self.mutate_layout()
            return result
        with patch.object(adapter,'_independent_functions_plan',
                          side_effect=mutate_after_plan):
            with self.assertRaisesRegex(GraphConflict,'Graph revision changed before independent source import'):
                adapter.import_independent_source_functions(
                    self.graph,self.source,review.functions,
                    expected_graph_revision=review.graph_revision,
                    expected_source_revision=review.source_revision,
                    expected_source_sha256=review.source_sha256)
        self.assertEqual(next(n for n in self.graph.state['nodes']
                              if n['id']=='one')['properties']['value'],1)

    def test_noop_import_still_refuses_graph_mutation_after_planner(self):
        self.path.write_text(self.generated+'\n# unrelated source-only section\n',
                             encoding='utf-8')
        self.source=SourceDocumentSession.open(self.path)
        reviewed=self.review()
        self.assertEqual(reviewed.changes,())
        plan=adapter._independent_functions_plan
        def mutate_after_plan(*args,**kwargs):
            result=plan(*args,**kwargs)
            self.mutate_layout()
            return result
        with patch.object(adapter,'_independent_functions_plan',
                          side_effect=mutate_after_plan):
            with self.assertRaisesRegex(GraphConflict,'Graph revision changed before independent source import'):
                adapter.import_independent_source_functions(
                    self.graph,self.source,reviewed.functions,
                    expected_graph_revision=reviewed.graph_revision,
                    expected_source_revision=reviewed.source_revision,
                    expected_source_sha256=reviewed.source_sha256)


if __name__=='__main__':
    unittest.main()
