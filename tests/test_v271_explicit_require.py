"""The first qualified sequential effect, through existing ProgramGraph + lowering."""
import ast
from pathlib import Path
import tempfile
import unittest

from studio_native.program_graph import ProgramGraph, template_ports, validate, GraphConflict
from studio_native.python_lowering import preview_python, publish_python

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / 'examples' / 'qualified-nested-branches.smi-graph'


class RequireExecutionTests(unittest.TestCase):
    def setUp(self):
        self.graph = ProgramGraph.open(BASE)
        self.add_guard('guard', 'entry', 'then', 'outer', 'exec', 'outer_check')

    def edit(self, action, **options):
        return self.graph.edit(self.graph.revision, action, **options)

    def add_guard(self, identity, origin, from_port, target, to_port, condition):
        shape = template_ports('python.require')
        for side in shape:
            for port in shape[side]:
                port['id'] = identity + '-' + port['name']
        self.edit('add_node', function='func', id=identity, operation='python.require',
                  inputs=shape['inputs'], outputs=shape['outputs'], properties={})
        old = next(e for e in self.graph.state['edges'] if e['source'] == origin
                   and e['target'] == target and e['relation'] == 'control')
        self.edit('disconnect', edge=old['id'])
        self.wire(origin, from_port, identity, 'exec', 'control')
        self.wire(identity, 'then', target, to_port, 'control')
        self.wire(condition, 'result', identity, 'condition')

    def wire(self, origin, from_port, target, to_port, relation='data'):
        self.edit('connect', source=origin, source_port=origin + '-' + from_port,
                  target=target, target_port=target + '-' + to_port, relation=relation)

    def preview(self):
        result = preview_python(self.graph.state)
        self.assertIsNotNone(result.source, result.issues)
        return result

    def test_guard_is_effectful_and_ordered_before_nested_branches(self):
        result = self.preview()
        tree = ast.parse(result.source)
        guards = [n for n in ast.walk(tree) if isinstance(n, ast.Raise)]
        self.assertEqual(len(guards), 1)
        self.assertIn('raise ValueError', result.source)
        self.assertNotIn('assert ', result.source)  # stable even with optimized Python
        positions = dict(result.node_lines)
        self.assertEqual(set(positions), {n['id'] for n in self.graph.state['nodes']})
        self.assertLess(positions['outer_check'], positions['guard'])
        self.assertLess(positions['guard'], positions['outer'])
        self.assertEqual('if not ' in result.source.splitlines()[positions['guard']-1], True)
        ns = {}
        exec(result.source, ns)
        self.assertEqual(ns['choose'](1, 10, 5), 2)
        self.assertEqual(ns['choose'](7, 10, 5), 9)
        with self.assertRaisesRegex(ValueError, 'Require failed'):
            ns['choose'](13, 10, 5)

    def test_guard_chain_is_valid_and_uses_one_effect_per_node(self):
        self.add_guard('guard2', 'guard', 'then', 'outer', 'exec', 'outer_check')
        result = self.preview()
        self.assertEqual(result.source.count('raise ValueError'), 2)
        positions = dict(result.node_lines)
        self.assertLess(positions['guard'], positions['guard2'])
        self.assertLess(positions['guard2'], positions['outer'])

    def test_disconnected_guard_remains_savable_but_not_publishable(self):
        edge = next(e for e in self.graph.state['edges'] if e['source']=='guard'
                    and e['relation']=='control')
        self.edit('disconnect', edge=edge['id'])
        validate(self.graph.state)
        self.assertIsNone(preview_python(self.graph.state).source)
        with tempfile.TemporaryDirectory() as tmp:
            saved = Path(tmp) / 'incomplete.smi-graph'
            fork = self.graph.save_as(saved)
            with self.assertRaises(GraphConflict):
                publish_python(fork, Path(tmp) / 'forbidden.py',
                               expected_revision=fork.revision)
            self.assertFalse((Path(tmp) / 'forbidden.py').exists())

    def test_rejects_bad_conditions_and_changed_signature(self):
        self.edit('replace_input', source='x', source_port='x-value',
                  target='guard', target_port='guard-condition')
        self.assertIsNone(preview_python(self.graph.state).source)
        self.edit('replace_input', source='outer_check', source_port='outer_check-result',
                  target='guard', target_port='guard-condition')
        self.edit('set_property', node='guard', key='hidden', value=True)
        self.assertIn('properties', '; '.join(preview_python(self.graph.state).issues))
        self.edit('set_property', node='guard', key='hidden', value=False)
        self.assertIsNone(preview_python(self.graph.state).source)

    def test_refuses_guard_join_and_control_cycle(self):
        state = self.graph.state
        # Bypass the editor to exercise lowering refusal independently of document validity.
        edge = next(e for e in state['edges'] if e['source']=='guard' and e['relation']=='control')
        edge['target'] = 'entry'
        edge['target_port'] = 'entry-then'
        self.assertIsNone(preview_python(state).source)

    def test_guard_cannot_be_used_as_a_data_producer(self):
        state = self.graph.state
        edge = next(e for e in state['edges'] if e['source']=='outer_check' and e['target']=='guard')
        edge['source']='guard'
        edge['source_port']='guard-then'
        self.assertIsNone(preview_python(state).source)

    def test_guarded_function_cannot_be_called_as_pure_expression(self):
        self.edit('add_function', id='consumer', name='consume')
        self.edit('set_return_type', function='consumer', type='py:int')
        self.edit('add_parameter', function='consumer', id='ca', name='a', type='py:int')
        self.edit('add_parameter', function='consumer', id='cb', name='b', type='py:int')
        self.edit('add_parameter', function='consumer', id='cc', name='c', type='py:int')
        for ident, op, props, ins, outs in (
            ('aarg','python.parameter',{'parameter_id':'ca'}, [], [('value','py:int')]),
            ('barg','python.parameter',{'parameter_id':'cb'}, [], [('value','py:int')]),
            ('carg','python.parameter',{'parameter_id':'cc'}, [], [('value','py:int')]),
            ('caller','python.call',{'callee_id':'func'},
             [('x','py:int'),('limit','py:int'),('offset','py:int')], [('result','py:int')]),
            ('done','python.return',{}, [('value','py:int')], []),
        ):
            self.edit('add_node', id=ident, function='consumer', operation=op, properties=props,
                      inputs=[{'id':ident+'-'+name,'name':name,'type':kind} for name,kind in ins],
                      outputs=[{'id':ident+'-'+name,'name':name,'type':kind,'required':False}
                               for name,kind in outs])
        for origin, out, target, pin in (
            ('aarg','value','caller','x'),('barg','value','caller','limit'),
            ('carg','value','caller','offset'),('caller','result','done','value')):
            self.wire(origin,out,target,pin)
        preview = preview_python(self.graph.state)
        self.assertIsNone(preview.source)
        self.assertIn('effectful function calls', str(preview.issues))

    def test_repeated_preview_persistence_and_explicit_publish(self):
        before = self.preview()
        self.edit('move_node', node='guard', x=70, y=900)
        self.assertEqual(before, self.preview())
        with tempfile.TemporaryDirectory() as temp:
            graph = Path(temp) / 'guard.smi-graph'
            output = Path(temp) / 'guard.py'
            self.graph.save_as(graph)
            reopened = ProgramGraph.open(graph)
            self.assertEqual(before, preview_python(reopened.state))
            receipt = publish_python(reopened, output, expected_revision=reopened.revision)
            self.assertEqual(output.read_text(), before.source)
            self.assertEqual(receipt.node_lines, before.node_lines)
            self.assertNotEqual(reopened.state['id'], self.graph.state['id'])
            self.assertEqual(reopened.state['nodes'], self.graph.state['nodes'])
            with self.assertRaises(Exception):
                publish_python(reopened, output, expected_revision=reopened.revision)

    def test_undo_redo_restore_exact_effect(self):
        initial = self.preview()
        self.edit('move_node', node='guard', x=60, y=40)
        current_revision = self.graph.revision
        self.assertTrue(self.graph.undo(current_revision))
        self.assertEqual(initial, self.preview())
        self.assertTrue(self.graph.redo(self.graph.revision))
        self.assertEqual(initial, self.preview())

    def test_native_smoke_covers_editor_creation_and_publication(self):
        smoke = (ROOT / 'studio_native' / 'qt_smoke.py').read_text()
        self.assertIn('QT_STAGE program-qualified-sequential-require', smoke)
        self.assertIn("fresh_guard.choose_node(operation='python.require')", smoke)
        self.assertIn('require_workspace.publish_python(path=require_output)', smoke)

    def test_sequential_require_without_branch_is_qualified(self):
        g = ProgramGraph()
        def edit(action, **kwargs):
            return g.edit(g.revision, action, **kwargs)
        edit('add_function', id='fn', name='check')
        edit('set_return_type', function='fn', type='py:int')
        for name, operation, props in (
            ('entry2','python.entry',{}),
            ('require2','python.require',{}),
            ('return2','python.return_flow',{}),
            ('truth','python.literal',{'value':True}),
            ('number','python.literal',{'value':5}),
        ):
            shape=template_ports(operation)
            for side in shape:
                for port in shape[side]:
                    port['id']=name+'-'+port['name']
            edit('add_node', id=name, function='fn', operation=operation,
                 properties=props, inputs=shape['inputs'], outputs=shape['outputs'])
        for source, output, target, inp, relation in (
            ('entry2','then','require2','exec','control'),
            ('require2','then','return2','exec','control'),
            ('truth','value','require2','condition','data'),
            ('number','value','return2','value','data'),
        ):
            edit('connect', source=source, source_port=source+'-'+output,
                 target=target, target_port=target+'-'+inp, relation=relation)
        result=preview_python(g.state)
        self.assertIsNotNone(result.source,result.issues)
        self.assertEqual({x for x, _ in result.node_lines},
                         {n['id'] for n in g.state['nodes']})
        ns={}
        exec(result.source,ns)
        self.assertEqual(ns['check'](),5)
        edit('set_property',node='truth',key='value',value=False)
        bad=preview_python(g.state)
        self.assertIsNotNone(bad.source,bad.issues)
        ns={}
        exec(bad.source,ns)
        with self.assertRaises(ValueError):
            ns['check']()

    def test_guard_runtime_error_name_shadowing_is_refused(self):
        self.edit('add_parameter', function='func', id='shadow', name='ValueError', type='py:int')
        self.assertIn('shadowed',str(preview_python(self.graph.state).issues))


if __name__ == '__main__':
    unittest.main()
