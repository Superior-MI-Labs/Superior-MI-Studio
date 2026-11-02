"""Comparison source edits and precise failed-batch diagnostics use one compiler proof."""
import tempfile
import unittest
from pathlib import Path

from studio_native.program_graph import ProgramGraph, ProgramGraphError
from studio_native.python_lowering import (
    preview_python, review_generated_source_edit, import_generated_source_edit,
    review_independent_source_function, review_independent_source_functions,
    import_independent_source_functions, import_independent_source_function,
)
from studio_native.source_editor import SourceDocumentSession

EXAMPLES = Path(__file__).resolve().parents[1] / 'examples'


class ComparisonReconciliationTests(unittest.TestCase):
    def graph(self, name='qualified-conditional-program'):
        return ProgramGraph.open(EXAMPLES / (name + '.smi-graph'))

    def source_owner(self, text):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / 'independent.py'
        path.write_text(text, encoding='utf-8')
        return SourceDocumentSession.open(path)

    def test_comparison_switch_preserves_ports_edges_and_undo(self):
        graph = self.graph()
        baseline = preview_python(graph.state).source
        self.assertIn('_smi_value_0 < _smi_value_1', baseline)
        edited = baseline.replace('_smi_value_0 < _smi_value_1',
                                  '_smi_value_0 == _smi_value_1')
        review = review_generated_source_edit(graph, baseline, edited,
                                             expected_revision=graph.revision)
        self.assertEqual(len(review.changes), 1)
        change = review.changes[0]
        self.assertEqual((change.action, change.before, change.after),
                         ('replace_node_operation', 'python.less_than', 'python.equal_int'))
        original = graph.state
        self.assertTrue(import_generated_source_edit(graph, baseline, edited,
                    expected_revision=graph.revision))
        self.assertEqual(preview_python(graph.state).source, edited)
        self.assertEqual(original['edges'], graph.state['edges'])
        self.assertEqual(original['layout'], graph.state['layout'])
        self.assertEqual({n['id']: n['ports'] for n in original['nodes']},
                         {n['id']: n['ports'] for n in graph.state['nodes']})
        self.assertTrue(graph.undo(graph.revision))
        self.assertEqual(preview_python(graph.state).source, baseline)
        self.assertTrue(graph.redo(graph.revision))
        self.assertEqual(preview_python(graph.state).source, edited)

    def test_reverse_comparison_switch_and_in_structured_branch(self):
        for name in ('qualified-conditional-program', 'qualified-structured-branch',
                     'qualified-nested-branches'):
            with self.subTest(name=name):
                graph = self.graph(name)
                baseline = preview_python(graph.state).source
                edited = baseline.replace(' < ', ' == ')
                review = review_generated_source_edit(graph, baseline, edited,
                                                      expected_revision=graph.revision)
                expected = 2 if name == 'qualified-nested-branches' else 1
                self.assertEqual(len(review.changes), expected)
                self.assertTrue(import_generated_source_edit(graph, baseline, edited,
                                expected_revision=graph.revision))
                self.assertEqual(preview_python(graph.state).source, edited)
                reverse = edited.replace(' == ', ' < ')
                self.assertTrue(import_generated_source_edit(graph, edited, reverse,
                                expected_revision=graph.revision))
                self.assertEqual(preview_python(graph.state).source, baseline)

    def test_reject_unqualified_comparison_changes_atomically(self):
        graph = self.graph()
        baseline = preview_python(graph.state).source
        variants = (
            baseline.replace(' < ', ' in '),
            baseline.replace(' < ', ' is '),
            baseline.replace('_smi_value_0 < _smi_value_1',
                             '_smi_value_0 < _smi_value_1 < 500'),
            baseline.replace(' < ', ' == ').replace('return _smi_value_5', 'return 99'),
            baseline.replace('_smi_value_0 < _smi_value_1',
                             'other == _smi_value_1'),
        )
        original = graph.state
        for source in variants:
            with self.subTest(source=source), self.assertRaises(ProgramGraphError):
                review_generated_source_edit(graph, baseline, source,
                                             expected_revision=graph.revision)
            self.assertEqual(graph.state, original)

    def test_independent_function_comparison_with_source_only_statements(self):
        graph = self.graph()
        baseline = preview_python(graph.state).source
        independent = ('import sys\n\ndef opaque(value):\n    return sys.version\n\n'
                       + baseline.replace(' < ', ' == '))
        session = self.source_owner(independent)
        receipt = review_independent_source_function(graph, session, 'choose',
                    expected_graph_revision=graph.revision)
        self.assertEqual(receipt.unmodeled_top_level, 2)
        self.assertEqual([(c.before, c.after) for c in receipt.changes],
                         [('python.less_than', 'python.equal_int')])
        self.assertTrue(import_independent_source_function(graph, session, 'choose',
            expected_graph_revision=receipt.graph_revision,
            expected_source_revision=receipt.source_revision,
            expected_source_sha256=receipt.source_sha256))
        self.assertEqual(session.text, independent)
        self.assertEqual(preview_python(graph.state).source, baseline.replace(' < ', ' == '))

    def test_multi_function_error_identifies_exact_refused_region(self):
        graph = self.graph('qualified-integer-program')
        base = preview_python(graph.state).source
        changed = (base.replace('_smi_value_0 = 1', '_smi_value_0 = 14')
                     .replace('_smi_value_1 * _smi_value_1',
                              '_smi_value_1 / _smi_value_1'))
        session = self.source_owner('import math\n\n'+changed)
        before = graph.state
        with self.assertRaisesRegex(ProgramGraphError,
                                   r"Function 'compose' \(source lines \d+-\d+\)") as caught:
            review_independent_source_functions(graph, session,
                ('increment', 'compose'), expected_graph_revision=graph.revision)
        self.assertIn('qualified mapped expressions', str(caught.exception))
        self.assertEqual(graph.state, before)
        # With the invalid region excluded, the other explicitly selected
        # function still passes the same proof. The rejected batch applies none.
        valid = review_independent_source_functions(graph, session, ('increment',),
                    expected_graph_revision=graph.revision)
        self.assertEqual([(c.node_id, c.after) for c in valid.changes], [('one', 14)])
        self.assertEqual(graph.state, before)

    def test_diagnostics_remain_bounded_on_multiple_unsupported_functions(self):
        graph = self.graph('qualified-integer-program')
        source = preview_python(graph.state).source.replace('return _smi_value_2',
                                                            'return 123', 1)
        source = source.replace('_smi_value_0 = 1', '_smi_value_0 = True')
        session = self.source_owner(source)
        with self.assertRaisesRegex(ProgramGraphError, "Function 'compose'"):
            review_independent_source_functions(graph, session,
                ('compose','increment'), expected_graph_revision=graph.revision)
        self.assertFalse(graph.dirty)


if __name__ == '__main__':
    unittest.main()
