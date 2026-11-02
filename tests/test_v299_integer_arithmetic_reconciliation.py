"""One integer arithmetic compiler vocabulary and bounded bidirectional edit proof."""
import tempfile
import unittest
from pathlib import Path

from studio_native.program_graph import ProgramGraph, ProgramGraphError, NODE_TEMPLATES
from studio_native.python_lowering import (
    INTEGER_ARITHMETIC_AST, INTEGER_ARITHMETIC_BY_AST,
    SOURCE_EDITABLE_OPERATIONS, preview_python, review_generated_source_edit,
    import_generated_source_edit, review_independent_source_functions,
    import_independent_source_functions,
)
from studio_native.source_editor import SourceDocumentSession

EXAMPLE = Path(__file__).resolve().parents[1] / 'examples' / 'qualified-integer-program.smi-graph'
ARITHMETIC = {'python.add': '+', 'python.subtract': '-', 'python.multiply': '*',
              'python.floor_divide': '//', 'python.modulo': '%'}


class QualifiedIntegerArithmeticTests(unittest.TestCase):
    def graph(self):
        return ProgramGraph.open(EXAMPLE)

    def source(self, text):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / 'independent.py'
        path.write_text(text, encoding='utf-8')
        return SourceDocumentSession.open(path)

    def test_one_operator_vocabulary_for_generation_and_reverse_import(self):
        self.assertEqual(set(INTEGER_ARITHMETIC_AST), set(ARITHMETIC))
        self.assertEqual({INTEGER_ARITHMETIC_BY_AST[value]: key
                          for key, value in INTEGER_ARITHMETIC_AST.items()},
                         {key: key for key in ARITHMETIC})
        self.assertTrue(set(ARITHMETIC) <= set(SOURCE_EDITABLE_OPERATIONS))
        for name in ARITHMETIC:
            with self.subTest(operation=name):
                self.assertEqual(NODE_TEMPLATES[name], NODE_TEMPLATES['python.add'])

    def test_python_integer_division_and_modulo_preserve_negative_semantics(self):
        for op in ('python.floor_divide', 'python.modulo'):
            with self.subTest(operation=op):
                graph = self.graph()
                self.assertTrue(graph.edit(graph.revision, 'replace_node_operation',
                                           node='add', operation=op))
                result = preview_python(graph.state)
                self.assertFalse(result.issues)
                scope = {}
                exec(compile(result.source, '<generated-by-test>', 'exec'), scope)
                # increment(x) uses x op 1, so prove signed semantics by
                # editing the literal divisor to -3 (not by checking strings).
                self.assertTrue(graph.edit(graph.revision, 'set_property',
                                           node='one', key='value', value=-3))
                source = preview_python(graph.state).source
                scope = {}
                exec(compile(source, '<generated-by-test>', 'exec'), scope)
                for x in (-7, -5, 5, 7):
                    actual = scope['increment'](x)
                    self.assertEqual(actual, x // -3 if op == 'python.floor_divide' else x % -3)
                self.assertIn(ARITHMETIC[op], source)

    def test_new_operations_qualified_as_graph_source_roundtrip(self):
        for name in ('python.floor_divide', 'python.modulo'):
            with self.subTest(operation=name):
                graph = self.graph()
                base = preview_python(graph.state).source
                candidate = base.replace(' * ', f' {ARITHMETIC[name]} ', 1)
                self.assertNotEqual(candidate, base)
                original = graph.state
                receipt = review_generated_source_edit(graph, base, candidate,
                    expected_revision=graph.revision)
                self.assertEqual([(c.node_id, c.after) for c in receipt.changes],
                                 [('mul', name)])
                self.assertTrue(import_generated_source_edit(graph, base, candidate,
                    expected_revision=receipt.graph_revision))
                self.assertEqual(preview_python(graph.state).source, candidate)
                self.assertEqual(original['edges'], graph.state['edges'])
                self.assertEqual(original['layout'], graph.state['layout'])
                self.assertTrue(graph.undo(graph.revision))
                self.assertEqual(preview_python(graph.state).source, base)
                self.assertTrue(graph.redo(graph.revision))
                self.assertEqual(preview_python(graph.state).source, candidate)

    def test_independently_authored_multi_function_import_is_one_transaction(self):
        graph = self.graph()
        baseline = preview_python(graph.state).source
        compose = baseline.split('def compose(y):', 1)[1].split('\ndef increment(x):', 1)[0]
        increment = baseline.split('def increment(x):', 1)[1]
        authored = ('import math\n\n# outside model\ndef helper():\n    return math.pi\n\n'
                    + 'def increment(x):' + increment.replace('_smi_value_0 = 1', '_smi_value_0 = -3')
                    + '\n\ndef compose(y):' + compose.replace(' * ', ' // '))
        session = self.source(authored)
        before = graph.state
        receipt = review_independent_source_functions(graph, session, ('increment', 'compose'),
            expected_graph_revision=graph.revision)
        self.assertEqual([(c.node_id, c.action) for c in receipt.changes],
                         [('one', 'set_property'), ('mul', 'replace_node_operation')])
        self.assertEqual({(f, n): authored.splitlines()[line-1].strip()
                          for f, n, line in receipt.change_lines},
                         {('increment','one'):'_smi_value_0 = -3',
                          ('compose','mul'):'_smi_value_2 = _smi_value_1 // _smi_value_1'})
        self.assertEqual(graph.state, before)
        undo_before = len(graph._undo)
        self.assertTrue(import_independent_source_functions(graph, session, receipt.functions,
            expected_graph_revision=receipt.graph_revision,
            expected_source_revision=receipt.source_revision,
            expected_source_sha256=receipt.source_sha256))
        self.assertEqual(len(graph._undo), undo_before+1)
        self.assertEqual(session.text, authored)
        self.assertIn('def helper()', session.text)
        self.assertTrue(graph.undo(graph.revision))
        self.assertEqual(graph.state['nodes'], before['nodes'])

    def test_rejects_unmodeled_operators_and_unsafe_literal_types(self):
        graph = self.graph()
        baseline = preview_python(graph.state).source
        before = graph.state
        candidates = (baseline.replace(' * ', ' / ', 1),
                      baseline.replace(' * ', ' ** ', 1),
                      baseline.replace(' * ', ' @ ', 1),
                      baseline.replace('_smi_value_0 = 1', '_smi_value_0 = 1.2', 1))
        for candidate in candidates:
            with self.subTest(candidate=candidate), self.assertRaises(ProgramGraphError):
                review_generated_source_edit(graph, baseline, candidate,
                    expected_revision=graph.revision)
            self.assertEqual(graph.state, before)

    def test_refuses_partial_batch_on_unsupported_expression(self):
        graph = self.graph()
        base = preview_python(graph.state).source
        changed = base.replace('_smi_value_0 = 1', '_smi_value_0 = 27').replace(' * ', ' ** ', 1)
        session = self.source('import sys\n\n' + changed)
        with self.assertRaisesRegex(ProgramGraphError, "Function 'compose'"):
            review_independent_source_functions(graph, session, ('increment', 'compose'),
                expected_graph_revision=graph.revision)
        self.assertFalse(graph.dirty)

    def test_negative_integer_literal_roundtrip_and_nonliteral_refusal(self):
        graph = self.graph()
        base = preview_python(graph.state).source
        changed = base.replace('_smi_value_0 = 1', '_smi_value_0 = -17', 1)
        receipt = review_generated_source_edit(graph, base, changed,
            expected_revision=graph.revision)
        self.assertEqual([(c.node_id, c.before, c.after) for c in receipt.changes],
                         [('one', 1, -17)])
        self.assertTrue(import_generated_source_edit(graph, base, changed,
            expected_revision=receipt.graph_revision))
        self.assertEqual(preview_python(graph.state).source, changed)
        self.assertTrue(graph.undo(graph.revision))
        self.assertEqual(preview_python(graph.state).source, base)
        for invalid in ('-True', '-x', '-(-1)', '+2', 'float(3)'):
            with self.subTest(invalid=invalid), self.assertRaises(ProgramGraphError):
                review_generated_source_edit(graph, base,
                    base.replace('_smi_value_0 = 1', f'_smi_value_0 = {invalid}', 1),
                    expected_revision=graph.revision)

    def test_selected_function_missing_identity_reports_only_exact_names(self):
        graph = self.graph()
        base = preview_python(graph.state).source
        session = self.source('import math\n\n'+base.replace(
            'def increment(x):', 'def renamed(x):'))
        with self.assertRaisesRegex(ProgramGraphError,
                "Function 'increment' must occur exactly once.*'renamed'"):
            review_independent_source_functions(graph, session, ('increment',),
                expected_graph_revision=graph.revision)
        self.assertFalse(graph.dirty)

    def test_duplicate_function_identity_reports_both_source_lines(self):
        graph = self.graph()
        base = preview_python(graph.state).source
        session = self.source(base+'\ndef increment(x):\n    return x\n')
        with self.assertRaisesRegex(ProgramGraphError,
                "duplicate source definitions at lines 7, 13"):
            review_independent_source_functions(graph, session, ('increment',),
                expected_graph_revision=graph.revision)
        self.assertFalse(graph.dirty)

    def test_zero_division_matches_python_not_implicit_protection(self):
        for name in ('python.floor_divide', 'python.modulo'):
            with self.subTest(name=name):
                graph = self.graph()
                graph.edit(graph.revision, 'replace_node_operation', node='add', operation=name)
                graph.edit(graph.revision, 'set_property', node='one', key='value', value=0)
                preview = preview_python(graph.state)
                scope = {}
                exec(compile(preview.source, '<generated-by-test>', 'exec'), scope)
                with self.assertRaises(ZeroDivisionError):
                    scope['increment'](8)

if __name__ == '__main__':
    unittest.main()
