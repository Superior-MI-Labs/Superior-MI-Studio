"""Independent-source order/identity reconciliation; production compiler proof only."""
import tempfile
import unittest
from pathlib import Path

from studio_native.program_graph import ProgramGraphError, GraphConflict
from studio_native.python_lowering import (
    preview_python, review_generated_source_edit,
    review_independent_source_functions, import_independent_source_functions,
    _equivalent_pure_assignment_order,
)
from studio_native.source_editor import SourceDocumentSession
from tests.test_v2102_semantic_input_reconciliation import Harness
import ast


class PureDependencyOrderTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness(name='compose', return_type='py:int')
        for p in ('x', 'y'):
            self.h.parameter(p)
        for node in ('a', 'b', 'sum'):
            self.h.node(node, 'python.add')
        self.h.node('ret', 'python.return')
        for source, target, input_name in (
            ('x', 'a', 'left'), ('y', 'a', 'right'),
            ('x', 'b', 'left'), ('y', 'b', 'right'),
            ('a', 'sum', 'left'), ('b', 'sum', 'right'),
            ('sum', 'ret', 'value'),
        ):
            self.h.wire(source, target, input_name)
        self.base = self.h.source()
        self.edited = self.base.replace(
            '    _smi_value_2 = _smi_value_0 + _smi_value_1\n'
            '    _smi_value_3 = _smi_value_0 + _smi_value_1',
            '    _smi_value_3 = _smi_value_0 + _smi_value_1\n'
            '    _smi_value_2 = _smi_value_3 + _smi_value_1',
        )
        self.assertNotEqual(self.base, self.edited)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'author.py'

    def session(self, contents):
        self.path.write_text(contents, encoding='utf-8')
        return SourceDocumentSession.open(self.path)

    def test_reordered_dependencies_preserve_nodes_source_and_undo(self):
        # The source retains baseline variable identities. Re-lowering assigns
        # compiler temporary numbers in dependency order; node IDs align them.
        source = 'import math\n\n# independent file\n' + self.edited + '\n# footer\n'
        session = self.session(source)
        before = self.h.graph.state
        review = review_independent_source_functions(self.h.graph, session, ('compose',),
                                                      expected_graph_revision=self.h.graph.revision)
        self.assertEqual([(c.node_id, c.action, c.input_port) for c in review.changes],
                         [('a', 'replace_input', 'left')])
        self.assertEqual(self.h.graph.state, before)
        self.assertTrue(import_independent_source_functions(self.h.graph, session, ('compose',),
            expected_graph_revision=review.graph_revision,
            expected_source_revision=review.source_revision,
            expected_source_sha256=review.source_sha256))
        generated = preview_python(self.h.graph.state)
        self.assertIsNotNone(generated.source, generated.issues)
        self.assertIn('_smi_value_3 = _smi_value_2 + _smi_value_1', generated.source)
        self.assertEqual(session.text, source)
        self.assertEqual(self.path.read_text(encoding='utf-8'), source)
        self.assertTrue(self.h.graph.undo(self.h.graph.revision))
        self.assertEqual(self.h.graph.state['edges'], before['edges'])
        self.assertTrue(self.h.graph.redo(self.h.graph.revision))

    def test_generated_source_strictly_refuses_reordered_edit(self):
        with self.assertRaises(ProgramGraphError):
            review_generated_source_edit(self.h.graph, self.base, self.edited,
                                         expected_revision=self.h.graph.revision)

    def test_review_becomes_stale_after_graph_change(self):
        session = self.session(self.edited)
        review = review_independent_source_functions(self.h.graph, session, ('compose',),
                                                      expected_graph_revision=self.h.graph.revision)
        self.h.graph.edit(self.h.graph.revision, 'move_node', node='a', x=12, y=36)
        with self.assertRaises(GraphConflict):
            import_independent_source_functions(self.h.graph, session, ('compose',),
                expected_graph_revision=review.graph_revision,
                expected_source_revision=review.source_revision,
                expected_source_sha256=review.source_sha256)

    def test_missing_producer_forward_reference_refused(self):
        # Reordering must not qualify a source that would read a temporary
        # before its assignment at runtime.
        invalid = self.base.replace(
            '    _smi_value_2 = _smi_value_0 + _smi_value_1',
            '    _smi_value_2 = _smi_value_3 + _smi_value_1',
        )
        original = self.h.graph.state
        with self.assertRaises(ProgramGraphError):
            review_independent_source_functions(self.h.graph, self.session(invalid),
                ('compose',), expected_graph_revision=self.h.graph.revision)
        self.assertEqual(self.h.graph.state, original)

    def test_pure_order_proof_does_not_permute_effects_or_division(self):
        first = ast.parse('def f(x, y):\n    _smi_value_0 = x // y\n'
                          '    _smi_value_1 = x + y\n    return _smi_value_1\n')
        second = ast.parse('def f(x, y):\n    _smi_value_1 = x + y\n'
                           '    _smi_value_0 = x // y\n    return _smi_value_1\n')
        self.assertFalse(_equivalent_pure_assignment_order(first, second))
        first = ast.parse('def f(x, y):\n    _smi_value_0 = f(x)\n'
                          '    _smi_value_1 = x + y\n    return _smi_value_1\n')
        second = ast.parse('def f(x, y):\n    _smi_value_1 = x + y\n'
                           '    _smi_value_0 = f(x)\n    return _smi_value_1\n')
        self.assertFalse(_equivalent_pure_assignment_order(first, second))

    def test_pure_order_proof_rejects_forward_reference(self):
        initial = ast.parse('def f(x):\n    _smi_value_0 = x\n'
                            '    _smi_value_1 = _smi_value_0 + x\n    return _smi_value_1\n')
        moved = ast.parse('def f(x):\n    _smi_value_1 = _smi_value_0 + x\n'
                          '    _smi_value_0 = x\n    return _smi_value_1\n')
        self.assertFalse(_equivalent_pure_assignment_order(initial, moved))

    def test_pure_order_proof_rejects_repeated_target_names(self):
        original = ast.parse('def f(x):\n    _smi_value_0 = x\n'
                             '    _smi_value_0 = x + 1\n    return _smi_value_0\n')
        moved = ast.parse('def f(x):\n    _smi_value_0 = x + 1\n'
                          '    _smi_value_0 = x\n    return _smi_value_0\n')
        self.assertFalse(_equivalent_pure_assignment_order(original, moved))


if __name__ == '__main__':
    unittest.main()
