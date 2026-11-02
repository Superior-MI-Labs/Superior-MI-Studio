"""Existing effectful call arguments are rewired by the authoritative graph compiler."""
import tempfile
import unittest
from pathlib import Path

from studio_native.program_graph import GraphConflict, ProgramGraphError
from studio_native.python_lowering import (
    preview_python, review_generated_source_edit, import_generated_source_edit,
    review_independent_source_functions, import_independent_source_functions,
)
from studio_native.source_editor import SourceDocumentSession
from tests.test_v275_ordered_calls import OrderedCallTests


class ExecutionCallArgumentReconciliationTests(unittest.TestCase):
    def setUp(self):
        h = OrderedCallTests(methodName='test_explicit_effectful_call_preserves_execution_and_result_mapping')
        h.setUp()
        h.qualified_graph()
        # Both candidate producer values must remain graph-live *before* the
        # effectful call. Otherwise changing its argument can move a producer
        # across an effect boundary, which the compiler must refuse.
        h.node('caller', 'zero2', 'python.literal', {'value': 0})
        h.node('caller', 'positive2', 'python.less_than')
        h.node('caller', 'require2', 'python.require')
        for source, output, target, port in (
            ('zero2','value','positive2','left'),
            ('param2','value','positive2','right'),
            ('positive2','result','require2','condition'),
        ):
            h.wire(source, output, target, port)
        first = next(e for e in h.graph.state['edges'] if e['source']=='entry2')
        h.edit('reconnect', edge=first['id'], target='require2', target_port='require2-inputs-exec')
        h.wire('require2', 'then', 'ordered', 'exec', 'control')
        self.h = h
        self.base = preview_python(h.graph.state).source
        self.assertIsNotNone(self.base)
        self.assertIn('guarded(_smi_value_0)', self.base)
        self.edited = self.base.replace('guarded(_smi_value_0)', 'guarded(_smi_value_1)')
        self.assertNotEqual(self.base, self.edited)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'author.py'

    def session(self, text):
        self.path.write_text(text, encoding='utf-8')
        return SourceDocumentSession.open(self.path)

    def test_generated_execution_argument_edit_is_one_undoable_wire_change(self):
        before = self.h.graph.state
        review = review_generated_source_edit(self.h.graph, self.base, self.edited,
                                               expected_revision=self.h.graph.revision)
        self.assertEqual([(c.function,c.node_id,c.action,c.input_port) for c in review.changes],
                         [('invoke','ordered','replace_input','x')])
        self.assertEqual(self.h.graph.state, before)
        depth = len(self.h.graph._undo)
        self.assertTrue(import_generated_source_edit(self.h.graph,self.base,self.edited,
                                                     expected_revision=review.graph_revision))
        self.assertEqual(len(self.h.graph._undo), depth+1)
        self.assertEqual(preview_python(self.h.graph.state).source,self.edited)
        self.assertTrue(self.h.graph.undo(self.h.graph.revision))
        self.assertEqual(self.h.graph.state['nodes'],before['nodes'])
        self.assertEqual(self.h.graph.state['edges'],before['edges'])

    def test_independent_source_keeps_other_functions_and_text_unchanged(self):
        authored = 'import math\n\n# user module\n'+self.edited+'\n# unrelated\n'
        session = self.session(authored)
        before = self.h.graph.state
        receipt = review_independent_source_functions(self.h.graph,session,('invoke',),
                                                     expected_graph_revision=self.h.graph.revision)
        self.assertEqual([(c.node_id,c.input_port) for c in receipt.changes],[('ordered','x')])
        self.assertEqual(len(receipt.change_spans),1)
        _,node_id,line,start,end_line,end=receipt.change_spans[0]
        self.assertEqual(node_id,'ordered')
        self.assertEqual(line,end_line)
        self.assertEqual(authored.splitlines()[line-1][start-1:end-1], '_smi_value_1')
        self.assertEqual(self.h.graph.state,before)
        self.assertTrue(import_independent_source_functions(self.h.graph,session,receipt.functions,
            expected_graph_revision=receipt.graph_revision,
            expected_source_revision=receipt.source_revision,
            expected_source_sha256=receipt.source_sha256))
        self.assertEqual(self.path.read_text(),authored)
        self.assertEqual(session.text,authored)
        self.assertEqual(preview_python(self.h.graph.state).source,self.edited)

    def test_effectful_call_removal_and_unknown_argument_refused(self):
        before = self.h.graph.state
        for altered in (
            self.base.replace('guarded(_smi_value_0)','guarded(12)'),
            self.base.replace('guarded(_smi_value_0)','missing(_smi_value_0)'),
            self.base.replace('guarded(_smi_value_0)','guarded(_smi_value_999)'),
            self.base.replace('guarded(_smi_value_0)','guarded()'),
            self.base.replace('guarded(_smi_value_0)','guarded(_smi_value_0, _smi_value_1)'),
        ):
            with self.subTest(altered=altered):
                with self.assertRaises(ProgramGraphError):
                    review_generated_source_edit(self.h.graph,self.base,altered,
                        expected_revision=self.h.graph.revision)
                self.assertEqual(self.h.graph.state,before)

    def test_stale_source_or_graph_rejected_after_preflight(self):
        session=self.session(self.edited)
        review=review_independent_source_functions(self.h.graph,session,('invoke',),
            expected_graph_revision=self.h.graph.revision)
        session.update(session.text+'\n# changed after review\n')
        with self.assertRaises(GraphConflict):
            import_independent_source_functions(self.h.graph,session,review.functions,
                expected_graph_revision=review.graph_revision,
                expected_source_revision=review.source_revision,
                expected_source_sha256=review.source_sha256)
        self.assertEqual(preview_python(self.h.graph.state).source,self.base)


if __name__=='__main__':
    unittest.main()
