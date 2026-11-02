"""Refusal diagnostics are read-only compiler witnesses, not new edit authority."""
from __future__ import annotations

import ast
from pathlib import Path
import tempfile
import unittest

from studio_native.program_graph import ProgramGraphError
from studio_native.python_lowering import (
    _source_ast_mismatch, preview_python, review_generated_source_edit,
    review_independent_source_functions, import_independent_source_functions,
)
from studio_native.source_editor import SourceDocumentSession
from tests.test_v2102_semantic_input_reconciliation import Harness


class SourceMismatchDiagnostics(unittest.TestCase):
    def test_ast_name_change_is_structural_and_located(self):
        expected = ast.parse('def f(x):\n    return x\n')
        actual = ast.parse('def f(x):\n    return different\n')
        original = ast.dump(actual, include_attributes=False)
        message = _source_ast_mismatch(expected, actual)
        self.assertIn('module.body[0].body[0].value.id', message)
        self.assertIn('candidate AST line 2', message)
        self.assertIn("'different'", message)
        self.assertEqual(ast.dump(actual, include_attributes=False), original)

    def test_added_statement_reports_structural_length(self):
        left = ast.parse('def f(x):\n    return x\n')
        right = ast.parse('def f(x):\n    return x\n    x = 9\n')
        message = _source_ast_mismatch(left, right)
        self.assertIn('1 statements vs 2 statements', message)
        self.assertIn('module.body[0].body', message)

    def test_changed_control_structure_reports_node_kind(self):
        left = ast.parse('def f(x):\n    return x\n')
        right = ast.parse('def f(x):\n    if x:\n        return x\n')
        message = _source_ast_mismatch(left, right)
        self.assertIn('Return vs If', message)
        self.assertIn('candidate AST line 2', message)

    def test_no_change_and_formatting_are_not_described_as_semantic_change(self):
        left = ast.parse('def f(x): return x')
        right = ast.parse('def f(x):\n  return (x)\n')
        self.assertIn('no syntax difference', _source_ast_mismatch(left, right))

    def test_bound_output_for_large_string(self):
        left = ast.parse('def f():\n    return "short"\n')
        right = ast.parse('def f():\n    return "' + 'A' * 10000 + '"\n')
        message = _source_ast_mismatch(left, right)
        self.assertLess(len(message), 300)
        self.assertIn('first mismatch', message)

    def test_nested_structure_has_bounded_depth(self):
        # Direct AST utility can encounter a deeper tree than the compiler's
        # normal supported subset. It must stay bounded for diagnostics.
        left = ast.parse('x')
        right = ast.parse('x')
        for _ in range(90):
            left = ast.UnaryOp(op=ast.Not(), operand=left)
            right = ast.UnaryOp(op=ast.Not(), operand=right)
        self.assertIn('diagnostic depth', _source_ast_mismatch(left, right))


class ReconciliationErrorIntegration(unittest.TestCase):
    def setUp(self):
        self.h = Harness(name='compute', return_type='py:int')
        self.h.parameter('x')
        self.h.parameter('y')
        self.h.node('sum', 'python.add')
        self.h.node('ret', 'python.return')
        self.h.wire('x', 'sum', 'left')
        self.h.wire('y', 'sum', 'right')
        self.h.wire('sum', 'ret', 'value')
        self.base = self.h.source()

    def session(self, text):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / 'user.py'
        path.write_text(text, encoding='utf-8')
        return SourceDocumentSession.open(path)

    def test_syntax_error_reports_line_and_column_without_mutation(self):
        before = self.h.graph.state
        bad = self.base.replace(' + ', ' + (')
        with self.assertRaisesRegex(ProgramGraphError, 'Edited Python syntax at line .*column'):
            review_generated_source_edit(self.h.graph, self.base, bad,
                                         expected_revision=self.h.graph.revision)
        self.assertEqual(before, self.h.graph.state)

    def test_unknown_operand_in_independent_source_names_function(self):
        edited = self.base.replace(' + _smi_value_1', ' + unknown_value')
        session = self.session('import math\n\n' + edited + '\n# unrelated\n')
        before = self.h.graph.state
        with self.assertRaisesRegex(ProgramGraphError, "Function 'compute' \\(source lines") as caught:
            review_independent_source_functions(self.h.graph, session, ('compute',),
                                                expected_graph_revision=self.h.graph.revision)
        self.assertIn('first mismatch', str(caught.exception))
        self.assertIn('unknown_value', str(caught.exception))
        self.assertEqual(before, self.h.graph.state)
        self.assertIn('unknown_value', session.text)

    def test_unsupported_new_statement_refuses_and_identifies_mismatch(self):
        edited = self.base.replace('    return ', '    print("effect")\n    return ')
        session = self.session('# source-owned\n' + edited)
        with self.assertRaisesRegex(ProgramGraphError, 'first mismatch'):
            review_independent_source_functions(self.h.graph, session, ('compute',),
                                                expected_graph_revision=self.h.graph.revision)
        self.assertIn('print("effect")', session.text)

    def test_valid_wire_edit_still_imports_with_revisions(self):
        # A compatible operator replacement preserves all producers and node
        # identities; this is the positive control for the refusal diagnostics.
        edited = self.base.replace(' + _smi_value_1', ' - _smi_value_1')
        session = self.session('# untouched source header\n' + edited)
        review = review_independent_source_functions(self.h.graph, session, ('compute',),
                                                     expected_graph_revision=self.h.graph.revision)
        self.assertEqual([(c.node_id, c.action, c.input_port) for c in review.changes],
                         [('sum', 'replace_node_operation', None)])
        original = self.h.graph.state
        self.assertTrue(import_independent_source_functions(self.h.graph, session, review.functions,
            expected_graph_revision=review.graph_revision,
            expected_source_revision=review.source_revision,
            expected_source_sha256=review.source_sha256))
        self.assertEqual(session.text, '# untouched source header\n' + edited)
        self.assertTrue(self.h.graph.undo(self.h.graph.revision))
        self.assertEqual(original['edges'], self.h.graph.state['edges'])
        self.assertEqual(original['nodes'], self.h.graph.state['nodes'])


if __name__ == '__main__':
    unittest.main()
