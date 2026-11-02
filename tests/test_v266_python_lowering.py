"""Qualified graph-owned Python preview: deterministic, pure, and fail-closed."""
import copy
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

from studio_native.program_graph import ProgramGraph, template_ports, validate
from studio_native.python_lowering import preview_python


class PreviewTests(unittest.TestCase):
    def graph(self):
        graph=ProgramGraph()
        self.edit(graph,'add_function',id='fn-increment',name='increment')
        self.edit(graph,'add_parameter',function='fn-increment',id='parameter-x',name='x',type='py:int')
        self.edit(graph,'set_return_type',function='fn-increment',type='py:int')
        self.node(graph,'fn-increment','parameter','python.parameter',props={'parameter_id':'parameter-x'})
        self.node(graph,'fn-increment','one','python.literal',props={'value':1})
        self.node(graph,'fn-increment','sum','python.add')
        self.node(graph,'fn-increment','return','python.return')
        self.wire(graph,'parameter','value','sum','left')
        self.wire(graph,'one','value','sum','right')
        self.wire(graph,'sum','result','return','value')
        return graph

    def edit(self, graph, action, **kwargs):
        graph.edit(graph.revision, action, **kwargs)

    def node(self, graph, function, ident, op, props=None, inputs=None, outputs=None):
        ports=template_ports(op) if op!='python.call' else {'inputs':inputs,'outputs':outputs}
        for direction, items in ports.items():
            for p in items:
                p['id']=f'{ident}-{p["name"]}'
        self.edit(graph,'add_node',id=ident,function=function,operation=op,
                  properties=props or {},**ports)

    def wire(self, graph, src, src_name, dst, dst_name):
        self.edit(graph,'connect',source=src,source_port=f'{src}-{src_name}',
                  target=dst,target_port=f'{dst}-{dst_name}')

    def test_full_function_matches_explicit_reference(self):
        graph=self.graph()
        original=graph.state
        preview=preview_python(original)
        self.assertEqual(preview.issues, ())
        self.assertIn('def increment(x):',preview.source)
        namespace={}
        exec(compile(preview.source,'<test-qualified-preview>','exec'),namespace)
        for value in (-20,0,42):
            self.assertEqual(namespace['increment'](value),value+1)
        self.assertEqual(len(preview.node_lines),4)
        self.assertEqual(graph.state,original)

    def test_two_functions_call_and_result_fanout(self):
        graph=self.graph()
        self.edit(graph,'add_function',id='fn-compose',name='compose')
        self.edit(graph,'add_parameter',function='fn-compose',id='param-y',name='y',type='py:int')
        self.edit(graph,'set_return_type',function='fn-compose',type='py:int')
        self.node(graph,'fn-compose','arg','python.parameter',props={'parameter_id':'param-y'})
        self.node(graph,'fn-compose','call','python.call',props={'callee_id':'fn-increment'},
                  inputs=[{'name':'x','type':'py:int'}],outputs=[{'name':'result','type':'py:int'}])
        self.node(graph,'fn-compose','product','python.multiply')
        self.node(graph,'fn-compose','done','python.return')
        self.wire(graph,'arg','value','call','x')
        self.wire(graph,'call','result','product','left')
        self.wire(graph,'call','result','product','right')
        self.wire(graph,'product','result','done','value')
        preview=preview_python(graph.state)
        self.assertFalse(preview.issues,preview.issues)
        self.assertEqual(preview.source.count('increment('),2) # definition + one invocation
        namespace={}
        exec(preview.source,namespace)
        self.assertEqual(namespace['compose'](4),25)
        self.assertEqual(preview.source,preview_python(graph.state).source)
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'program.smi-graph';graph.save(path)
            self.assertEqual(preview_python(ProgramGraph.open(path).state).source,preview.source)

    def test_incomplete_remains_valid_and_refuses_preview(self):
        graph=self.graph()
        self.edit(graph,'disconnect',edge=graph.state['edges'][0]['id'])
        validate(graph.state)
        self.assertIsNone(preview_python(graph.state).source)
        self.assertIn('missing input',str(preview_python(graph.state).issues))

    def test_orphan_node_refused_not_silently_dropped(self):
        graph=self.graph()
        self.node(graph,'fn-increment','orphan','python.literal',props={'value':12})
        result=preview_python(graph.state)
        self.assertIsNone(result.source)
        self.assertIn('orphan',str(result.issues))

    def test_control_edge_refused(self):
        graph=self.graph()
        state=graph.state
        for node in state['nodes']:
            if node['id']=='sum':
                node['ports']['outputs'][0]['type']='execution'
            elif node['id']=='return':
                node['ports']['inputs'][0]['type']='execution'
        for edge in state['edges']:
            if edge['source']=='sum': edge['relation']='control'
        validate(state)
        self.assertIn('control flow',str(preview_python(state).issues))

    def test_expression_cycle_rejected(self):
        graph=self.graph()
        self.edit(graph,'replace_input',source='sum',source_port='sum-result',
                  target='sum',target_port='sum-left')
        self.assertIn('cyclic data dependency',str(preview_python(graph.state).issues))

    def test_unknown_operations_and_versions_preserved_but_refused(self):
        graph=self.graph()
        self.edit(graph,'set_property',node='sum',key='surprise',value='no')
        self.assertIn('unknown arithmetic properties',str(preview_python(graph.state).issues))
        graph=self.graph()
        state=graph.state
        next(n for n in state['nodes'] if n['id']=='sum')['operation_version']=2
        self.assertIn('unsupported operation version',str(preview_python(state).issues))
        graph=self.graph()
        state=graph.state
        next(n for n in state['nodes'] if n['id']=='sum')['operation']='python.do-anything'
        self.assertIn('not qualified',str(preview_python(state).issues))

    def test_type_mismatch_and_literal_restrictions(self):
        graph=self.graph()
        self.edit(graph,'set_property',node='one',key='value',value=True)
        self.assertIn('integer',str(preview_python(graph.state).issues))
        graph=self.graph()
        state=graph.state
        next(n for n in state['nodes'] if n['id']=='sum')['ports']['inputs'][0]['type']='py:str'
        self.assertIn('integer-compatible',str(preview_python(state).issues))

    def test_renamed_or_removed_parameter_refuses_preview(self):
        graph=self.graph()
        self.edit(graph,'rename_parameter',function='fn-increment',parameter='parameter-x',name='z')
        self.assertIn('def increment(z):',preview_python(graph.state).source)
        self.edit(graph,'remove_parameter',function='fn-increment',parameter='parameter-x')
        self.assertIsNone(preview_python(graph.state).source)

    def test_unknown_or_stale_calls_refused(self):
        graph=self.graph()
        state=graph.state
        self.assertEqual(preview_python(state).issues,())
        self.edit(graph,'add_function',id='fn-other',name='other')
        self.edit(graph,'set_return_type',function='fn-other',type='py:int')
        self.node(graph,'fn-other','call','python.call',props={'callee_id':'fn-increment'},
                  inputs=[{'name':'wrong','type':'py:int'}],outputs=[{'name':'result','type':'py:int'}])
        self.node(graph,'fn-other','ret-other','python.return')
        self.node(graph,'fn-other','two','python.literal',props={'value':2})
        self.wire(graph,'two','value','call','wrong')
        self.wire(graph,'call','result','ret-other','value')
        self.assertIn('signature',str(preview_python(graph.state).issues))

    def test_unqualified_recursion_rejected(self):
        graph=self.graph()
        self.node(graph,'fn-increment','call-self','python.call',props={'callee_id':'fn-increment'},
                  inputs=[{'name':'x','type':'py:int'}],outputs=[{'name':'result','type':'py:int'}])
        self.edit(graph,'replace_input',source='call-self',source_port='call-self-result',
                  target='sum',target_port='sum-left')
        self.wire(graph,'parameter','value','call-self','x')
        self.assertIn('recursive',str(preview_python(graph.state).issues))

    def test_revision_layout_and_node_insertion_order_do_not_change_preview(self):
        graph=self.graph()
        expected=preview_python(graph.state).source
        self.edit(graph,'move_node',node='one',x=-100,y=200)
        self.assertEqual(expected,preview_python(graph.state).source)
        graph.undo(graph.revision)
        self.assertEqual(expected,preview_python(graph.state).source)
        # Reorder persisted node array, without changing identities or edges
        state=graph.state; state['nodes'].reverse();state['edges'].reverse()
        validate(state)
        self.assertEqual(expected,preview_python(state).source)

    def test_parameter_does_not_collide_with_compiler_temporaries(self):
        graph=self.graph()
        self.edit(graph,'rename_parameter',function='fn-increment',parameter='parameter-x',name='_smi_value_0')
        result=preview_python(graph.state)
        self.assertFalse(result.issues,result.issues)
        namespace={};exec(result.source,namespace)
        self.assertEqual(namespace['increment'](11),12)

    def test_bool_int_change_is_real_graph_revision_and_undoable(self):
        graph=self.graph()
        revision=graph.revision
        self.assertTrue(graph.edit(revision,'set_property',node='one',key='value',value=True))
        self.assertEqual(graph.revision,revision+1)
        self.assertIs(type(next(n for n in graph.state['nodes'] if n['id']=='one')['properties']['value']),bool)
        self.assertIsNone(preview_python(graph.state).source)
        self.assertTrue(graph.undo(graph.revision))
        self.assertEqual(preview_python(graph.state).issues,())

    def test_preview_cli_success_and_refusal_do_not_write_python(self):
        repo=Path(__file__).resolve().parents[1]
        example=repo/'examples'/'qualified-integer-program.smi-graph'
        result=subprocess.run([sys.executable,'-m','studio_native.python_lowering',str(example)],
                              cwd=repo,capture_output=True,text=True,timeout=8)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('def compose(y):',result.stdout)
        self.assertFalse((repo/'examples'/'qualified-integer-program.py').exists())
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'incomplete.smi-graph'
            doc=self.graph()
            doc.edit(doc.revision,'disconnect',edge=doc.state['edges'][0]['id'])
            doc.save(path)
            before=path.read_bytes()
            result=subprocess.run([sys.executable,'-m','studio_native.python_lowering',str(path)],
                                  cwd=repo,capture_output=True,text=True,timeout=8)
            self.assertEqual(result.returncode,2)
            self.assertIn('Preview refused',result.stderr)
            self.assertEqual(path.read_bytes(),before)

    def test_release_does_not_package_graph_sidecar_locks(self):
        from scripts.build_release import source_files
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in ('sample.smi-graph','.sample.smi-graph.smi-lock',
                         '.sample.smi-graph.smi-previous'):
                (root/name).write_bytes(b'x')
            self.assertEqual([p.name for p in source_files(root)],['sample.smi-graph'])

    def test_no_implicit_execution_of_unknown_expressions(self):
        with tempfile.TemporaryDirectory() as temp:
            sentinel=Path(temp)/'executed'
            graph=self.graph()
            self.edit(graph,'set_property',node='one',key='expression',value=f'open({str(sentinel)!r},"w").close()')
            result=preview_python(graph.state)
            self.assertIsNone(result.source)
            self.assertFalse(sentinel.exists())

if __name__=='__main__': unittest.main()
