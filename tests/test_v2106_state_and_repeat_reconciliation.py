"""Round-trip evidence for execution-owned state and bounded Repeat inputs.

All edits reuse existing graph wires and compiler proof; no state or source
owner is synthesized by the test fixtures.
"""
import tempfile
from pathlib import Path
import unittest

from studio_native.program_graph import GraphConflict, ProgramGraphError
from studio_native.python_lowering import (
    preview_python, review_generated_source_edit, import_generated_source_edit,
    review_independent_source_functions, import_independent_source_functions,
)
from studio_native.source_editor import SourceDocumentSession
from tests import test_v272_ordered_binding, test_v273_mutable_local_state, test_v274_bounded_repeat


def fixture(kind):
    if kind == 'bind':
        h = test_v272_ordered_binding.OrderedBindingTests('runTest')
        h.setUp()
        h.standard()
        h.node('less', 'python.less_than')
        h.node('require', 'python.require')
        g = h.graph
        next_control = 'bind'
    elif kind == 'state':
        h = test_v273_mutable_local_state.MutableLocalTests('runTest')
        h.setUp()
        h.setup_sequence()
        h.node('less', 'python.less_than')
        h.node('require', 'python.require')
        g = h.g
        next_control = 'local'
    else:
        h = test_v274_bounded_repeat.RepeatQualificationTests('runTest')
        h.setUp()
        h.standard_graph()
        h.node('positive', 'python.less_than')
        h.node('require', 'python.require')
        g = h.graph
        next_control = 'slot'
    if kind == 'repeat':
        h.wire('initial', 'value', 'positive', 'left')
        h.wire('count', 'value', 'positive', 'right')
        h.wire('positive', 'result', 'require', 'condition')
    else:
        h.wire('two', 'value', 'less', 'left')
        h.wire('three', 'value', 'less', 'right')
        h.wire('less', 'result', 'require', 'condition')
    edge = next(e for e in g.state['edges'] if e['source'] == 'entry' and e['relation'] == 'control')
    h.edit('reconnect', edge=edge['id'], target='require', target_port='require-inputs-exec')
    h.wire('require', 'then', next_control, 'exec', 'control')
    source = preview_python(g.state)
    assert source.source is not None, source.issues
    if kind == 'bind':
        before, after, node = '_smi_value_3 = _smi_value_1', '_smi_value_3 = _smi_value_0', 'bind'
    elif kind == 'state':
        before, after, node = '_smi_slot_3 = _smi_value_1', '_smi_slot_3 = _smi_value_0', 'local'
    else:
        before, after, node = '_smi_repeat_count_0 = _smi_value_0', '_smi_repeat_count_0 = _smi_value_1', 'repeat'
    assert source.source.count(before) == 1
    return g, source.source, source.source.replace(before, after), node


class StateAndRepeatReconciliation(unittest.TestCase):
    def session(self, text):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / 'authored.py'
        path.write_text(text, encoding='utf-8')
        return SourceDocumentSession.open(path)

    def test_generated_write_and_repeat_count_rewire(self):
        for kind in ('bind', 'state', 'repeat'):
            with self.subTest(kind=kind):
                graph, original, edited, node = fixture(kind)
                before = graph.state
                review = review_generated_source_edit(graph, original, edited,
                                                     expected_revision=graph.revision)
                self.assertEqual([(c.node_id, c.action, c.input_port) for c in review.changes],
                                 [(node, 'replace_input', 'count' if kind == 'repeat' else 'value')])
                self.assertEqual(before, graph.state)
                undo_depth = len(graph._undo)
                self.assertTrue(import_generated_source_edit(graph, original, edited,
                                                            expected_revision=review.graph_revision))
                self.assertEqual(len(graph._undo), undo_depth + 1)
                self.assertEqual(preview_python(graph.state).source, edited)
                self.assertTrue(graph.undo(graph.revision))
                self.assertEqual(graph.state['nodes'], before['nodes'])
                self.assertEqual(graph.state['edges'], before['edges'])
                self.assertTrue(graph.redo(graph.revision))
                self.assertEqual(preview_python(graph.state).source, edited)

    def test_local_assignment_rewire_and_atomic_two_write_import(self):
        graph, original, edited, _ = fixture('state')
        # Local initialization and later assignment both use the already
        # evaluated pair of producers. No local identity or control edge moves.
        combined = edited.replace('_smi_slot_3 = _smi_value_0\n    _smi_value_5',
                                  '_smi_slot_3 = _smi_value_1\n    _smi_value_5')
        self.assertNotEqual(edited, combined)
        review = review_generated_source_edit(graph, original, combined,
                                             expected_revision=graph.revision)
        self.assertEqual({c.node_id for c in review.changes}, {'local', 'assign'})
        before = graph.state
        self.assertTrue(import_generated_source_edit(graph, original, combined,
                                                     expected_revision=graph.revision))
        self.assertEqual(preview_python(graph.state).source, combined)
        self.assertTrue(graph.undo(graph.revision))
        self.assertEqual(graph.state['nodes'], before['nodes'])
        self.assertEqual(graph.state['edges'], before['edges'])

    def test_independent_source_keeps_bytes_and_reports_exact_value_spans(self):
        for kind in ('bind', 'state', 'repeat'):
            with self.subTest(kind=kind):
                graph, original, edited, node = fixture(kind)
                authored = 'import math\n\n# unmodeled preface\n' + edited + '\n# untouched footer\n'
                session = self.session(authored)
                function = {'bind':'capture','state':'calculate','repeat':'count_up'}[kind]
                before = graph.state
                receipt = review_independent_source_functions(graph, session, (function,),
                                                             expected_graph_revision=graph.revision)
                self.assertEqual([(c.node_id, c.input_port) for c in receipt.changes],
                                 [(node, 'count' if kind == 'repeat' else 'value')])
                self.assertEqual(len(receipt.change_spans), 1)
                func, ident, start_line, start_col, end_line, end_col = receipt.change_spans[0]
                self.assertEqual((func, ident), (function, node))
                lines = authored.splitlines()
                self.assertEqual(start_line, end_line)
                self.assertTrue(lines[start_line-1][start_col-1:end_col-1].startswith('_smi_value_'))
                self.assertEqual(graph.state, before)
                self.assertTrue(import_independent_source_functions(
                    graph, session, receipt.functions, expected_graph_revision=receipt.graph_revision,
                    expected_source_revision=receipt.source_revision,
                    expected_source_sha256=receipt.source_sha256))
                self.assertEqual(session.text, authored)
                self.assertEqual(session.path.read_text(), authored)
                self.assertEqual(preview_python(graph.state).source, edited)
                self.assertTrue(graph.undo(graph.revision))
                self.assertEqual(graph.state['nodes'], before['nodes'])
                self.assertEqual(graph.state['edges'], before['edges'])

    def test_repeat_guard_and_loop_semantics_are_immutable(self):
        graph, original, edited, _ = fixture('repeat')
        original_graph = graph.state
        for malformed in (
            edited.replace('range(_smi_repeat_count_0)', 'range(_smi_value_1)'),
            edited.replace('_smi_repeat_count_0 < 0', '_smi_repeat_count_0 < -1'),
            edited.replace('_smi_repeat_count_0 > 10000', '_smi_repeat_count_0 > 10001'),
            edited.replace('_smi_repeat_count_0 = _smi_value_1', '_smi_repeat_count_0 = 0'),
            edited.replace('_smi_repeat_count_0 = _smi_value_1', '_smi_repeat_count_0 = missing'),
            edited.replace('for _smi_repeat_index_0 in', 'for changed in'),
        ):
            with self.subTest(changed=malformed):
                with self.assertRaises(ProgramGraphError):
                    review_generated_source_edit(graph, original, malformed,
                                                 expected_revision=graph.revision)
                self.assertEqual(graph.state, original_graph)

    def test_state_destination_and_execution_order_cannot_change(self):
        graph, original, edited, _ = fixture('state')
        original_graph = graph.state
        for malformed in (
            edited.replace('_smi_slot_3 = _smi_value_0', '_smi_slot_99 = _smi_value_0', 1),
            edited.replace('_smi_slot_3 = _smi_value_0', '_smi_slot_3 = missing', 1),
            edited.replace('_smi_slot_3 = _smi_value_0', '_smi_slot_3 = True', 1),
            edited.replace('if not _smi_value_2:', 'if _smi_value_2:'),
        ):
            with self.subTest(changed=malformed):
                with self.assertRaises(ProgramGraphError):
                    review_generated_source_edit(graph, original, malformed,
                                                 expected_revision=graph.revision)
                self.assertEqual(graph.state, original_graph)

    def test_boolean_capture_rewire_preserves_typed_execution(self):
        h=test_v272_ordered_binding.OrderedBindingTests('runTest')
        h.setUp()
        h.edit('set_return_type',function='fn',type='py:bool')
        for name,operation,props in (
            ('entry','python.entry',None),('ret','python.return_flow',None),
            ('bind','python.bind_bool',None),('truth','python.literal',{'value':True}),
            ('negate','python.not',None),('choice','python.select_bool',None),
            ('require','python.require',None),
        ):
            h.node(name,operation,props)
        for src,out,dest,pin,relation in (
            ('entry','then','require','exec','control'),
            ('require','then','bind','exec','control'),
            ('bind','then','ret','exec','control'),
            ('truth','value','negate','value','data'),
            ('truth','value','choice','condition','data'),
            ('truth','value','choice','true_value','data'),
            ('negate','result','choice','false_value','data'),
            ('choice','result','require','condition','data'),
            ('truth','value','bind','value','data'),
            ('bind','value','ret','value','data'),
        ):
            h.wire(src,out,dest,pin,relation)
        original=preview_python(h.graph.state).source
        self.assertIsNotNone(original)
        edited=original.replace('_smi_value_3 = _smi_value_0',
                                '_smi_value_3 = _smi_value_1')
        self.assertNotEqual(original,edited)
        receipt=review_generated_source_edit(h.graph,original,edited,
                                             expected_revision=h.graph.revision)
        self.assertEqual([(c.node_id,c.input_port) for c in receipt.changes],
                         [('bind','value')])
        self.assertTrue(import_generated_source_edit(h.graph,original,edited,
                                                     expected_revision=receipt.graph_revision))
        self.assertEqual(preview_python(h.graph.state).source,edited)
        space={}
        exec(edited,space)
        self.assertIs(space['capture'](),False)

    def test_stale_source_and_graph_refuse_without_partial_state(self):
        graph, original, edited, _ = fixture('repeat')
        session = self.session('import math\n'+edited)
        receipt = review_independent_source_functions(graph, session, ('count_up',),
                                                     expected_graph_revision=graph.revision)
        untouched = graph.state
        session.update(session.text + '\n# source revision changed\n')
        with self.assertRaises(GraphConflict):
            import_independent_source_functions(
                graph, session, receipt.functions,
                expected_graph_revision=receipt.graph_revision,
                expected_source_revision=receipt.source_revision,
                expected_source_sha256=receipt.source_sha256)
        self.assertEqual(graph.state, untouched)
        with self.assertRaises(GraphConflict):
            review_generated_source_edit(graph, original, edited,
                                         expected_revision=graph.revision-1)


if __name__ == '__main__':
    unittest.main()
