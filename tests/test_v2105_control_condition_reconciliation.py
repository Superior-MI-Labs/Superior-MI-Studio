"""Compiler-owned rewiring for existing Branch/Require conditions, no AST owner."""
import tempfile
import unittest
from pathlib import Path

from studio_native.program_graph import GraphConflict, ProgramGraphError
from studio_native.python_lowering import (
    preview_python, review_generated_source_edit, import_generated_source_edit,
    review_independent_source_functions, import_independent_source_functions,
)
from studio_native.source_editor import SourceDocumentSession
from tests.test_v2102_semantic_input_reconciliation import Harness


class ControlConditionReconciliationTests(unittest.TestCase):
    def setUp(self):
        h = Harness(return_type='py:bool')
        for param in ('a', 'b'):
            h.parameter(param, 'py:bool')
        for name, operation in (
            ('entry', 'python.entry'), ('guard_a', 'python.require'),
            ('guard_b', 'python.require'), ('guard_c', 'python.require'),
            ('branch', 'python.branch'), ('yes', 'python.return_flow'),
            ('no', 'python.return_flow'),
        ):
            h.node(name, operation)
        for source, target, input_name in (
            ('a', 'guard_a', 'condition'), ('b', 'guard_b', 'condition'),
            ('b', 'guard_c', 'condition'), ('a', 'branch', 'condition'),
            ('a', 'yes', 'value'), ('b', 'no', 'value'),
        ):
            h.wire(source, target, input_name)
        for source, target, pin in (
            ('entry', 'guard_a', 'then'), ('guard_a', 'guard_b', 'then'),
            ('guard_b', 'guard_c', 'then'), ('guard_c', 'branch', 'then'),
            ('branch', 'yes', 'true'), ('branch', 'no', 'false'),
        ):
            h.wire(source, target, 'exec', pin, 'control')
        self.h = h
        self.base = h.source()
        self.assertEqual(self.base.count('if not _smi_value_1:'), 2)
        self.assertEqual(self.base.count('if _smi_value_0:'), 1)
        # Edit the final existing Require, not the first one that produces b.
        lines = self.base.splitlines(keepends=True)
        guards = [index for index, line in enumerate(lines) if 'if not _smi_value_1:' in line]
        lines[guards[-1]] = lines[guards[-1]].replace('value_1:', 'value_0:')
        self.require_edit = ''.join(lines)
        self.branch_edit = self.base.replace('if _smi_value_0:', 'if _smi_value_1:')
        self.both = self.require_edit.replace('if _smi_value_0:', 'if _smi_value_1:')
        self.assertNotEqual(self.base, self.both)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'independent.py'

    def session(self, contents):
        self.path.write_text(contents, encoding='utf-8')
        return SourceDocumentSession.open(self.path)

    def test_branch_existing_boolean_input_rewires_without_modifying_nodes(self):
        original = self.h.graph.state
        review = review_generated_source_edit(self.h.graph, self.base, self.branch_edit,
                                               expected_revision=self.h.graph.revision)
        self.assertEqual([(c.node_id, c.action, c.input_port) for c in review.changes],
                         [('branch', 'replace_input', 'condition')])
        self.assertEqual(self.h.graph.state, original)
        self.assertTrue(import_generated_source_edit(self.h.graph, self.base, self.branch_edit,
                                                     expected_revision=review.graph_revision))
        self.assertEqual(self.h.source(), self.branch_edit)
        self.assertEqual(self.h.graph.state['nodes'], original['nodes'])
        self.assertTrue(self.h.graph.undo(self.h.graph.revision))
        self.assertEqual(self.h.graph.state['edges'], original['edges'])
        self.assertTrue(self.h.graph.redo(self.h.graph.revision))
        self.assertEqual(self.h.source(), self.branch_edit)

    def test_require_guard_rewires_without_changing_raise_effect(self):
        review = review_generated_source_edit(self.h.graph, self.base, self.require_edit,
                                               expected_revision=self.h.graph.revision)
        self.assertEqual([(c.node_id, c.input_port) for c in review.changes],
                         [('guard_c', 'condition')])
        self.assertTrue(import_generated_source_edit(self.h.graph, self.base, self.require_edit,
                                                     expected_revision=review.graph_revision))
        self.assertEqual(self.h.source(), self.require_edit)
        self.assertIn("raise ValueError('Superior MI graph Require failed')", self.h.source())

    def test_combined_controls_import_as_one_undoable_transaction(self):
        before = self.h.graph.state
        undo_depth = len(self.h.graph._undo)
        review = review_generated_source_edit(self.h.graph, self.base, self.both,
                                              expected_revision=self.h.graph.revision)
        self.assertEqual([(c.node_id, c.input_port) for c in review.changes],
                         [('guard_c', 'condition'), ('branch', 'condition')])
        self.assertTrue(import_generated_source_edit(self.h.graph, self.base, self.both,
                                                     expected_revision=review.graph_revision))
        self.assertEqual(len(self.h.graph._undo), undo_depth + 1)
        self.assertEqual(self.h.source(), self.both)
        self.assertTrue(self.h.graph.undo(self.h.graph.revision))
        self.assertEqual(self.h.graph.state['edges'], before['edges'])

    def test_independently_authored_function_remains_source_owned(self):
        authored = 'import math\n\n# user module\n' + self.both + '\n# unrelated footer\n'
        session = self.session(authored)
        before = self.h.graph.state
        review = review_independent_source_functions(self.h.graph, session, ('choose',),
                                                     expected_graph_revision=self.h.graph.revision)
        self.assertEqual({c.node_id for c in review.changes}, {'guard_c', 'branch'})
        # Inspector receipts use actual independent-source text columns and
        # do not select the Require's entire raising body.
        self.assertEqual({node_id for _, node_id, *_ in review.change_spans},
                         {'guard_c', 'branch'})
        for function, node_id, start_line, start_col, end_line, end_col in review.change_spans:
            self.assertEqual(function, 'choose')
            self.assertEqual(start_line, end_line)
            line = authored.splitlines()[start_line-1]
            self.assertIn(line[start_col-1:end_col-1], ('_smi_value_0', '_smi_value_1'))
            self.assertEqual((start_line, node_id) in
                             {(line_no, ident) for _, ident, line_no in review.change_lines}, True)
        self.assertEqual(self.h.graph.state, before)
        self.assertEqual(session.text, authored)
        self.assertTrue(import_independent_source_functions(
            self.h.graph, session, review.functions,
            expected_graph_revision=review.graph_revision,
            expected_source_revision=review.source_revision,
            expected_source_sha256=review.source_sha256))
        self.assertEqual(session.text, authored)
        self.assertEqual(self.path.read_text(), authored)
        self.assertEqual(self.h.source(), self.both)

    def test_unknown_value_or_changed_effect_is_refused_without_side_effects(self):
        before = self.h.graph.state
        for mutated in (
            self.branch_edit.replace('if _smi_value_1:', 'if missing:'),
            self.require_edit.replace('raise ValueError', 'raise RuntimeError'),
            self.branch_edit.replace('if _smi_value_1:', 'if not _smi_value_1:'),
            self.base.replace('if not _smi_value_1:', 'if _smi_value_1:', 1),
        ):
            with self.subTest(mutated=mutated):
                with self.assertRaises(ProgramGraphError):
                    review_generated_source_edit(self.h.graph, self.base, mutated,
                                                 expected_revision=self.h.graph.revision)
                self.assertEqual(self.h.graph.state, before)

    def test_stale_graph_revision_and_source_receipt_refused(self):
        session = self.session(self.both)
        review = review_independent_source_functions(self.h.graph, session, ('choose',),
                                                     expected_graph_revision=self.h.graph.revision)
        session.update(session.text + '\n# after preflight\n')
        with self.assertRaises(GraphConflict):
            import_independent_source_functions(self.h.graph, session, review.functions,
                expected_graph_revision=review.graph_revision,
                expected_source_revision=review.source_revision,
                expected_source_sha256=review.source_sha256)
        with self.assertRaises(GraphConflict):
            review_generated_source_edit(self.h.graph, self.base, self.both,
                                         expected_revision=self.h.graph.revision - 1)


if __name__ == '__main__':
    unittest.main()
