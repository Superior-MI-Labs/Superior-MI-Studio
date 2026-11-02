"""Bounded structured Repeat: real loop-carried slots, no arbitrary CFG shortcuts."""
import tempfile
from pathlib import Path
import unittest
from studio_native.program_graph import ProgramGraph, template_ports, validate
from studio_native.python_lowering import preview_python, publish_python


class RepeatQualificationTests(unittest.TestCase):
    def setUp(self):
        self.graph = ProgramGraph()
        self.edit('add_function', id='f', name='count_up')
        self.edit('set_return_type', function='f', type='py:int')
        self.edit('add_parameter', function='f', id='iterations', name='n', type='py:int')

    def edit(self, action, **params):
        return self.graph.edit(self.graph.revision, action, **params)

    def node(self, name, operation, properties=None):
        ports = template_ports(operation)
        for side, members in ports.items():
            for port in members:
                port['id'] = f'{name}-{side}-{port["name"]}'
        self.edit('add_node', id=name, function='f', operation=operation,
                  properties=properties or {}, inputs=ports['inputs'], outputs=ports['outputs'])

    def wire(self, source, port, target, input_port, relation='data'):
        self.edit('connect', source=source, source_port=f'{source}-outputs-{port}',
                  target=target, target_port=f'{target}-inputs-{input_port}', relation=relation)

    def standard_graph(self):
        for name, op, properties in [
            ('entry', 'python.entry', {}), ('initial', 'python.literal', {'value': 0}),
            ('one', 'python.literal', {'value': 1}),
            ('count', 'python.parameter', {'parameter_id': 'iterations'}),
            ('slot', 'python.local_int', {}), ('repeat', 'python.repeat_int', {}),
            ('snapshot', 'python.read_int', {'local_id': 'slot'}),
            ('increment', 'python.add', {}),
            ('assign', 'python.assign_int', {'local_id': 'slot'}),
            ('end', 'python.repeat_end', {}),
            ('final_snapshot', 'python.read_int', {'local_id': 'slot'}),
            ('ret', 'python.return_flow', {}),
        ]:
            self.node(name, op, properties)
        for a, output, b in [
            ('entry','then','slot'),('slot','then','repeat'),
            ('repeat','body','snapshot'),('snapshot','then','assign'),
            ('assign','then','end'),('repeat','after','final_snapshot'),
            ('final_snapshot','then','ret')
        ]:
            self.wire(a, output, b, 'exec', 'control')
        for a, out, b, inp in [
            ('initial','value','slot','value'),('count','value','repeat','count'),
            ('snapshot','value','increment','left'),('one','value','increment','right'),
            ('increment','result','assign','value'),('final_snapshot','value','ret','value')
        ]:
            self.wire(a, out, b, inp)

    def test_repeated_mutation_behavior_and_mapping(self):
        self.standard_graph()
        got = preview_python(self.graph.state)
        self.assertIsNotNone(got.source, got.issues)
        scope = {}
        exec(got.source, scope)
        self.assertEqual([scope['count_up'](n) for n in (0, 1, 5, 100)], [0, 1, 5, 100])
        self.assertIn('for _smi_repeat_index_', got.source)
        self.assertEqual(set(dict(got.node_lines)), {n['id'] for n in self.graph.state['nodes']})
        self.assertEqual(len(got.node_lines), len(self.graph.state['nodes']))
        self.assertEqual(preview_python(self.graph.state), got)
        for n in (-1, 10001):
            with self.assertRaisesRegex(ValueError, 'Repeat count outside'):
                scope['count_up'](n)

    def test_persistence_undo_and_explicit_publication(self):
        self.standard_graph()
        with tempfile.TemporaryDirectory() as tmp:
            saved=Path(tmp)/'repeat.smi-graph'
            output=Path(tmp)/'repeat.py'
            self.graph.save_as(saved)
            reopened=ProgramGraph.open(saved)
            result=preview_python(reopened.state)
            self.assertIsNotNone(result.source, result.issues)
            receipt=publish_python(reopened,output,expected_revision=reopened.revision)
            self.assertEqual(dict(receipt.node_lines)['repeat'],dict(result.node_lines)['repeat'])
            self.assertEqual(output.read_text(),result.source)
            edge=next(e for e in reopened.state['edges'] if e['target']=='end')
            reopened.edit(reopened.revision,'disconnect',edge=edge['id'])
            validate(reopened.state)  # incomplete graph is still a valid saved document
            self.assertIsNone(preview_python(reopened.state).source)
            self.assertTrue(reopened.undo(reopened.revision))
            self.assertIsNotNone(preview_python(reopened.state).source)
            self.assertTrue(reopened.redo(reopened.revision))
            self.assertIsNone(preview_python(reopened.state).source)

    def test_after_path_cannot_use_iteration_snapshot(self):
        self.standard_graph()
        final_edge=next(e for e in self.graph.state['edges'] if e['target']=='ret' and e['relation']=='data')
        self.edit('reconnect',edge=final_edge['id'],source='snapshot',source_port='snapshot-outputs-value')
        got=preview_python(self.graph.state)
        self.assertIsNone(got.source)
        self.assertIn('before its execution path',str(got.issues))

    def test_unpaired_end_is_rejected(self):
        self.standard_graph()
        self.edit('remove_node',node='end')
        self.assertIsNone(preview_python(self.graph.state).source)

    def test_bad_count_type_and_wrong_ports(self):
        self.standard_graph()
        self.node('bool_source', 'python.literal', {'value': True})
        count_edge=next(e for e in self.graph.state['edges'] if e['source']=='count')
        self.edit('reconnect',edge=count_edge['id'],source='bool_source',source_port='bool_source-outputs-value')
        got=preview_python(self.graph.state)
        self.assertIsNone(got.source)
        self.assertIn('Repeat count expects py:int',str(got.issues))

    def test_branch_inside_body_refused(self):
        self.standard_graph()
        self.node('branch', 'python.branch')
        self.node('wrong_return','python.return_flow')
        self.node('condition','python.literal',{'value': True})
        edge=next(e for e in self.graph.state['edges'] if e['source']=='repeat' and e['relation']=='control' and e['target']=='snapshot')
        self.edit('reconnect',edge=edge['id'],target='branch',target_port='branch-inputs-exec')
        self.wire('condition','value','branch','condition')
        self.wire('branch','true','snapshot','exec','control')
        self.wire('branch','false','wrong_return','exec','control')
        self.wire('initial','value','wrong_return','value')
        got=preview_python(self.graph.state)
        self.assertIsNone(got.source)
        self.assertIn('Branch inside Repeat',str(got.issues))


    def test_guard_effect_is_repeated_and_skipped_at_zero(self):
        self.standard_graph()
        self.node('guard', 'python.require')
        self.node('allowed', 'python.literal', {'value': False})
        existing = next(e for e in self.graph.state['edges'] if
                        e['source'] == 'repeat' and e['target'] == 'snapshot' and e['relation'] == 'control')
        self.edit('reconnect', edge=existing['id'], target='guard', target_port='guard-inputs-exec')
        self.wire('allowed', 'value', 'guard', 'condition')
        self.wire('guard', 'then', 'snapshot', 'exec', 'control')
        result = preview_python(self.graph.state)
        self.assertIsNotNone(result.source, result.issues)
        env={}
        exec(result.source, env)
        self.assertEqual(env['count_up'](0), 0)  # body not executed
        with self.assertRaisesRegex(ValueError, 'Require failed'):
            env['count_up'](1)

    def test_pure_call_into_repeat_effect_is_refused(self):
        self.standard_graph()
        self.edit('add_function', id='caller', name='call_repeat')
        self.edit('set_return_type', function='caller', type='py:int')
        self.edit('add_node', id='call', function='caller', operation='python.call',
                  properties={'callee_id':'f'},
                  inputs=[{'name':'n','type':'py:int'}], outputs=[{'name':'result','type':'py:int'}])
        result=preview_python(self.graph.state)
        self.assertIsNone(result.source)
        self.assertIn('effectful function calls require explicit execution semantics', str(result.issues))

    def test_runtime_limit_and_shadowed_range(self):
        self.standard_graph()
        env={}
        result=preview_python(self.graph.state)
        exec(result.source, env)
        self.assertEqual(env['count_up'](10000), 10000)
        self.edit('rename_function', function='f', name='range')
        self.assertIsNone(preview_python(self.graph.state).source)
        self.assertIn('range or ValueError name is shadowed', str(preview_python(self.graph.state).issues))


if __name__ == '__main__':
    unittest.main()
