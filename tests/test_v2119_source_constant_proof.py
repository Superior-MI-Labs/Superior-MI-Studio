"""Conditional expression and text literal proof never executes authored Python."""
import tempfile
import unittest
from pathlib import Path
from studio_native.program_graph import ProgramGraphError
from studio_native.python_lowering import (
    preview_python, review_independent_source_functions,
    import_independent_source_functions, review_generated_source_edit)
from studio_native.source_editor import SourceDocumentSession
from tests.test_v2102_semantic_input_reconciliation import Harness


class SourceConstantProof(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.file=Path(self.temp.name)/'source.py'

    def model(self, value, return_type):
        h=Harness(name='compute',return_type=return_type)
        h.node('literal','python.literal',{'value':value})
        h.node('ret','python.return')
        h.wire('literal','ret','value')
        original=h.graph.state
        base=h.source()
        expected=' = '+repr(value)
        self.assertEqual(base.count(expected),1)
        return h,original,base,expected

    def review(self, model, expression):
        h,original,base,anchor=model
        edited=base.replace(anchor,' = '+expression,1)
        self.file.write_text(edited,encoding='utf-8')
        session=SourceDocumentSession.open(self.file)
        receipt=review_independent_source_functions(h.graph,session,('compute',),
            expected_graph_revision=h.graph.revision)
        self.assertEqual(h.graph.state,original)
        return session,edited,receipt

    def test_integer_conditional_literal_and_nested_arithmetic(self):
        model=self.model(3,'py:int')
        for expr,expected in [
            ('(2 + 3) * 4 if 2 < 3 else 9',20),
            ('8 if False else -7 // 3',-3),
            ('3 if True else 99',3),
            ('(10 if True else 20) + 1',11),
        ]:
            with self.subTest(expr=expr):
                _,_,receipt=self.review(model,expr)
                self.assertEqual([c.after for c in receipt.changes],
                                 [expected] if expected!=3 else [])

    def test_boolean_conditional_with_full_proof(self):
        model=self.model(False,'py:bool')
        for expr,result in [
            ('(2 < 3) if not False else (3 == 4)',True),
            ('False if True else True',False),
            ('(1 + 1) == 2 if True else False',True),
        ]:
            with self.subTest(expr=expr):
                _,_,receipt=self.review(model,expr)
                self.assertEqual([c.after for c in receipt.changes],
                                 [True] if result else [])

    def test_explicit_import_is_atomic_undoable_and_preserves_source(self):
        h,original,base,anchor=self.model(3,'py:int')
        session,source,receipt=self.review((h,original,base,anchor),
            '7 if True else (2 + 1)')
        self.assertEqual(len(receipt.changes),1)
        self.assertTrue(import_independent_source_functions(
            h.graph,session,receipt.functions,
            expected_graph_revision=receipt.graph_revision,
            expected_source_revision=receipt.source_revision,
            expected_source_sha256=receipt.source_sha256))
        self.assertEqual(session.text,source)
        self.assertEqual(self.file.read_text(),source)
        self.assertIn(' = 7',preview_python(h.graph.state).source)
        self.assertTrue(h.graph.undo(h.graph.revision))
        self.assertEqual(h.graph.state['nodes'],original['nodes'])
        with self.assertRaises(ProgramGraphError):
            review_generated_source_edit(h.graph,base,source,
                expected_revision=h.graph.revision)

    def test_effectful_unsupported_or_mismatched_branches_refuse(self):
        for model,expression in [
            (self.model(3,'py:int'), '3 if True else dangerous()'),
            (self.model(3,'py:int'), '3 if unknown else 4'),
            (self.model(3,'py:int'), '3 if 1 else 4'),
            (self.model(3,'py:int'), '3 if True else False'),
            (self.model(3,'py:int'), '3 if True else 2.0'),
            (self.model(3,'py:int'), '3 if False else 2 / 0'),
            (self.model(3,'py:int'), '3 if True else 1 << 2'),
            (self.model(3,'py:int'), "'X' + 'Y'"),
            (self.model(3,'py:int'), "'a' if True else 'b'"),
        ]:
            with self.subTest(expression=expression), self.assertRaises(ProgramGraphError):
                self.review(model,expression)

    def test_oversized_authored_function_refuses_without_mutation(self):
        model=self.model(3,'py:int')
        h,original,base,anchor=model
        # 2,100 assignments require more than 4,096 AST nodes. The graph
        # remains small; only the untrusted source-proof AST is excessive.
        oversized=''.join(f'    unused_{i} = {i}\n' for i in range(2100))
        statement='    _smi_value_0 = 3'
        self.assertEqual(base.count(statement),1)
        text=base.replace(statement,oversized+statement,1)
        self.file.write_text(text,encoding='utf-8')
        session=SourceDocumentSession.open(self.file)
        with self.assertRaisesRegex(ProgramGraphError,'AST exceeds'):
            review_independent_source_functions(h.graph,session,('compute',),
                expected_graph_revision=h.graph.revision)
        self.assertEqual(h.graph.state,original)

    def test_no_graph_change_on_existing_value(self):
        model=self.model(3,'py:int')
        _,_,receipt=self.review(model,'3 if True else 4')
        self.assertFalse(receipt.changes)


if __name__=='__main__': unittest.main()
