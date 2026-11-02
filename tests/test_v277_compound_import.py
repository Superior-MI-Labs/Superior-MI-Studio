"""Graph-owned compound transactions; generated source is a candidate, not truth."""
import unittest
from pathlib import Path
from studio_native.program_graph import ProgramGraph, ProgramGraphError, GraphConflict
from studio_native.python_lowering import import_generated_source_edit, preview_python

EXAMPLES=Path(__file__).resolve().parents[1]/'examples'


class CompoundReconciliationTests(unittest.TestCase):
    def graph(self):
        return ProgramGraph.open(EXAMPLES/'qualified-integer-program.smi-graph')

    def candidate(self, source):
        return source.replace('_smi_value_0 = 1','_smi_value_0 = 12').replace(
            '_smi_value_1 + _smi_value_0','_smi_value_1 * _smi_value_0')

    def test_compound_owner_one_revision_and_one_undo_for_two_edits(self):
        graph=self.graph()
        before=graph.state
        changed=graph.edit_many(graph.revision,[
            ('set_property',{'node':'one','key':'value','value':12}),
            ('replace_node_operation',{'node':'add','operation':'python.multiply'})])
        self.assertTrue(changed)
        self.assertEqual(graph.revision,before['revision']+1)
        self.assertEqual(graph.state['edges'],before['edges'])
        self.assertEqual(graph.state['layout'],before['layout'])
        self.assertTrue(graph.undo(graph.revision))
        self.assertEqual({k:v for k,v in graph.state.items() if k!='revision'},
                         {k:v for k,v in before.items() if k!='revision'})
        self.assertTrue(graph.redo(graph.revision))
        self.assertEqual(next(n for n in graph.state['nodes'] if n['id']=='add')['operation'],
                         'python.multiply')

    def test_compound_failure_never_mutates_graph_or_history(self):
        graph=self.graph()
        before=graph.state
        undo_before=len(graph._undo)
        with self.assertRaises(ProgramGraphError):
            graph.edit_many(graph.revision,[
                ('set_property',{'node':'one','key':'value','value':8}),
                ('replace_node_operation',{'node':'add','operation':'python.less_than'})])
        self.assertEqual(graph.state,before)
        self.assertEqual(len(graph._undo),undo_before)
        self.assertFalse(graph.undo(graph.revision))

    def test_bounded_commands_stale_revision_and_invalid_shape(self):
        graph=self.graph()
        before=graph.state
        with self.assertRaises(GraphConflict):
            graph.edit_many(graph.revision+1,[('set_property',{'node':'one','key':'value','value':2})])
        for command_list in ([],[('set_property',{})]*33,[['set_property',{}]],
                             [('set_property',{})],['set_property']):
            with self.subTest(commands=command_list),self.assertRaises((ProgramGraphError,KeyError)):
                graph.edit_many(graph.revision,command_list)
            self.assertEqual(graph.state,before)

    def test_full_python_roundtrip_batch_and_failed_mixed_edit(self):
        graph=self.graph()
        base=preview_python(graph.state).source
        candidate=self.candidate(base)
        self.assertTrue(import_generated_source_edit(graph,base,candidate,
                            expected_revision=graph.revision))
        self.assertEqual(preview_python(graph.state).source,candidate)
        self.assertTrue(graph.undo(graph.revision))
        self.assertEqual(preview_python(graph.state).source,base)
        # One supported and one unsupported alteration cannot commit either.
        graph2=self.graph()
        original=graph2.state
        invalid=candidate.replace('return _smi_value_2','return 42')
        with self.assertRaises(ProgramGraphError):
            import_generated_source_edit(graph2,base,invalid,
                                         expected_revision=graph2.revision)
        self.assertEqual(graph2.state,original)

    def test_canonical_file_is_never_changed_by_import(self):
        path=EXAMPLES/'qualified-integer-program.smi-graph'
        raw=path.read_bytes()
        graph=self.graph()
        base=preview_python(graph.state).source
        self.assertTrue(import_generated_source_edit(graph,base,self.candidate(base),
                                                     expected_revision=graph.revision))
        self.assertEqual(path.read_bytes(),raw)
        self.assertTrue(graph.dirty)


if __name__=='__main__':unittest.main()
