"""Compiler-proven source operand changes use the existing graph input owner.

No second source map, no graph topology guess, no partial transaction.
"""
import tempfile
import unittest
from pathlib import Path

from studio_native.program_graph import ProgramGraph, ProgramGraphError, GraphConflict
from studio_native.python_lowering import (
    preview_python, review_generated_source_edit, import_generated_source_edit,
    review_independent_source_functions, import_independent_source_functions)
from studio_native.source_editor import SourceDocumentSession

EXAMPLE=Path(__file__).resolve().parents[1]/'examples/qualified-integer-program.smi-graph'
ORIGINAL='_smi_value_2 = _smi_value_1 * _smi_value_1'
REWIRED='_smi_value_2 = _smi_value_1 * _smi_value_0'


class SourceOperandReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.graph=ProgramGraph.open(EXAMPLE)
        self.base=preview_python(self.graph.state).source
        self.assertIn(ORIGINAL,self.base)
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.file=Path(self.tmp.name)/'hand_written.py'

    def session(self,text):
        self.file.write_text(text,encoding='utf-8')
        return SourceDocumentSession.open(self.file)

    def test_generated_one_input_rewire_is_atomic_and_undoable(self):
        original=self.graph.state
        source=self.base.replace(ORIGINAL,REWIRED)
        receipt=review_generated_source_edit(self.graph,self.base,source,
            expected_revision=self.graph.revision)
        self.assertEqual([(c.function,c.node_id,c.action,c.before,c.after) for c in receipt.changes],
            [('compose','mul','replace_input',('call-inc','call-inc-result'),('p-y','p-y-value'))])
        self.assertEqual(receipt.changes[0].input_port,'right')
        self.assertEqual(self.graph.state,original)
        before=len(self.graph._undo)
        self.assertTrue(import_generated_source_edit(self.graph,self.base,source,
            expected_revision=receipt.graph_revision))
        self.assertEqual(len(self.graph._undo),before+1)
        self.assertEqual(preview_python(self.graph.state).source,source)
        self.assertTrue(self.graph.undo(self.graph.revision))
        self.assertEqual(self.graph.state['nodes'],original['nodes'])
        self.assertEqual(self.graph.state['edges'],original['edges'])
        self.assertTrue(self.graph.redo(self.graph.revision))
        self.assertEqual(preview_python(self.graph.state).source,source)

    def test_two_operand_rewire_and_compatible_operator_switch_one_transaction(self):
        # The call remains live, and the parameter remains live. Reordering
        # inputs cannot be assumed safe unless the full graph proof passes.
        source=self.base.replace(ORIGINAL,'_smi_value_2 = _smi_value_0 + _smi_value_1')
        receipt=review_generated_source_edit(self.graph,self.base,source,
            expected_revision=self.graph.revision)
        self.assertEqual([(c.node_id,c.action) for c in receipt.changes],
            [('mul','replace_node_operation'),('mul','replace_input')])
        self.assertEqual(len({c.node_id for c in receipt.changes}),1)
        self.assertTrue(import_generated_source_edit(self.graph,self.base,source,
            expected_revision=receipt.graph_revision))
        self.assertEqual(preview_python(self.graph.state).source,source)

    def test_both_input_wires_can_swap_without_losing_nodes(self):
        # Start with two distinct producers feeding the same operation. Both
        # remain reachable after a swap, so the compiler can prove it.
        self.graph.edit(self.graph.revision,'replace_input',source='p-y',
                        source_port='p-y-value',target='mul',target_port='mul-right')
        original=preview_python(self.graph.state).source
        self.assertIn('_smi_value_2 = _smi_value_1 * _smi_value_0',original)
        edited=original.replace('_smi_value_1 * _smi_value_0',
                                '_smi_value_0 * _smi_value_1')
        review=review_generated_source_edit(self.graph,original,edited,
                                            expected_revision=self.graph.revision)
        self.assertEqual([(c.action,c.input_port) for c in review.changes],
                         [('replace_input','left'),('replace_input','right')])
        previous=self.graph.state
        self.assertTrue(import_generated_source_edit(self.graph,original,edited,
                                                     expected_revision=review.graph_revision))
        self.assertEqual(preview_python(self.graph.state).source,edited)
        self.assertTrue(self.graph.undo(self.graph.revision))
        self.assertEqual(self.graph.state['edges'],previous['edges'])

    def test_self_referential_wire_rejected_by_compiler(self):
        # The generated expression may mention the target output by name,
        # but a graph cycle cannot be silently compiled.
        edited=self.base.replace(ORIGINAL,'_smi_value_2 = _smi_value_1 * _smi_value_2')
        with self.assertRaises(ProgramGraphError):
            review_generated_source_edit(self.graph,self.base,edited,
                                         expected_revision=self.graph.revision)

    def test_independent_file_reordered_functions_and_extra_code(self):
        compose=self.base.split('def compose(y):',1)[1].split('\ndef increment(x):',1)[0]
        increment=self.base.split('def increment(x):',1)[1]
        authored=('import math\n\ndef custom():\n    return 1\n\n'
                  'def increment(x):'+increment+'\n\ndef compose(y):'+compose.replace(ORIGINAL,REWIRED))
        session=self.session(authored)
        original=self.graph.state
        receipt=review_independent_source_functions(self.graph,session,('compose',),
            expected_graph_revision=self.graph.revision)
        self.assertEqual([(c.node_id,c.action) for c in receipt.changes],[('mul','replace_input')])
        self.assertEqual(len(receipt.change_spans),1)
        self.assertEqual(session.text,authored)
        self.assertEqual(self.graph.state,original)
        self.assertTrue(import_independent_source_functions(self.graph,session,('compose',),
            expected_graph_revision=receipt.graph_revision,
            expected_source_revision=receipt.source_revision,
            expected_source_sha256=receipt.source_sha256))
        self.assertEqual(preview_python(self.graph.state).source,self.base.replace(ORIGINAL,REWIRED))
        self.assertEqual(session.text,authored)
        self.assertEqual(self.file.read_text(),authored)

    def test_independent_batch_literal_and_rewire_in_one_atomic_import(self):
        authored=('import math\n\n'+self.base.replace(ORIGINAL,REWIRED)
                 .replace('_smi_value_0 = 1','_smi_value_0 = 23'))
        session=self.session(authored)
        receipt=review_independent_source_functions(self.graph,session,('compose','increment'),
            expected_graph_revision=self.graph.revision)
        self.assertEqual({(c.node_id,c.action) for c in receipt.changes},
            {('mul','replace_input'),('one','set_property')})
        before=self.graph.state
        self.assertTrue(import_independent_source_functions(self.graph,session,receipt.functions,
            expected_graph_revision=receipt.graph_revision,
            expected_source_revision=receipt.source_revision,
            expected_source_sha256=receipt.source_sha256))
        self.assertEqual(len(self.graph._undo)>0,True)
        self.assertTrue(self.graph.undo(self.graph.revision))
        self.assertEqual(self.graph.state['nodes'],before['nodes'])
        self.assertEqual(self.graph.state['edges'],before['edges'])

    def test_rewire_unknown_variable_rejected_without_graph_mutation(self):
        original=self.graph.state
        for replacement in ('_smi_missing','unknown','42','_smi_value_999'):
            with self.subTest(replacement=replacement):
                edited=self.base.replace(ORIGINAL,f'_smi_value_2 = _smi_value_1 * {replacement}')
                with self.assertRaises(ProgramGraphError):
                    review_generated_source_edit(self.graph,self.base,edited,
                        expected_revision=self.graph.revision)
                self.assertEqual(self.graph.state,original)

    def test_orphan_producer_refused_even_with_valid_data_pin(self):
        original=self.graph.state
        # Replacing both uses of call-inc or making a Return bypass an existing
        # result would silently erase work. The compiler must refuse it.
        candidate=self.base.replace(ORIGINAL,'_smi_value_2 = _smi_value_0 * _smi_value_0')
        with self.assertRaises(ProgramGraphError):
            review_generated_source_edit(self.graph,self.base,candidate,
                expected_revision=self.graph.revision)
        self.assertEqual(self.graph.state,original)

    def test_stale_graph_revision_or_source_digest_cannot_use_preview(self):
        edited=self.base.replace(ORIGINAL,REWIRED)
        session=self.session('import math\n\n'+edited)
        receipt=review_independent_source_functions(self.graph,session,('compose',),
            expected_graph_revision=self.graph.revision)
        session.update(session.text+'\n# changed unrelated text\n')
        with self.assertRaises(GraphConflict):
            import_independent_source_functions(self.graph,session,receipt.functions,
                expected_graph_revision=receipt.graph_revision,
                expected_source_revision=receipt.source_revision,
                expected_source_sha256=receipt.source_sha256)
        session.update('import math\n\n'+edited)
        receipt=review_independent_source_functions(self.graph,session,('compose',),
            expected_graph_revision=self.graph.revision)
        self.graph.edit(self.graph.revision,'move_node',node='mul',x=14,y=20)
        with self.assertRaises(GraphConflict):
            import_independent_source_functions(self.graph,session,receipt.functions,
                expected_graph_revision=receipt.graph_revision,
                expected_source_revision=receipt.source_revision,
                expected_source_sha256=receipt.source_sha256)

    def test_noop_rewire_does_not_create_false_review(self):
        self.assertEqual(review_generated_source_edit(self.graph,self.base,self.base,
            expected_revision=self.graph.revision).changes,())

if __name__=='__main__': unittest.main()
