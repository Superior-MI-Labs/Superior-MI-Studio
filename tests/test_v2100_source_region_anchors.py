"""Independent Python correspondence: explicit binding identity and exact source receipts.

This suite does not make unmodeled Python graph-owned. It tests refusal and
advisory source locations before/after the compiler's existing full AST proof.
"""
import tempfile
import unittest
from pathlib import Path

from studio_native.program_graph import ProgramGraph, ProgramGraphError, GraphConflict
from studio_native.python_lowering import (
    preview_python, review_independent_source_functions,
    review_independent_source_function, import_independent_source_functions)
from studio_native.source_editor import SourceDocumentSession

EXAMPLE=Path(__file__).resolve().parents[1]/'examples/qualified-integer-program.smi-graph'


class IndependentSourceRegionEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'external.py'
        self.graph=ProgramGraph.open(EXAMPLE)
        generated=preview_python(self.graph.state).source
        self.assertIsNotNone(generated)
        self.original=generated
        self.changed=generated.replace('_smi_value_0 = 1', '_smi_value_0 = -17')
        self.assertNotEqual(self.changed, generated)
        self.session=self.open('import math\n\n'+self.changed)

    def open(self,text):
        self.path.write_text(text,encoding='utf-8')
        return SourceDocumentSession.open(self.path)

    def review(self,names=('increment',)):
        return review_independent_source_functions(self.graph,self.session,names,
            expected_graph_revision=self.graph.revision)

    def test_original_line_and_column_refer_to_exact_authored_assignment(self):
        receipt=self.review()
        self.assertEqual(len(receipt.changes),1)
        self.assertEqual(len(receipt.change_lines),1)
        self.assertEqual(len(receipt.change_spans),1)
        function,node,line,start,end_line,end=receipt.change_spans[0]
        self.assertEqual((function,node),('increment','one'))
        self.assertEqual((function,node,line),receipt.change_lines[0])
        self.assertEqual(line,end_line)
        statement=self.session.text.splitlines()[line-1]
        self.assertEqual(statement[start-1:end-1], '-17')
        self.assertTrue(start>1)
        self.assertEqual(self.graph.revision,self.graph.state['revision'])
        self.assertEqual(self.path.read_text(),self.session.text)

    def test_multi_function_source_reordering_and_trivia_have_exact_spans(self):
        generated=self.original
        compose=generated.split('def compose(y):',1)[1].split('\ndef increment(x):')[0]
        increment=generated.split('def increment(x):',1)[1]
        changed=('import math\n\n# comment\n'
                 'def increment(x):'+increment.replace('_smi_value_0 = 1','_smi_value_0 = -17')+
                 '\n\ndef compose(y):'+compose.replace(' * ',' % '))
        self.session.update(changed)
        receipt=self.review(('increment','compose'))
        self.assertEqual(len(receipt.changes),2)
        self.assertEqual(len(receipt.change_spans),2)
        for function,node,line,start,end_line,end in receipt.change_spans:
            source=self.session.text.splitlines()[line-1]
            segment=source[start-1:end-1]
            # v2.108 selects the edited expression instead of the complete
            # generated assignment (which was previously overly broad).
            self.assertTrue(segment == '-17' or '_smi_value_' in segment)
            self.assertEqual(line,end_line)
        original_graph=self.graph.state
        self.assertTrue(import_independent_source_functions(self.graph,self.session,receipt.functions,
            expected_graph_revision=receipt.graph_revision,
            expected_source_revision=receipt.source_revision,
            expected_source_sha256=receipt.source_sha256))
        self.assertEqual(self.session.text,changed)
        self.assertEqual(self.path.read_text(),('import math\n\n'+self.changed))
        self.assertTrue(self.graph.undo(self.graph.revision))
        self.assertEqual(self.graph.state['nodes'],original_graph['nodes'])

    def test_explicit_module_binding_shadows_graph_function_refused(self):
        examples=(
            'increment = 9',
            'increment: object = None',
            'del increment',
            'from utility import increment',
            'from utility import item as increment',
            'import utility as increment',
            'from utility import *',
            'class increment: pass',
            'if 1:\n    increment = 99',
            'if 1:\n    def increment(): pass',
            'try:\n    pass\nexcept Exception as increment:\n    pass',
            'for increment in []: pass',
            'match 1:\n    case increment:\n        pass',
            'values = [(increment := n) for n in range(2)]',
            'values = {n: (increment := n) for n in range(2)}',
        )
        for suffix in examples:
            with self.subTest(suffix=suffix):
                self.session.update('import math\n\n'+self.changed+'\n'+suffix+'\n')
                original=self.graph.state
                with self.assertRaisesRegex(ProgramGraphError,'module-scope binding shadows selected') as failure:
                    self.review()
                self.assertIn('line(s)',str(failure.exception))
                self.assertEqual(self.graph.state,original)
                self.assertFalse(self.graph.dirty)

    def test_function_local_bindings_do_not_shadow_top_level(self):
        self.session.update('import math\n\n'+self.changed+'\n'
            'def extra():\n    increment = 27\n    class increment: pass\n'
            '    return increment\n\n'
            'values = [increment for increment in []]\n'
            'later = [(lambda increment: increment)(1) for _ in []]\n')
        self.assertEqual([c.node_id for c in self.review().changes],['one'])

    def test_shadowing_detected_before_noop_graph_import(self):
        self.session.update(self.original+'\nincrement = 99\n')
        with self.assertRaisesRegex(ProgramGraphError,'shadows selected'):
            self.review()

    def test_stale_review_still_refused_even_when_new_region_looks_identical(self):
        receipt=self.review()
        self.session.update(self.session.text+'\n# separate source change')
        with self.assertRaisesRegex(GraphConflict,'source revision'):
            import_independent_source_functions(self.graph,self.session,receipt.functions,
                expected_graph_revision=receipt.graph_revision,
                expected_source_revision=receipt.source_revision,
                expected_source_sha256=receipt.source_sha256)
        self.assertFalse(self.graph.dirty)

    def test_one_function_api_exposes_same_span_receipt(self):
        item=review_independent_source_function(self.graph,self.session,'increment',
            expected_graph_revision=self.graph.revision)
        self.assertEqual(len(item.change_spans),1)
        self.assertEqual(item.change_spans[0][:3],item.change_lines[0])


if __name__=='__main__':
    unittest.main()
