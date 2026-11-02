"""Executable structured Branch qualification without a general CFG runtime."""
import ast
from pathlib import Path
import tempfile
import unittest

from studio_native.program_graph import ProgramGraph, GraphConflict, template_ports, validate
from studio_native.python_lowering import preview_python, publish_python


class StructuredBranchTests(unittest.TestCase):
    def setUp(self):
        self.g=ProgramGraph()
        self.edit('add_function',id='f-choose',name='choose')
        self.edit('set_return_type',function='f-choose',type='py:int')
        for name in ('value','limit'):
            self.edit('add_parameter',function='f-choose',id='param-'+name,name=name,type='py:int')
        for name,op,props in (
            ('entry','python.entry',{}),('branch','python.branch',{}),
            ('true_return','python.return_flow',{}),('false_return','python.return_flow',{}),
            ('x','python.parameter',{'parameter_id':'param-value'}),
            ('limit','python.parameter',{'parameter_id':'param-limit'}),
            ('check','python.less_than',{}),('one','python.literal',{'value':1}),
            ('sum','python.add',{})):
            self.node(name,op,props)
        self.wire('entry','then','branch','exec','control')
        self.wire('branch','true','true_return','exec','control')
        self.wire('branch','false','false_return','exec','control')
        self.wire('x','value','check','left')
        self.wire('limit','value','check','right')
        self.wire('check','result','branch','condition')
        self.wire('x','value','sum','left')
        self.wire('one','value','sum','right')
        self.wire('sum','result','true_return','value')
        self.wire('x','value','false_return','value')

    def edit(self,action,**kwargs):
        return self.g.edit(self.g.revision,action,**kwargs)

    def node(self,node_id,operation,props=None):
        shape=template_ports(operation)
        for side in shape:
            for p in shape[side]:p['id']=node_id+'-'+p['name']
        self.edit('add_node',id=node_id,function='f-choose',operation=operation,
                  inputs=shape['inputs'],outputs=shape['outputs'],properties=props or {})

    def wire(self,source,out,target,inp,relation='data'):
        self.edit('connect',source=source,source_port=source+'-'+out,
                  target=target,target_port=target+'-'+inp,relation=relation)

    def preview(self):
        result=preview_python(self.g.state)
        self.assertFalse(result.issues,result.issues)
        self.assertIsNotNone(result.source)
        return result

    def test_generates_true_execution_branch_and_correct_behavior(self):
        preview=self.preview()
        tree=ast.parse(preview.source)
        branch=next(n for n in tree.body[0].body if isinstance(n,ast.If))
        self.assertIsInstance(branch.body[-1],ast.Return)
        self.assertIsInstance(branch.orelse[-1],ast.Return)
        ns={}
        exec(preview.source,ns)
        self.assertEqual(ns['choose'](3,10),4)
        self.assertEqual(ns['choose'](10,10),10)
        self.assertEqual(ns['choose'](-8,2),-7)
        self.assertEqual(ns['choose'](4,1),4)
        self.assertEqual(preview.source,preview_python(self.g.state).source)
        self.assertEqual(set(n for n,_ in preview.node_lines),
                         {n['id'] for n in self.g.state['nodes']})

    def test_only_selected_arm_producers_execute(self):
        tree=ast.parse(self.preview().source)
        body=tree.body[0].body
        arm=next(n for n in body if isinstance(n,ast.If))
        true_calls=[n for statement in arm.body for n in ast.walk(statement) if isinstance(n,ast.BinOp)]
        self.assertTrue(true_calls)
        self.assertNotIn(' + ',ast.unparse(ast.Module(body=body[:body.index(arm)],type_ignores=[])))
        self.assertFalse(any(isinstance(n,ast.BinOp) for n in arm.orelse))

    def test_layout_is_nonsemantic_and_publication_is_explicit(self):
        first=self.preview()
        self.edit('move_node',node='branch',x=700,y=-900)
        self.assertEqual(self.preview(),first)
        with tempfile.TemporaryDirectory() as folder:
            graph=Path(folder)/'choose.smi-graph'
            destination=Path(folder)/'choose.py'
            self.g.save(graph)
            reloaded=ProgramGraph.open(graph)
            self.assertEqual(reloaded.state,self.g.state)
            published=publish_python(reloaded,destination,expected_revision=reloaded.revision)
            self.assertEqual(destination.read_text(),first.source)
            self.assertEqual(published.node_lines,first.node_lines)
            self.assertEqual(reloaded.state,self.g.state)
            with self.assertRaises(Exception):
                publish_python(reloaded,destination,expected_revision=reloaded.revision)

    def test_incomplete_branches_remain_savable(self):
        edge=next(e for e in self.g.state['edges'] if e['target']=='true_return' and e['relation']=='control')
        self.edit('disconnect',edge=edge['id'])
        validate(self.g.state)
        self.assertIn('Branch output',str(preview_python(self.g.state).issues))
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'incomplete.smi-graph'
            self.g.save(p)
            self.assertIsNone(preview_python(ProgramGraph.open(p).state).source)
            with self.assertRaises(GraphConflict):
                publish_python(self.g,Path(folder)/'forbidden.py',expected_revision=self.g.revision)

    def test_wrong_condition_type_refuses_generation(self):
        self.edit('replace_input',source='x',source_port='x-value',target='branch',target_port='branch-condition')
        self.assertIsNone(preview_python(self.g.state).source)  # orphaned comparison and untyped replacement

    def test_wrong_return_type_refuses_generation(self):
        self.edit('set_return_type',function='f-choose',type='py:bool')
        self.assertIn('value type differs from function return type',str(preview_python(self.g.state).issues))

    def test_no_unqualified_extra_control_edges(self):
        state=self.g.state
        state['edges'].append(dict(state['edges'][0],id='extra-execution-edge',target='true_return',target_port='true_return-exec'))
        self.assertIsNone(preview_python(state).source)  # structurally invalid duplicate pin

    def test_incomplete_control_graph_does_not_activate_unqualified_lowering(self):
        self.edit('remove_node',node='branch')
        self.assertIsNone(preview_python(self.g.state).source)

    def test_mixed_plain_and_flow_return_is_refused(self):
        self.node('plain','python.return')
        self.assertIn('mix Return node kinds',str(preview_python(self.g.state).issues))

    def test_duplicate_branch_refused(self):
        self.node('second','python.branch')
        self.assertIsNone(preview_python(self.g.state).source)  # missing inputs also invalidate the duplicate

    def test_mutating_control_node_properties_is_refused(self):
        self.edit('set_property',node='branch',key='unsafe',value=True)
        self.assertIn('cannot have properties',str(preview_python(self.g.state).issues))

    def test_broken_control_port_signature_refused(self):
        state=self.g.state
        next(n for n in state['nodes'] if n['id']=='branch')['ports']['outputs'][0]['name']='YES'
        self.assertIn('signature',str(preview_python(state).issues))

    def test_no_geometry_affects_semantic_control_order(self):
        original=self.preview()
        for node in self.g.state['nodes']:
            self.edit('move_node',node=node['id'],x=-1200,y=1000)
        self.assertEqual(self.preview(),original)

    def test_undo_and_redo_a_control_edge(self):
        edge=next(e for e in self.g.state['edges'] if e['source']=='branch' and e['target']=='false_return')
        before=self.preview()
        self.edit('disconnect',edge=edge['id'])
        self.assertIsNone(preview_python(self.g.state).source)
        self.assertTrue(self.g.undo(self.g.revision))
        self.assertEqual(self.preview().source,before.source)
        self.assertTrue(self.g.redo(self.g.revision))
        self.assertIsNone(preview_python(self.g.state).source)


    def test_qualified_graph_function_can_call_branching_function(self):
        self.edit('add_function',id='f-wrapper',name='wrapper')
        self.edit('add_parameter',function='f-wrapper',id='p-y',name='y',type='py:int')
        self.edit('add_parameter',function='f-wrapper',id='p-n',name='n',type='py:int')
        self.edit('set_return_type',function='f-wrapper',type='py:int')
        for node,op,props in (
            ('y','python.parameter',{'parameter_id':'p-y'}),
            ('n','python.parameter',{'parameter_id':'p-n'}),
            ('call','python.call',{'callee_id':'f-choose'}),
            ('finish','python.return',{})):
            if op=='python.call':
                self.edit('add_node',id=node,function='f-wrapper',operation=op,
                          inputs=[{'id':node+'-'+name,'name':name,'type':'py:int'}
                                  for name in ('value','limit')],
                          outputs=[{'id':node+'-result','name':'result','type':'py:int','required':False}],
                          properties=props)
            else:
                ports=template_ports(op)
                for side in ports:
                    for port in ports[side]:port['id']=node+'-'+port['name']
                self.edit('add_node',id=node,function='f-wrapper',operation=op,
                          inputs=ports['inputs'],outputs=ports['outputs'],properties=props)
        for source,out,target,inp in (('y','value','call','value'),('n','value','call','limit'),
                                      ('call','result','finish','value')):
            self.wire(source,out,target,inp)
        compiled=self.preview()
        functions={}
        exec(compiled.source,functions)
        self.assertEqual(functions['wrapper'](2,4),3)
        self.assertEqual(functions['wrapper'](7,4),7)
        self.assertEqual([f.name for f in ast.parse(compiled.source).body],['choose','wrapper'])

    def test_two_boolean_return_arms(self):
        self.edit('set_return_type',function='f-choose',type='py:bool')
        self.edit('remove_node',node='sum')
        self.edit('remove_node',node='one')
        self.node('yes','python.literal',{'value':True})
        self.node('no','python.literal',{'value':False})
        self.wire('yes','value','true_return','value')
        self.edit('replace_input',source='no',source_port='no-value',target='false_return',target_port='false_return-value')
        compiled=self.preview()
        scope={}
        exec(compiled.source,scope)
        self.assertIs(scope['choose'](1,2),True)
        self.assertIs(scope['choose'](2,1),False)

    def test_shared_pure_expression_has_no_cross_arm_state_dependency(self):
        self.edit('remove_node',node='one')
        self.edit('remove_node',node='sum')
        self.node('one','python.literal',{'value':1})
        self.node('sum','python.add')
        self.wire('x','value','sum','left')
        self.wire('one','value','sum','right')
        self.wire('sum','result','true_return','value')
        self.edit('replace_input',source='sum',source_port='sum-result',
                  target='false_return',target_port='false_return-value')
        compiled=self.preview()
        tree=ast.parse(compiled.source)
        flow=next(node for node in tree.body[0].body if isinstance(node,ast.If))
        self.assertTrue(any(isinstance(node,ast.BinOp) for stmt in flow.body for node in ast.walk(stmt)))
        self.assertTrue(any(isinstance(node,ast.BinOp) for stmt in flow.orelse for node in ast.walk(stmt)))
        scope={}
        exec(compiled.source,scope)
        self.assertEqual(scope['choose'](2,5),3)
        self.assertEqual(scope['choose'](7,5),8)
        self.assertEqual([n for n,_ in compiled.node_lines].count('sum'),2)

    def test_wrong_control_relation_is_rejected_by_graph_document(self):
        state=self.g.state
        edge=next(e for e in state['edges'] if e['source']=='entry')
        edge['relation']='data'
        self.assertIsNone(preview_python(state).source)
        self.assertIn('execution',str(preview_python(state).issues))

    def test_extra_orphan_pure_node_fails_qualification(self):
        self.node('unused','python.literal',{'value':999})
        self.assertIn('orphan',str(preview_python(self.g.state).issues))


if __name__=='__main__':unittest.main()
