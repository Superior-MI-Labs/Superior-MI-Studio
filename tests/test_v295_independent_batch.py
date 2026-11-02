"""Batched independent-region reconciliation: one proof, one graph transaction."""
import tempfile
import unittest
from pathlib import Path
from studio_native.program_graph import ProgramGraph, GraphConflict, ProgramGraphError
from studio_native.python_lowering import (
    preview_python, review_independent_source_functions,
    import_independent_source_functions, review_independent_source_function)
from studio_native.source_editor import SourceDocumentSession

EXAMPLE=Path(__file__).resolve().parents[1]/'examples/qualified-integer-program.smi-graph'

class IndependentFunctionBatchTests(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        self.root=Path(directory.name)
        self.graph=ProgramGraph.open(EXAMPLE)
        base=preview_python(self.graph.state).source
        self.original=base
        compose=base.split('def compose(y):',1)[1].split('\ndef increment(x):')[0]
        increment=base.split('def increment(x):',1)[1]
        self.text=('import math\n\n# source-only functions remain private\n'
                   'def unmodeled():\n    return math.pi\n\n'
                   'def increment(x):'+increment.replace('_smi_value_0 = 1','_smi_value_0 = 42')
                   +'\n\ndef compose(y):'+compose.replace('_smi_value_1 * _smi_value_1','_smi_value_1 + _smi_value_1'))
        self.file=self.root/'foreign.py'
        self.file.write_text(self.text,encoding='utf-8')
        self.session=SourceDocumentSession.open(self.file)

    def review(self,names=('increment','compose')):
        return review_independent_source_functions(self.graph,self.session,names,
            expected_graph_revision=self.graph.revision)

    def apply(self,receipt):
        return import_independent_source_functions(self.graph,self.session,receipt.functions,
            expected_graph_revision=receipt.graph_revision,
            expected_source_revision=receipt.source_revision,
            expected_source_sha256=receipt.source_sha256)

    def test_two_functions_with_reordered_source_are_one_atomic_change(self):
        before=self.graph.state
        undo_before=len(self.graph._undo)
        receipt=self.review()
        self.assertEqual(receipt.functions,('increment','compose'))
        self.assertEqual([c.function for c in receipt.changes],['increment','compose'])
        self.assertEqual([(c.node_id,c.action) for c in receipt.changes],
                         [('one','set_property'),('mul','replace_node_operation')])
        self.assertEqual(receipt.unmodeled_top_level,2)
        self.assertEqual(len(receipt.regions),2)
        self.assertLess(receipt.regions[0][1],receipt.regions[1][1])
        self.assertEqual(self.graph.state,before)
        self.assertEqual(len(self.graph._undo),undo_before)
        self.assertTrue(self.apply(receipt))
        self.assertEqual(self.graph.revision,before['revision']+1)
        self.assertEqual(len(self.graph._undo),undo_before+1)
        self.assertEqual(self.session.text,self.text)
        self.assertEqual(self.file.read_text(encoding='utf-8'),self.text)
        self.assertTrue(self.graph.undo(self.graph.revision))
        self.assertEqual(preview_python(self.graph.state).source,self.original)

    def test_order_of_explicit_names_does_not_change_semantics(self):
        receipt=self.review(('compose','increment'))
        self.assertEqual(receipt.regions[0][0],'compose')
        self.assertEqual({c.function for c in receipt.changes},{'compose','increment'})
        self.assertTrue(self.apply(receipt))

    def test_rejects_unknown_or_duplicate_function_without_mutation(self):
        before=self.graph.state
        for names in ((),('increment','increment'),('increment','missing'),
                      ('not valid',),tuple(['compose']*33)):
            with self.subTest(names=names),self.assertRaises(ProgramGraphError):
                self.review(names)
            self.assertEqual(self.graph.state,before)

    def test_rejects_duplicate_top_level_definition(self):
        self.session.update(self.text+'\ndef compose(y):\n    return y\n')
        with self.assertRaisesRegex(ProgramGraphError,'exactly once'):
            self.review()
        self.assertFalse(self.graph.dirty)

    def test_unsupported_edit_in_one_function_rejects_all_other_edits(self):
        self.session.update(self.text.replace('return _smi_value_2','return 99',1))
        before=self.graph.state
        with self.assertRaises(ProgramGraphError):self.review()
        self.assertEqual(self.graph.state,before)

    def test_unsupported_mutation_of_unselected_function_is_opaque(self):
        # Only increment is selected; compose remains generated in the proof.
        result=self.review(('increment',))
        self.assertEqual([c.function for c in result.changes],['increment'])
        self.assertTrue(self.apply(result))
        self.assertIn('_smi_value_1 + _smi_value_1',self.session.text)

    def test_review_does_not_authorize_stale_source_or_graph(self):
        receipt=self.review()
        self.session.update(self.text+'\n# unrelated comment\n')
        with self.assertRaisesRegex(GraphConflict,'source revision'):
            self.apply(receipt)
        self.session.update(self.text)
        receipt=self.review()
        self.graph.edit(self.graph.revision,'move_node',node='one',x=13,y=26)
        with self.assertRaisesRegex(GraphConflict,'Graph revision'):
            self.apply(receipt)

    def test_external_source_change_refused_at_both_gates(self):
        receipt=self.review()
        self.file.write_text('external mutation\n',encoding='utf-8')
        with self.assertRaises(GraphConflict):self.apply(receipt)
        with self.assertRaises(GraphConflict):self.review()

    def test_noop_selection_does_not_increase_revision(self):
        original=self.session.text
        self.session.update(self.original)
        revision=self.graph.revision
        receipt=self.review()
        self.assertEqual(receipt.changes,())
        self.assertFalse(self.apply(receipt))
        self.assertEqual(self.graph.revision,revision)
        self.assertEqual(self.file.read_text(encoding='utf-8'),original)

    def test_single_function_api_still_returns_old_receipt(self):
        receipt=review_independent_source_function(self.graph,self.session,'increment',
            expected_graph_revision=self.graph.revision)
        self.assertEqual(receipt.function,'increment')
        self.assertEqual(len(receipt.changes),1)

    def test_decorated_function_refused_not_silently_stripped(self):
        self.session.update(self.text.replace('def increment(x):','@staticmethod\ndef increment(x):'))
        with self.assertRaisesRegex(ProgramGraphError,'Decorated'):
            self.review()

if __name__=='__main__':unittest.main()
