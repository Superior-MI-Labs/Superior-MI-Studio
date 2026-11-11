"""Public generated-source reviews/imports must not inherit a newer graph revision."""
import unittest
from pathlib import Path
from unittest.mock import patch

from studio_native import python_lowering as adapter
from studio_native.program_graph import ProgramGraph, GraphConflict

EXAMPLE=Path(__file__).resolve().parents[1]/'examples/qualified-integer-program.smi-graph'


class GeneratedSourceGraphReceiptTests(unittest.TestCase):
    def setUp(self):
        self.graph=ProgramGraph.open(EXAMPLE)
        self.revision=self.graph.revision
        self.base=adapter.preview_python(self.graph.state).source
        self.assertIsNotNone(self.base)
        self.edit=self.base.replace('_smi_value_0 = 1','_smi_value_0 = 35',1)
        self.assertNotEqual(self.edit,self.base)

    def move_graph(self):
        self.assertTrue(self.graph.edit(self.graph.revision,'move_node',
                                        node='one',x=613,y=273))

    def review(self,edit=None):
        return adapter.review_generated_source_edit(
            self.graph,self.base,self.edit if edit is None else edit,
            expected_revision=self.revision)

    def import_edit(self,edit=None):
        return adapter.import_generated_source_edit(
            self.graph,self.base,self.edit if edit is None else edit,
            expected_revision=self.revision)

    def test_valid_generated_source_still_reviewed_and_imported(self):
        review=self.review()
        self.assertEqual(review.graph_revision,self.revision)
        self.assertTrue(review.changes)
        self.assertTrue(self.import_edit())
        self.assertEqual(self.graph.revision,self.revision+1)
        self.assertEqual(next(n for n in self.graph.state['nodes']
                              if n['id']=='one')['properties']['value'],35)

    def test_unchanged_generated_source_remains_noop_without_mutation(self):
        self.assertFalse(self.import_edit(self.base))
        self.assertEqual(self.graph.revision,self.revision)

    def test_review_refuses_graph_mutated_after_successful_proof(self):
        actual=adapter._qualified_source_edit_plan
        def move_after_proof(*args,**kwargs):
            result=actual(*args,**kwargs)
            self.move_graph()
            return result
        with patch.object(adapter,'_qualified_source_edit_plan',
                          side_effect=move_after_proof):
            with self.assertRaisesRegex(GraphConflict,
                                        'Graph revision changed during generated source review'):
                self.review()
        self.assertEqual(next(n for n in self.graph.state['nodes']
                              if n['id']=='one')['properties']['value'],1)

    def test_real_edit_import_refuses_graph_mutated_after_proof(self):
        actual=adapter._qualified_source_edit_plan
        def move_after_proof(*args,**kwargs):
            result=actual(*args,**kwargs)
            self.move_graph()
            return result
        with patch.object(adapter,'_qualified_source_edit_plan',
                          side_effect=move_after_proof):
            with self.assertRaisesRegex(GraphConflict,
                                        'Graph revision changed during generated source import'):
                self.import_edit()
        self.assertEqual(next(n for n in self.graph.state['nodes']
                              if n['id']=='one')['properties']['value'],1)

    def test_noop_import_refuses_graph_mutated_after_proof(self):
        actual=adapter._qualified_source_edit_plan
        def move_after_noop(*args,**kwargs):
            result=actual(*args,**kwargs)
            self.move_graph()
            return result
        with patch.object(adapter,'_qualified_source_edit_plan',
                          side_effect=move_after_noop):
            with self.assertRaisesRegex(GraphConflict,
                                        'Graph revision changed during generated source import'):
                self.import_edit(self.base)

    def test_review_refuses_stale_failure_diagnostic_after_graph_mutation(self):
        actual=adapter._qualified_source_edit_plan
        def move_on_failure(*args,**kwargs):
            try:
                return actual(*args,**kwargs)
            finally:
                self.move_graph()
        with patch.object(adapter,'_qualified_source_edit_plan',
                          side_effect=move_on_failure):
            with self.assertRaisesRegex(GraphConflict,
                                        'Graph revision changed during generated source review'):
                self.review(self.base+'\nraise ValueError("unsupported")\n')

    def test_import_refuses_stale_failure_diagnostic_after_graph_mutation(self):
        actual=adapter._qualified_source_edit_plan
        def move_on_failure(*args,**kwargs):
            try:
                return actual(*args,**kwargs)
            finally:
                self.move_graph()
        with patch.object(adapter,'_qualified_source_edit_plan',
                          side_effect=move_on_failure):
            with self.assertRaisesRegex(GraphConflict,
                                        'Graph revision changed during generated source import'):
                self.import_edit(self.base+'\nraise ValueError("unsupported")\n')


if __name__=='__main__':
    unittest.main()
