"""Execution-call qualification through the existing ProgramGraph and Python lowering owners."""
import tempfile
from pathlib import Path
import unittest

from studio_native.program_graph import ProgramGraph, template_ports, validate
from studio_native.python_lowering import preview_python, publish_python


class OrderedCallTests(unittest.TestCase):
    def setUp(self):
        self.graph = ProgramGraph()
        self.edit('add_function', id='callee', name='guarded')
        self.edit('set_return_type', function='callee', type='py:int')
        self.edit('add_parameter', function='callee', id='arg', name='x', type='py:int')
        self.edit('add_function', id='caller', name='invoke')
        self.edit('set_return_type', function='caller', type='py:int')
        self.edit('add_parameter', function='caller', id='caller_arg', name='y', type='py:int')

    def edit(self, action, **kwargs):
        return self.graph.edit(self.graph.revision, action, **kwargs)

    def node(self, function, ident, operation, properties=None):
        ports = template_ports(operation)
        self.raw_node(function, ident, operation, properties or {}, ports['inputs'], ports['outputs'])

    def raw_node(self, function, ident, operation, properties, inputs, outputs):
        for side, ports in [('inputs',inputs), ('outputs',outputs)]:
            for port in ports:
                port['id'] = f'{ident}-{side}-{port["name"]}'
        self.edit('add_node', id=ident, function=function, operation=operation,
                  properties=properties, inputs=inputs, outputs=outputs)

    def wire(self, src, src_port, dst, dst_port, kind='data'):
        self.edit('connect', source=src, source_port=f'{src}-outputs-{src_port}',
                  target=dst, target_port=f'{dst}-inputs-{dst_port}', relation=kind)

    def qualified_graph(self):
        for name, operation, props in (
            ('entry1', 'python.entry', {}),
            ('param1', 'python.parameter', {'parameter_id':'arg'}),
            ('zero', 'python.literal', {'value':0}),
            ('positive', 'python.less_than', {}),
            ('guard', 'python.require', {}),
            ('ret1', 'python.return_flow', {})):
            self.node('callee', name, operation, props)
        self.wire('entry1','then','guard','exec','control')
        self.wire('guard','then','ret1','exec','control')
        self.wire('zero','value','positive','left')
        self.wire('param1','value','positive','right')
        self.wire('positive','result','guard','condition')
        self.wire('param1','value','ret1','value')
        for name, operation, props in (
            ('entry2','python.entry',{}),
            ('param2','python.parameter',{'parameter_id':'caller_arg'}),
            ('ret2','python.return_flow',{})):
            self.node('caller', name, operation, props)
        self.raw_node('caller','ordered','python.call_exec',{'callee_id':'callee'},
                      [{'name':'exec','type':'execution'}, {'name':'x','type':'py:int'}],
                      [{'name':'then','type':'execution'}, {'name':'result','type':'py:int'}])
        self.wire('entry2','then','ordered','exec','control')
        self.wire('ordered','then','ret2','exec','control')
        self.wire('param2','value','ordered','x')
        self.wire('ordered','result','ret2','value')

    def test_explicit_effectful_call_preserves_execution_and_result_mapping(self):
        self.qualified_graph()
        result=preview_python(self.graph.state)
        self.assertIsNotNone(result.source,result.issues)
        self.assertIn('guarded(',result.source)
        self.assertEqual([ident for ident,_ in result.node_lines].count('ordered'),1)
        env={}
        exec(result.source,env)
        self.assertEqual(env['invoke'](7),7)
        with self.assertRaisesRegex(ValueError,'Require failed'):
            env['invoke'](0)
        self.assertEqual(preview_python(self.graph.state),result)

    def test_pure_call_to_effectful_function_still_refused(self):
        self.qualified_graph()
        self.node('caller','pure','python.literal',{'value':1})
        self.raw_node('caller','bad','python.call',{'callee_id':'callee'},
                      [{'name':'x','type':'py:int'}],[{'name':'result','type':'py:int'}])
        self.wire('pure','value','bad','x')
        result=preview_python(self.graph.state)
        self.assertIsNone(result.source)
        self.assertIn('effectful function calls require explicit execution semantics',str(result.issues))

    def test_unordered_execution_call_is_not_qualified(self):
        self.qualified_graph()
        edge=next(e for e in self.graph.state['edges'] if e['source']=='entry2')
        self.edit('disconnect',edge=edge['id'])
        self.assertIsNone(preview_python(self.graph.state).source)

    def test_wrong_type_and_stale_signature_refused(self):
        self.qualified_graph()
        self.edit('add_parameter',function='callee',id='extra',name='extra',type='py:bool')
        result=preview_python(self.graph.state)
        self.assertIsNone(result.source)
        self.assertIn('signature',str(result.issues))

    def test_conflicting_parameter_name_rejected(self):
        self.qualified_graph()
        self.edit('rename_parameter',function='callee',parameter='arg',name='exec')
        result=preview_python(self.graph.state)
        self.assertIsNone(result.source)
        self.assertIn('conflicts with exec pin',str(result.issues))

    def test_recursive_execution_calls_are_rejected(self):
        self.qualified_graph()
        self.raw_node('callee','recursive','python.call_exec',{'callee_id':'caller'},
                      [{'name':'exec','type':'execution'},{'name':'y','type':'py:int'}],
                      [{'name':'then','type':'execution'},{'name':'result','type':'py:int'}])
        result=preview_python(self.graph.state)
        self.assertIsNone(result.source)
        self.assertIn('recursive',str(result.issues))

    def test_call_is_not_speculatively_executed_in_unselected_branch(self):
        self.qualified_graph()
        self.node('caller','choice','python.branch')
        self.node('caller','disabled','python.literal',{'value':False})
        self.node('caller','zero2','python.literal',{'value':0})
        self.node('caller','safe_return','python.return_flow')
        edge=next(e for e in self.graph.state['edges'] if e['source']=='entry2')
        self.edit('reconnect',edge=edge['id'],target='choice',target_port='choice-inputs-exec')
        self.wire('choice','true','ordered','exec','control')
        self.wire('choice','false','safe_return','exec','control')
        self.wire('disabled','value','choice','condition')
        self.wire('zero2','value','safe_return','value')
        result=preview_python(self.graph.state)
        self.assertIsNotNone(result.source,result.issues)
        env={}
        exec(result.source,env)
        # y=0 would fail Require if the call was hoisted before the Branch.
        self.assertEqual(env['invoke'](0),0)

    def test_effectful_call_inside_bounded_repeat_is_not_hoisted(self):
        self.qualified_graph()
        self.node('caller','repeat','python.repeat_int')
        self.node('caller','end','python.repeat_end')
        self.node('caller','zero2','python.literal',{'value':0})
        # Replace the current Entry -> call -> Return with
        # Entry -> Repeat(Body:call->End, After:Return).
        edge=next(e for e in self.graph.state['edges'] if e['source']=='entry2')
        self.edit('reconnect',edge=edge['id'],target='repeat',target_port='repeat-inputs-exec')
        edge=next(e for e in self.graph.state['edges'] if e['source']=='ordered' and e['relation']=='control')
        self.edit('reconnect',edge=edge['id'],target='end',target_port='end-inputs-exec')
        value_edge=next(e for e in self.graph.state['edges'] if e['source']=='ordered' and e['relation']=='data')
        self.edit('reconnect',edge=value_edge['id'],source='zero2',source_port='zero2-outputs-value')
        self.wire('repeat','body','ordered','exec','control')
        self.wire('repeat','after','ret2','exec','control')
        self.wire('param2','value','repeat','count')
        # Use y=0 as the argument for guarded(), which would raise if
        # called. Zero iterations must not invoke it even once.
        self.edit('replace_input',source='zero2',source_port='zero2-outputs-value',
                  target='ordered',target_port='ordered-inputs-x',relation='data')
        result=preview_python(self.graph.state)
        self.assertIsNotNone(result.source,result.issues)
        env={}
        exec(result.source,env)
        self.assertEqual(env['invoke'](0),0)
        with self.assertRaisesRegex(ValueError,'Require failed'):
            env['invoke'](1)

    def test_wrong_ordered_call_argument_type_rejected(self):
        self.qualified_graph()
        self.node('caller','flag','python.literal',{'value':True})
        self.edit('replace_input',source='flag',source_port='flag-outputs-value',
                  target='ordered',target_port='ordered-inputs-x',relation='data')
        result=preview_python(self.graph.state)
        self.assertIsNone(result.source)
        self.assertIn('expects py:int',str(result.issues))

    def test_save_undo_publication_and_no_implicit_execution(self):
        self.qualified_graph()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'ordered.smi-graph'; output=Path(tmp)/'ordered.py'
            self.graph.save_as(path)
            loaded=ProgramGraph.open(path)
            got=preview_python(loaded.state)
            self.assertIsNotNone(got.source,got.issues)
            receipt=publish_python(loaded,output,expected_revision=loaded.revision)
            self.assertEqual(output.read_text(),got.source)
            self.assertEqual(receipt.graph_revision,loaded.revision)
            edge=next(e for e in loaded.state['edges'] if e['source']=='ordered' and e['relation']=='control')
            loaded.edit(loaded.revision,'disconnect',edge=edge['id'])
            validate(loaded.state)
            self.assertIsNone(preview_python(loaded.state).source)
            self.assertTrue(loaded.undo(loaded.revision))
            self.assertIsNotNone(preview_python(loaded.state).source)
            with self.assertRaises(Exception):
                publish_python(loaded,output,expected_revision=loaded.revision)

if __name__ == '__main__': unittest.main()
