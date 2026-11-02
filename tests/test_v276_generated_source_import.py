"""A bounded first source-to-graph acceptance proof; no lossy fallback."""
import unittest
from pathlib import Path
from studio_native.program_graph import ProgramGraph, ProgramGraphError, GraphConflict
from studio_native.python_lowering import preview_python, import_generated_source_edit

EXAMPLES = Path(__file__).resolve().parents[1] / 'examples'


class GeneratedLiteralImportTests(unittest.TestCase):
    def document(self, name='qualified-integer-program'):
        return ProgramGraph.open(EXAMPLES / (name+'.smi-graph'))

    def test_one_literal_edit_preserves_nodes_and_undo_history(self):
        graph = self.document()
        before = graph.state
        base = preview_python(before)
        self.assertEqual(base.issues, ())
        self.assertEqual(len([n for n in before['nodes'] if n['operation']=='python.literal']), 1)
        revised = base.source.replace('_smi_value_0 = 1', '_smi_value_0 = 8')
        self.assertNotEqual(revised, base.source)
        self.assertTrue(import_generated_source_edit(graph, base.source, revised, expected_revision=graph.revision))
        self.assertEqual(preview_python(graph.state).source, revised)
        self.assertEqual({n['id'] for n in before['nodes']}, {n['id'] for n in graph.state['nodes']})
        self.assertEqual(graph.state['edges'], before['edges'])
        self.assertEqual(graph.state['layout'], before['layout'])
        self.assertEqual(graph.revision, before['revision']+1)
        self.assertTrue(graph.undo(graph.revision))
        self.assertEqual(preview_python(graph.state).source,base.source)
        self.assertTrue(graph.redo(graph.revision))
        self.assertEqual(preview_python(graph.state).source,revised)

    def test_noop_is_not_a_revision(self):
        graph=self.document()
        base=preview_python(graph.state).source
        revision=graph.revision
        self.assertFalse(import_generated_source_edit(graph,base,base,expected_revision=revision))
        self.assertEqual(graph.revision,revision)

    def test_reject_stale_revision_and_stale_source_base(self):
        graph=self.document()
        base=preview_python(graph.state).source
        revised=base.replace('_smi_value_0 = 1','_smi_value_0 = 7')
        graph.edit(graph.revision,'move_node',node='one',x=120,y=80)
        with self.assertRaises(GraphConflict):
            import_generated_source_edit(graph,base,revised,expected_revision=graph.revision-1)
        graph.edit(graph.revision,'set_property',node='one',key='value',value=2)
        with self.assertRaises(GraphConflict):
            import_generated_source_edit(graph,base,revised,expected_revision=graph.revision)

    def test_unsupported_source_edits_preserve_graph(self):
        graph=self.document()
        base=preview_python(graph.state).source
        variants=[base.replace('_smi_value_0 = 1','_smi_value_0 = True'),
                  base.replace('_smi_value_0 = 1','_smi_value_0 = 9',1).replace('return _smi_value_2','return 17'),
                  base.replace('_smi_value_0 = 1','_smi_value_0=9'),
                  base.replace('_smi_value_0 = 1','_smi_value_0 = other()'),
                  base.replace('_smi_value_0 = 1','_smi_value_0 = 9\n    print("unwanted")'),
                  base.replace('_smi_value_0 = 1','_smi_value_0 = -True'),
                  base.replace('_smi_value_0 = 1','_smi_value_0 = 1 # comment'),
                  base+'# appendix\n',
                  'def broken(:\n']
        snapshot=graph.state
        for changed in variants:
            self.assertNotEqual(changed,base)
            with self.subTest(changed=changed):
                with self.assertRaises(ProgramGraphError):
                    import_generated_source_edit(graph,base,changed,expected_revision=graph.revision)
                self.assertEqual(graph.state,snapshot)

    def test_bool_literal_import_preserves_type(self):
        graph=self.document('qualified-conditional-program')
        base=preview_python(graph.state).source
        revised=base.replace('_smi_value_3 = 1','_smi_value_3 = 4')
        self.assertTrue(import_generated_source_edit(graph,base,revised,expected_revision=graph.revision))
        self.assertEqual(preview_python(graph.state).source,revised)

    def test_arithmetic_operator_switch_produces_identical_code_with_stable_ids(self):
        graph=self.document()
        base=preview_python(graph.state).source
        edited=base.replace('_smi_value_1 + _smi_value_0', '_smi_value_1 * _smi_value_0')
        self.assertNotEqual(base, edited)
        before=graph.state
        self.assertTrue(import_generated_source_edit(graph,base,edited,expected_revision=graph.revision))
        self.assertEqual(preview_python(graph.state).source,edited)
        self.assertEqual(before['edges'],graph.state['edges'])
        self.assertEqual(before['layout'],graph.state['layout'])
        changed=next(n for n in graph.state['nodes'] if n['id']=='add')
        self.assertEqual(changed['operation'],'python.multiply')
        self.assertTrue(graph.undo(graph.revision))
        self.assertEqual(preview_python(graph.state).source,base)

    def test_multi_expression_import_is_one_undoable_graph_transaction(self):
        graph=self.document()
        base=preview_python(graph.state).source
        edited=base.replace('_smi_value_0 = 1','_smi_value_0 = 3').replace(
            '_smi_value_1 + _smi_value_0','_smi_value_1 - _smi_value_0')
        before=graph.state
        self.assertTrue(import_generated_source_edit(graph,base,edited,expected_revision=graph.revision))
        self.assertEqual(graph.revision,before['revision']+1)
        self.assertEqual(preview_python(graph.state).source,edited)
        self.assertEqual(graph.state['edges'],before['edges'])
        self.assertEqual(graph.state['layout'],before['layout'])
        self.assertTrue(graph.undo(graph.revision))
        self.assertEqual(graph.state,before | {'revision': graph.revision})
        self.assertEqual(preview_python(graph.state).source,base)
        self.assertTrue(graph.redo(graph.revision))
        self.assertEqual(preview_python(graph.state).source,edited)

    def test_operation_replacement_requires_same_exact_port_contract(self):
        graph=self.document()
        before=graph.state
        with self.assertRaises(ProgramGraphError):
            graph.edit(graph.revision,'replace_node_operation',node='add',operation='python.less_than')
        self.assertEqual(graph.state,before)
        with self.assertRaises(ProgramGraphError):
            graph.edit(graph.revision,'replace_node_operation',node='one',operation='python.call')
        self.assertEqual(graph.state,before)

    def test_generated_code_not_executed_or_written(self):
        graph=self.document()
        base=preview_python(graph.state).source
        original_file=(EXAMPLES/'qualified-integer-program.smi-graph').read_bytes()
        changed=base.replace('_smi_value_0 = 1','_smi_value_0 = 10')
        self.assertTrue(import_generated_source_edit(graph,base,changed,expected_revision=graph.revision))
        self.assertEqual((EXAMPLES/'qualified-integer-program.smi-graph').read_bytes(),original_file)
        self.assertTrue(graph.dirty)

if __name__=='__main__':unittest.main()
