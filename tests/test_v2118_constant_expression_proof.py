"""Bounded constant arithmetic: source-owned syntax, compiler-owned graph proof."""
import tempfile
import unittest
from pathlib import Path

from studio_native.program_graph import GraphConflict, ProgramGraphError
from studio_native.python_lowering import (
    preview_python, review_generated_source_edit, review_independent_source_functions,
    import_independent_source_functions)
from studio_native.source_editor import SourceDocumentSession
from tests.test_v2106_state_and_repeat_reconciliation import fixture


class ConstantExpressionProofTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'authored.py'
        self.graph,self.base,_,_=fixture('bind')
        self.original=self.graph.state
        self.anchor='    _smi_value_0 = 3'
        self.assertEqual(self.base.count(self.anchor),1)

    def source(self,expression, *, prefix=''):
        text=prefix+self.base.replace(self.anchor,'    _smi_value_0 = '+expression)
        self.path.write_text(text,encoding='utf-8')
        return SourceDocumentSession.open(self.path),text

    def review(self,expression, *, prefix=''):
        session,text=self.source(expression,prefix=prefix)
        receipt=review_independent_source_functions(self.graph,session,('capture',),
            expected_graph_revision=self.graph.revision)
        return session,text,receipt

    def test_nested_arithmetic_literal_import_is_one_undoable_graph_change(self):
        session,text,review=self.review('(2 + 3) * 4',prefix='import math\n# source owns this\n')
        self.assertEqual([(c.action,c.before,c.after) for c in review.changes],
                         [('set_property',3,20)])
        self.assertEqual(self.graph.state,self.original)
        self.assertTrue(import_independent_source_functions(self.graph,session,review.functions,
            expected_graph_revision=review.graph_revision,
            expected_source_revision=review.source_revision,
            expected_source_sha256=review.source_sha256))
        self.assertIn('_smi_value_0 = 20',preview_python(self.graph.state).source)
        self.assertEqual(session.text,text)
        self.assertEqual(self.path.read_text(),text)
        self.assertTrue(self.graph.undo(self.graph.revision))
        self.assertEqual(self.graph.state['nodes'],self.original['nodes'])
        self.assertTrue(self.graph.redo(self.graph.revision))
        self.assertIn('_smi_value_0 = 20',preview_python(self.graph.state).source)

    def test_equivalent_arithmetic_remains_source_only(self):
        session,text,review=self.review('1 + 2')
        self.assertEqual(review.changes,())
        self.assertEqual(session.text,text)
        self.assertEqual(self.graph.state,self.original)

    def test_signed_integer_python_semantics(self):
        for expr,expected in [('2 * 7',14), ('-7 // 3',-3),
                              ('-7 % 3',2), ('2 + -(3 * 4)',-10),
                              ('+5 - 9',-4), ('8 // -3',-3)]:
            with self.subTest(expr=expr):
                _,_,receipt=self.review(expr)
                self.assertEqual([(c.before,c.after) for c in receipt.changes],[(3,expected)])
                self.assertEqual(self.graph.state,self.original)

    def test_source_evidence_is_original_expression(self):
        session,text,receipt=self.review('(2 + 3) * 4')
        self.assertEqual(len(receipt.change_spans),1)
        _,_,first,col,last,end=receipt.change_spans[0]
        self.assertEqual(first,last)
        self.assertEqual(text.splitlines()[first-1][col-1:end-1],'(2 + 3) * 4')

    def test_generated_source_import_remains_strict(self):
        changed=self.base.replace(self.anchor,'    _smi_value_0 = 2 * 7')
        with self.assertRaises(ProgramGraphError):
            review_generated_source_edit(self.graph,self.base,changed,
                                         expected_revision=self.graph.revision)

    def test_unqualified_expressions_refuse_without_mutation(self):
        cases=('1 / 2','1 // 0','2 % 0','2 ** 3','1 << 2',
               '1 + True','float(3)','True + 3','2 ** 9000000',
               '9223372036854775807 + 1','(-9223372036854775807) * 2',
               '2 + unknown','1.5 + 2','(1, 2)[0]','2 @ 3')
        for expr in cases:
            with self.subTest(expr=expr):
                with self.assertRaises(ProgramGraphError):
                    self.review(expr)
                self.assertEqual(self.graph.state,self.original)

    def test_annotated_readable_local_and_expression_share_one_proof(self):
        text=self.base.replace('_smi_value_0','starting_amount').replace(
            'starting_amount = 3','starting_amount: int = (1 + 2)')
        self.path.write_text(text,encoding='utf-8')
        session=SourceDocumentSession.open(self.path)
        receipt=review_independent_source_functions(self.graph,session,('capture',),
            expected_graph_revision=self.graph.revision)
        self.assertEqual(receipt.changes,())
        self.assertEqual(session.text,text)
        self.assertEqual(self.graph.state,self.original)

    def test_docstring_and_computed_literal_still_import_atomically(self):
        text=self.base.replace('def capture():\n',
            'def capture():\n    """Source-only function documentation."""\n    pass\n')
        text=text.replace(self.anchor,'    _smi_value_0: int = (5 + 2) * 3')
        self.path.write_text(text,encoding='utf-8')
        session=SourceDocumentSession.open(self.path)
        receipt=review_independent_source_functions(self.graph,session,('capture',),
            expected_graph_revision=self.graph.revision)
        self.assertEqual([(c.before,c.after) for c in receipt.changes],[(3,21)])
        self.assertTrue(import_independent_source_functions(self.graph,session,receipt.functions,
            expected_graph_revision=receipt.graph_revision,
            expected_source_revision=receipt.source_revision,
            expected_source_sha256=receipt.source_sha256))
        self.assertEqual(session.text,text)
        self.assertEqual(self.path.read_text(),text)

    def test_obsolete_source_receipt_refuses_after_graph_revision_changes(self):
        session,text,receipt=self.review('2 * 7')
        self.graph.edit(self.graph.revision,'set_property',node='two',key='value',value=5)
        with self.assertRaises(GraphConflict):
            import_independent_source_functions(self.graph,session,receipt.functions,
                expected_graph_revision=receipt.graph_revision,
                expected_source_revision=receipt.source_revision,
                expected_source_sha256=receipt.source_sha256)

    def test_external_file_change_refuses_atomic_commit(self):
        session,text,review=self.review('2 * 7')
        self.path.write_text(text+'\n# external edit',encoding='utf-8')
        with self.assertRaises(GraphConflict):
            import_independent_source_functions(self.graph,session,review.functions,
                expected_graph_revision=review.graph_revision,
                expected_source_revision=review.source_revision,
                expected_source_sha256=review.source_sha256)
        self.assertEqual(self.graph.state,self.original)

    def test_expression_inside_counted_control_flow_preserves_control(self):
        graph,baseline,_,_=fixture('repeat')
        anchor='    _smi_value_1 = 0'
        self.assertEqual(baseline.count(anchor),1)
        candidate=baseline.replace(anchor,'    _smi_value_1 = (2 + 3) - 5')
        self.path.write_text(candidate,encoding='utf-8')
        session=SourceDocumentSession.open(self.path)
        receipt=review_independent_source_functions(graph,session,('count_up',),
            expected_graph_revision=graph.revision)
        self.assertEqual(receipt.changes,())
        self.assertEqual(session.text,candidate)
        self.assertIn('for _smi_repeat_index_0 in',candidate)


if __name__=='__main__':
    unittest.main()
