"""Source rewiring for existing Boolean/Return pins, proved by trial compiler.

These tests build real graph-owned functions. No alternate reverse AST or new
identity owner is used, and a source edit cannot discard an orphan producer.
"""
import ast
import tempfile
import unittest
from pathlib import Path

from studio_native.program_graph import ProgramGraph, ProgramGraphError, template_ports
from studio_native.python_lowering import (preview_python, review_generated_source_edit,
    import_generated_source_edit, review_independent_source_functions,
    import_independent_source_functions)
from studio_native.source_editor import SourceDocumentSession


class Harness:
    def __init__(self, name='choose', return_type='py:bool'):
        self.graph=ProgramGraph()
        self.edit('add_function',id='fn',name=name)
        self.edit('set_return_type',function='fn',type=return_type)
    def edit(self, action, **arguments):
        return self.graph.edit(self.graph.revision,action,**arguments)
    def parameter(self, label, typ='py:int'):
        self.edit('add_parameter',function='fn',id='p-'+label,name=label,type=typ)
        self.node(label,'python.parameter',{'parameter_id':'p-'+label})
    def node(self,ident,operation,properties=None):
        ports=template_ports(operation)
        for side in ports:
            for port in ports[side]:
                port['id']=f'{ident}-{port["name"]}'
        self.edit('add_node',id=ident,function='fn',operation=operation,
            inputs=ports['inputs'],outputs=ports['outputs'],properties=properties or {})
    def wire(self,source,target,port,source_port=None,relation='data'):
        if source_port is None:
            ports=next(n for n in self.graph.state['nodes'] if n['id']==source)['ports']['outputs']
            source_port=next(p['name'] for p in ports if p['type']!='execution')
        self.edit('connect',source=source,source_port=f'{source}-{source_port}',
            target=target,target_port=f'{target}-{port}',relation=relation)
    def source(self):
        receipt=preview_python(self.graph.state)
        assert receipt.source is not None, receipt.issues
        return receipt.source


class SemanticRewiringTests(unittest.TestCase):
    def make_boolean(self):
        g=Harness()
        for p in ('x','y'):
            g.parameter(p)
        for name in ('eq1','eq2'):
            g.node(name,'python.equal_int')
        g.node('not1','python.not')
        g.node('not2','python.not')
        g.node('choice','python.select_bool')
        g.node('return','python.return')
        for source,target,port in (
            ('x','eq1','left'),('y','eq1','right'),
            ('x','eq2','left'),('y','eq2','right'),
            ('eq1','not1','value'),('eq2','not2','value'),
            ('eq1','choice','condition'),('not1','choice','true_value'),
            ('not2','choice','false_value'),('choice','return','value')):
            g.wire(source,target,port)
        return g

    def test_not_input_switch_keeps_other_users_alive(self):
        g=self.make_boolean(); base=g.source()
        expressions=[n for n in ast.walk(ast.parse(base)) if isinstance(n,ast.Assign)
            and isinstance(n.value,ast.UnaryOp) and isinstance(n.value.op,ast.Not)]
        self.assertEqual(len(expressions),2)
        first=expressions[0]
        line=base.splitlines()[first.lineno-1]
        other=next(n for n in expressions if n is not first)
        old=first.value.operand.id
        new=other.value.operand.id
        edited=base.replace(line,line.replace('not '+old,'not '+new))
        self.assertNotEqual(base,edited)
        review=review_generated_source_edit(g.graph,base,edited,expected_revision=g.graph.revision)
        self.assertEqual([(c.node_id,c.action,c.input_port) for c in review.changes],
                         [('not1','replace_input','value')])
        original=g.graph.state
        self.assertTrue(import_generated_source_edit(g.graph,base,edited,expected_revision=review.graph_revision))
        self.assertEqual(g.source(),edited)
        self.assertTrue(g.graph.undo(g.graph.revision))
        self.assertEqual(g.graph.state['edges'],original['edges'])

    def test_select_branch_swap_combines_two_wires(self):
        g=self.make_boolean(); base=g.source()
        item=next(n for n in ast.walk(ast.parse(base)) if isinstance(n,ast.Assign) and isinstance(n.value,ast.IfExp))
        line=base.splitlines()[item.lineno-1]
        original_line=line
        edited_line=f'    {item.targets[0].id} = {item.value.orelse.id} if {item.value.test.id} else {item.value.body.id}'
        edited=base.replace(original_line,edited_line)
        review=review_generated_source_edit(g.graph,base,edited,expected_revision=g.graph.revision)
        self.assertEqual([(c.node_id,c.input_port) for c in review.changes],
                         [('choice','true_value'),('choice','false_value')])
        self.assertTrue(import_generated_source_edit(g.graph,base,edited,expected_revision=review.graph_revision))
        self.assertEqual(g.source(),edited)

    def test_independent_boolean_batch_combines_not_and_select_rewires(self):
        g=self.make_boolean();base=g.source()
        tree=ast.parse(base)
        nots=[n for n in ast.walk(tree) if isinstance(n,ast.Assign) and isinstance(n.value,ast.UnaryOp)
              and isinstance(n.value.op,ast.Not)]
        select=next(n for n in ast.walk(tree) if isinstance(n,ast.Assign) and isinstance(n.value,ast.IfExp))
        old_not,new_not=nots
        lines=base.splitlines(keepends=True)
        line=lines[old_not.lineno-1]
        lines[old_not.lineno-1]=line.replace('not '+old_not.value.operand.id,
                                           'not '+new_not.value.operand.id)
        lines[select.lineno-1]=(f'    {select.targets[0].id} = '
            f'{select.value.orelse.id} if {select.value.test.id} else '
            f'{select.value.body.id}\n')
        edited=''.join(lines)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'user.py'
            authored='# independently edited source\n\n'+edited+'\n# unrelated data\n'
            path.write_text(authored,encoding='utf-8')
            session=SourceDocumentSession.open(path)
            before=g.graph.state
            review=review_independent_source_functions(g.graph,session,('choose',),
                expected_graph_revision=g.graph.revision)
            self.assertEqual({(c.node_id,c.input_port) for c in review.changes},
                {('not1','value'),('choice','true_value'),('choice','false_value')})
            self.assertEqual(g.graph.state,before)
            self.assertTrue(import_independent_source_functions(g.graph,session,('choose',),
                expected_graph_revision=review.graph_revision,
                expected_source_revision=review.source_revision,
                expected_source_sha256=review.source_sha256))
            self.assertEqual(g.source(),edited)
            self.assertEqual(session.text,authored)
            self.assertTrue(g.graph.undo(g.graph.revision))
            self.assertEqual(g.graph.state['nodes'],before['nodes'])
            self.assertEqual(g.graph.state['edges'],before['edges'])

    def make_flow(self):
        g=Harness(return_type='py:int')
        for p in ('x','y'):g.parameter(p)
        for node,op in (('entry','python.entry'),('less','python.less_than'),
                        ('branch','python.branch'),('true_ret','python.return_flow'),
                        ('false_ret','python.return_flow')):
            g.node(node,op)
        g.wire('x','less','left')
        g.wire('y','less','right')
        g.wire('less','branch','condition')
        g.wire('x','true_ret','value')
        g.wire('y','false_ret','value')
        g.wire('entry','branch','exec','then','control')
        g.wire('branch','true_ret','exec','true','control')
        g.wire('branch','false_ret','exec','false','control')
        return g

    def test_structured_return_flow_rewire_and_independent_source(self):
        g=self.make_flow();base=g.source()
        # Both parameters stay live in the condition and remain in scope.
        returns=[n for n in ast.walk(ast.parse(base)) if isinstance(n,ast.Return)]
        self.assertEqual(len(returns),2)
        a,b=returns
        line=base.splitlines()[a.lineno-1]
        edited=base.replace(line,' '*(a.col_offset)+f'return {b.value.id}')
        receipt=review_generated_source_edit(g.graph,base,edited,expected_revision=g.graph.revision)
        self.assertEqual([(c.node_id,c.input_port) for c in receipt.changes],
            [('true_ret','value')])
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'external.py'
            authored='import os\n\n# arbitrary source-owned header\n'+edited+'\n# source-owned trailer\n'
            path.write_text(authored,encoding='utf-8')
            session=SourceDocumentSession.open(path)
            independent=review_independent_source_functions(g.graph,session,('choose',),
                expected_graph_revision=g.graph.revision)
            self.assertEqual([(c.node_id,c.input_port) for c in independent.changes],
                [('true_ret','value')])
            self.assertTrue(import_independent_source_functions(g.graph,session,('choose',),
                expected_graph_revision=independent.graph_revision,
                expected_source_revision=independent.source_revision,
                expected_source_sha256=independent.source_sha256))
            self.assertEqual(g.source(),edited)
            self.assertEqual(session.text,authored)

    def test_existing_pure_call_argument_rewire_keeps_both_parameters_live(self):
        # A callee is graph-owned and separately qualified. Only its *existing*
        # call input is rewired; the call target, execution order, and nodes
        # remain unchanged. Both x and y are used elsewhere, so no orphan.
        g=Harness(name='caller',return_type='py:int')
        for p in ('x','y'):
            g.parameter(p)
        g.edit('add_function',id='callee',name='increment')
        g.edit('set_return_type',function='callee',type='py:int')
        g.edit('add_parameter',function='callee',id='p-a',name='a',type='py:int')
        callee_ports=template_ports('python.parameter')
        for side in callee_ports:
            for port in callee_ports[side]:
                port['id']='ca-'+port['name']
        g.edit('add_node',id='ca',function='callee',operation='python.parameter',
               inputs=callee_ports['inputs'],outputs=callee_ports['outputs'],
               properties={'parameter_id':'p-a'})
        callee_return=template_ports('python.return')
        for side in callee_return:
            for port in callee_return[side]:
                port['id']='cr-'+port['name']
        g.edit('add_node',id='cr',function='callee',operation='python.return',
               inputs=callee_return['inputs'],outputs=callee_return['outputs'],properties={})
        g.edit('connect',source='ca',source_port='ca-value',target='cr',target_port='cr-value')
        g.edit('add_node',id='z-call',function='fn',operation='python.call',
               inputs=[{'id':'z-call-a','name':'a','type':'py:int'}],
               outputs=[{'id':'z-call-result','name':'result','type':'py:int','required':False}],
               properties={'callee_id':'callee'})
        g.node('z-sum','python.add')
        g.node('zz-final','python.add')
        g.node('zz-return','python.return')
        g.wire('x','z-call','a')
        g.wire('x','z-sum','left')
        g.wire('y','z-sum','right')
        g.wire('z-call','zz-final','left')
        g.wire('z-sum','zz-final','right')
        g.wire('zz-final','zz-return','value')
        baseline=g.source()
        call=next(n for n in ast.walk(ast.parse(baseline)) if isinstance(n,ast.Assign)
                  and isinstance(n.value,ast.Call))
        target=call.value.args[0].id
        param_names=[n for n in ast.walk(ast.parse(baseline)) if isinstance(n,ast.Assign)
                     and isinstance(n.value,ast.Name) and n.value.id=='y']
        self.assertEqual(len(param_names),1)
        replacement=param_names[0].targets[0].id
        line=baseline.splitlines()[call.lineno-1]
        edited=baseline.replace(line,line.replace(f'increment({target})',f'increment({replacement})'))
        self.assertNotEqual(edited,baseline)
        review=review_generated_source_edit(g.graph,baseline,edited,
                                            expected_revision=g.graph.revision)
        self.assertEqual([(c.node_id,c.action,c.input_port) for c in review.changes],
                         [('z-call','replace_input','a')])
        before=g.graph.state
        self.assertTrue(import_generated_source_edit(g.graph,baseline,edited,
                                                    expected_revision=review.graph_revision))
        self.assertEqual(g.source(),edited)
        self.assertTrue(g.graph.undo(g.graph.revision))
        self.assertEqual(g.graph.state['edges'],before['edges'])

    def test_pure_return_change_orphans_old_producer_and_refuses(self):
        g=self.make_boolean();before=g.graph.state;base=g.source()
        return_line=next(line for line in base.splitlines() if line.strip().startswith('return '))
        edited=base.replace(return_line,'    return _smi_value_0')
        with self.assertRaises(ProgramGraphError):
            review_generated_source_edit(g.graph,base,edited,expected_revision=g.graph.revision)
        self.assertEqual(g.graph.state,before)

    def test_return_statement_topology_cannot_be_imported(self):
        g=self.make_flow();base=g.source();before=g.graph.state
        # No heuristic pairing of Return nodes across changed source control
        # structure, even if both original producer variables still exist.
        edited=base.replace('    else:', '    elif True:')
        with self.assertRaises(ProgramGraphError):
            review_generated_source_edit(g.graph,base,edited,expected_revision=g.graph.revision)
        self.assertEqual(g.graph.state,before)

    def test_unqualified_boolean_change_refuses(self):
        g=self.make_boolean();base=g.source()
        altered=base.replace('not _smi_value_', 'not missing_value_')
        with self.assertRaises(ProgramGraphError):
            review_generated_source_edit(g.graph,base,altered,expected_revision=g.graph.revision)

if __name__=='__main__':unittest.main()
