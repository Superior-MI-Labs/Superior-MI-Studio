"""Bounded Boolean source spelling normalizes only a transient proof candidate."""
import tempfile
import unittest
from pathlib import Path
from studio_native.program_graph import ProgramGraphError
from studio_native.python_lowering import (review_independent_source_functions,
    import_independent_source_functions, preview_python, review_generated_source_edit)
from studio_native.source_editor import SourceDocumentSession
from tests.test_v2102_semantic_input_reconciliation import Harness

class BooleanExpressionProofTests(unittest.TestCase):
    def setUp(self):
        self.h=Harness(name='flag',return_type='py:bool')
        self.h.node('flag-value','python.literal',{'value':False})
        self.h.node('result','python.return')
        self.h.wire('flag-value','result','value')
        self.base=self.h.source()
        self.assertIn(' = False',self.base)
        self.initial=self.h.graph.state
        self.directory=tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path=Path(self.directory.name)/'authored.py'

    def review(self, expression):
        source=self.base.replace(' = False', ' = '+expression,1)
        self.path.write_text(source,encoding='utf-8')
        session=SourceDocumentSession.open(self.path)
        receipt=review_independent_source_functions(self.h.graph,session,('flag',),
            expected_graph_revision=self.h.graph.revision)
        return session,source,receipt

    def test_fixed_boolean_comparisons_normalize_to_existing_literal(self):
        for expression,result in [('2 < 3',True),('3 <= 2',False),('3 > 2',True),
                                  ('3 >= 4',False),('3 == 3',True),('2 != 2',False),
                                  ('(2 * 3) == 6',True),('not False',True),
                                  ('True or False',True),('True and False',False)]:
            with self.subTest(expression=expression):
                _,_,receipt=self.review(expression)
                self.assertEqual([c.after for c in receipt.changes],
                                 [result] if result else [])
                self.assertEqual(self.h.graph.state,self.initial)

    def test_true_comparison_import_is_undoable_and_source_owned(self):
        session,text,receipt=self.review('(2 + 3) == 5')
        self.assertEqual(len(receipt.changes),1)
        self.assertEqual((receipt.changes[0].before,receipt.changes[0].after),(False,True))
        self.assertTrue(import_independent_source_functions(self.h.graph,session,receipt.functions,
            expected_graph_revision=receipt.graph_revision,
            expected_source_revision=receipt.source_revision,
            expected_source_sha256=receipt.source_sha256))
        self.assertEqual(session.text,text)
        self.assertEqual(self.path.read_text(),text)
        self.assertIn(' = True',preview_python(self.h.graph.state).source)
        self.assertTrue(self.h.graph.undo(self.h.graph.revision))
        self.assertEqual(self.h.graph.state['nodes'],self.initial['nodes'])
        with self.assertRaises(ProgramGraphError):
            review_generated_source_edit(self.h.graph,self.base,text,
                expected_revision=self.h.graph.revision)

    def test_unsupported_boolean_shapes_do_not_execute_or_guess(self):
        cases=('2 < 3 < 4','2 == True','True == 1','2 in (2,3)',
               'foo() or True','False and dangerous()',
               'not flag','3 is 3','True | False','True + False',
               '2.0 <= 3','2 > unknown','not (2 / 0)')
        for expression in cases:
            with self.subTest(expression=expression),self.assertRaises(ProgramGraphError):
                self.review(expression)
            self.assertEqual(self.h.graph.state,self.initial)

if __name__=='__main__': unittest.main()
