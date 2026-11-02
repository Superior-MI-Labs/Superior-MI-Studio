"""Execution-ordered typed capture; a stepping stone, NOT mutable variables."""
import ast
from pathlib import Path
import tempfile
import unittest

from studio_native.program_graph import ProgramGraph, template_ports, validate
from studio_native.python_lowering import preview_python, publish_python


class OrderedBindingTests(unittest.TestCase):
    def setUp(self):
        self.graph=ProgramGraph()
        self.edit('add_function', id='fn', name='capture')
        self.edit('set_return_type', function='fn', type='py:int')

    def edit(self, action, **kwargs):
        return self.graph.edit(self.graph.revision, action, **kwargs)

    def node(self, ident, operation, props=None):
        shape=template_ports(operation)
        for side in shape:
            for port in shape[side]:
                port['id']=f'{ident}-{side}-{port["name"]}'
        self.edit('add_node', id=ident, function='fn', operation=operation,
                  properties=props or {}, inputs=shape['inputs'], outputs=shape['outputs'])
        return ident

    def wire(self, source, output, target, inp, relation='data'):
        self.edit('connect', source=source, source_port=f'{source}-outputs-{output}',
                  target=target, target_port=f'{target}-inputs-{inp}', relation=relation)

    def standard(self):
        self.node('entry','python.entry')
        self.node('bind','python.bind_int')
        self.node('return','python.return_flow')
        self.node('two','python.literal',{'value':2})
        self.node('three','python.literal',{'value':3})
        self.node('sum','python.add')
        self.wire('entry','then','bind','exec','control')
        self.wire('bind','then','return','exec','control')
        self.wire('two','value','bind','value')
        self.wire('bind','value','sum','left')
        self.wire('three','value','sum','right')
        self.wire('sum','result','return','value')

    def test_ordered_binding_generates_actual_python_and_node_mapping(self):
        self.standard()
        result=preview_python(self.graph.state)
        self.assertIsNotNone(result.source,result.issues)
        self.assertIn('def capture():',result.source)
        self.assertEqual(set(dict(result.node_lines)),
                         {n['id'] for n in self.graph.state['nodes']})
        self.assertLess(dict(result.node_lines)['bind'],dict(result.node_lines)['sum'])
        namespace={}
        exec(result.source,namespace)
        self.assertEqual(namespace['capture'](),5)
        self.assertEqual(result,preview_python(self.graph.state))

    def test_binding_input_must_match_type(self):
        self.standard()
        self.edit('set_property',node='two',key='value',value=True)
        result=preview_python(self.graph.state)
        self.assertIsNone(result.source)
        self.assertIn('binding expects py:int',str(result.issues))

    def test_binding_cannot_be_used_before_execution(self):
        self.standard()
        # Source expression for Bind uses its own output, creating a
        # cross-epoch value dependency. Refuse rather than hoist.
        edge=next(e for e in self.graph.state['edges'] if e['target']=='bind'
                  and e['relation']=='data')
        self.edit('reconnect',edge=edge['id'],source='bind',source_port='bind-outputs-value')
        result=preview_python(self.graph.state)
        self.assertIsNone(result.source)
        self.assertTrue(any('cyclic' in issue or 'before its execution' in issue for issue in result.issues),result.issues)

    def test_binding_cannot_appear_on_wrong_branch(self):
        self.standard()
        self.node('condition','python.literal',{'value':False})
        self.node('branch','python.branch')
        self.node('other_return','python.return_flow')
        # Entry -> Branch. True -> Bind -> Return, False -> Return.
        edge=next(e for e in self.graph.state['edges'] if e['source']=='entry')
        self.edit('reconnect',edge=edge['id'],target='branch',target_port='branch-inputs-exec')
        self.wire('branch','true','bind','exec','control')
        self.wire('branch','false','other_return','exec','control')
        self.wire('condition','value','branch','condition')
        self.wire('bind','value','other_return','value')
        result=preview_python(self.graph.state)
        self.assertIsNone(result.source)
        self.assertIn('before its execution',str(result.issues))

    def test_binding_is_savable_and_explicitly_publishable(self):
        self.standard()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'capture.smi-graph'
            output=Path(tmp)/'capture.py'
            fork=self.graph.save_as(path)
            reopened=ProgramGraph.open(path)
            self.assertEqual(fork.state,reopened.state)
            publication=publish_python(reopened,output,expected_revision=reopened.revision)
            self.assertEqual(output.read_text(),preview_python(reopened.state).source)
            self.assertEqual(dict(publication.node_lines),dict(preview_python(reopened.state).node_lines))

    def test_binding_undo_redo_and_incomplete_document(self):
        self.standard()
        initial=preview_python(self.graph.state)
        self.assertIsNotNone(initial.source,initial.issues)
        wire=next(e for e in self.graph.state['edges'] if e['target']=='bind'
                  and e['relation']=='data')
        self.edit('disconnect',edge=wire['id'])
        validate(self.graph.state)
        self.assertIsNone(preview_python(self.graph.state).source)
        self.assertTrue(self.graph.undo(self.graph.revision))
        self.assertEqual(initial,preview_python(self.graph.state))
        self.assertTrue(self.graph.redo(self.graph.revision))
        self.assertIsNone(preview_python(self.graph.state).source)

    def test_bool_binding_capture(self):
        self.edit('set_return_type',function='fn',type='py:bool')
        self.node('entry','python.entry')
        self.node('bind','python.bind_bool')
        self.node('out','python.return_flow')
        self.node('truth','python.literal',{'value':True})
        self.wire('entry','then','bind','exec','control')
        self.wire('bind','then','out','exec','control')
        self.wire('truth','value','bind','value')
        self.wire('bind','value','out','value')
        result=preview_python(self.graph.state)
        self.assertIsNotNone(result.source,result.issues)
        namespace={}
        exec(result.source,namespace)
        self.assertIs(namespace['capture'](),True)

    def test_persisted_example_round_trip_and_publication(self):
        example=Path(__file__).resolve().parents[1]/'examples'/'qualified-ordered-bindings.smi-graph'
        graph=ProgramGraph.open(example)
        result=preview_python(graph.state)
        self.assertIsNotNone(result.source,result.issues)
        namespace={}
        exec(result.source,namespace)
        self.assertEqual(namespace['capture'](),5)
        self.assertEqual(set(dict(result.node_lines)),{n['id'] for n in graph.state['nodes']})
        with tempfile.TemporaryDirectory() as temporary:
            receipt=publish_python(graph,Path(temporary)/'capture.py',expected_revision=graph.revision)
            self.assertEqual(dict(receipt.node_lines),dict(result.node_lines))

    def test_effectful_binding_cannot_be_hoisted_through_pure_call(self):
        self.standard()
        self.edit('add_function',id='caller',name='reader')
        self.edit('set_return_type',function='caller',type='py:int')
        # Copy only signature-consistent call ports into new function.
        ports={'inputs':[], 'outputs':[{'id':'call-value','name':'result','type':'py:int','required':False}]}
        self.edit('add_node',id='call',function='caller',operation='python.call',
                  properties={'callee_id':'fn'},**ports)
        ret={'inputs':[{'id':'ret-value','name':'value','type':'py:int'}],'outputs':[]}
        self.edit('add_node',id='ret',function='caller',operation='python.return',
                  properties={},**ret)
        self.edit('connect',source='call',source_port='call-value',target='ret',target_port='ret-value',relation='data')
        result=preview_python(self.graph.state)
        self.assertIsNone(result.source)
        self.assertIn('effectful function calls',str(result.issues))


if __name__=='__main__': unittest.main()
