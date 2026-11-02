"""One explicitly selected independently authored function, not arbitrary Python import."""
import tempfile
import unittest
from pathlib import Path

from studio_native.program_graph import ProgramGraph, ProgramGraphError, GraphConflict
from studio_native.python_lowering import (
    preview_python,review_independent_source_function,import_independent_source_function)
from studio_native.source_editor import SourceDocumentSession

EXAMPLE=Path(__file__).resolve().parents[1]/'examples/qualified-integer-program.smi-graph'

class IndependentFunctionRegionTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.folder=Path(tmp.name)
        self.graph=ProgramGraph.open(EXAMPLE)
        self.base=preview_python(self.graph.state).source
        self.source=self.folder/'independent.py'
        # Not a generated file: function order, unrelated helpers and source
        # trivia are independently owned and must never be rewritten.
        self.text=('import math\n\ndef unrelated():\n    return math.pi\n\n'
            'def increment(x):\n    _smi_value_0 = 25\n    _smi_value_1 = x\n'
            '    _smi_value_2 = _smi_value_1 * _smi_value_0\n    return _smi_value_2\n')
        self.source.write_text(self.text,encoding='utf-8')
        self.session=SourceDocumentSession.open(self.source)

    def review(self):
        return review_independent_source_function(self.graph,self.session,'increment',
            expected_graph_revision=self.graph.revision)

    def apply(self,receipt):
        return import_independent_source_function(self.graph,self.session,'increment',
            expected_graph_revision=receipt.graph_revision,
            expected_source_revision=receipt.source_revision,
            expected_source_sha256=receipt.source_sha256)

    def test_independent_function_review_and_atomic_import_leave_source_unmodified(self):
        before=self.graph.state
        review=self.review()
        self.assertEqual([(x.function,x.node_id,x.action) for x in review.changes],
                         [('increment','one','set_property'),('increment','add','replace_node_operation')])
        self.assertEqual(review.unmodeled_top_level,2)
        self.assertEqual(self.graph.state,before)
        self.assertTrue(self.apply(review))
        self.assertEqual(self.graph.revision,before['revision']+1)
        self.assertEqual(self.source.read_text(),self.text)
        self.assertEqual(self.session.text,self.text)
        self.assertIn('return _smi_value_2',preview_python(self.graph.state).source)
        self.assertTrue(self.graph.undo(self.graph.revision))
        self.assertEqual(preview_python(self.graph.state).source,self.base)

    def test_independent_source_revision_change_after_review_refused(self):
        review=self.review();before=self.graph.state
        self.session.update(self.text.replace('25','27'))
        with self.assertRaisesRegex(GraphConflict,'source revision'):
            self.apply(review)
        self.assertEqual(self.graph.state,before)

    def test_independent_graph_revision_change_after_review_refused(self):
        review=self.review()
        self.graph.edit(self.graph.revision,'move_node',node='one',x=22,y=12)
        before=self.graph.state
        with self.assertRaisesRegex(GraphConflict,'Graph revision'):
            self.apply(review)
        self.assertEqual(self.graph.state,before)

    def test_unsupported_function_edits_never_import(self):
        for rewritten in (self.text.replace('return _smi_value_2','return 999'),
                          self.text.replace('def increment(x):','def increment(x, y):'),
                          self.text.replace('    return _smi_value_2','    print("side effect")\n    return _smi_value_2')):
            with self.subTest(rewritten=rewritten),self.assertRaises(ProgramGraphError):
                self.session.update(rewritten)
                self.review()
        self.assertFalse(self.graph.dirty)

    def test_duplicate_named_function_refused(self):
        self.session.update(self.text+'\ndef increment(x):\n    return 99\n')
        with self.assertRaisesRegex(ProgramGraphError,'exactly once'):
            self.review()

    def test_external_source_change_refused_without_graph_mutation(self):
        before=self.graph.state
        self.source.write_text('external override\n',encoding='utf-8')
        with self.assertRaises(GraphConflict):self.review()
        self.assertEqual(before,self.graph.state)

    def test_invalid_python_elsewhere_refused_without_graph_mutation(self):
        self.session.update('def broken(:\n'+self.text)
        with self.assertRaises(ProgramGraphError):self.review()
        self.assertFalse(self.graph.dirty)

    def test_function_actions_extend_existing_menu_not_toolbar(self):
        source=(Path(__file__).resolve().parents[1]/'studio_native/gui.py').read_text()
        menu=source.split('    def function_menu(',1)[1].split('    def rename_function(',1)[0]
        self.assertIn('Review independent .py function',menu)
        self.assertIn('Import reviewed function',menu)
        bar=source.split('    def __init__(self,window,document: ProgramGraph):',1)[1].split('    def function_menu(',1)[0]
        self.assertNotIn("('Review independent .py function',",bar)

    def test_unknown_named_region_refused(self):
        with self.assertRaisesRegex(ProgramGraphError,'exactly once'):
            review_independent_source_function(self.graph,self.session,'unrelated',
                expected_graph_revision=self.graph.revision)

if __name__=='__main__':unittest.main()
