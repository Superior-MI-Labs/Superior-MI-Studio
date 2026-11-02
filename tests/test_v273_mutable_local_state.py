"""Qualified, explicitly execution-ordered mutable slots; no CFG joins/loops."""
import tempfile
from pathlib import Path
import unittest
from studio_native.program_graph import ProgramGraph, template_ports, validate
from studio_native.python_lowering import preview_python, publish_python


class MutableLocalTests(unittest.TestCase):
    def setUp(self):
        self.g = ProgramGraph()
        self.edit('add_function', id='f', name='calculate')
        self.edit('set_return_type', function='f', type='py:int')

    def edit(self, action, **kw):
        return self.g.edit(self.g.revision, action, **kw)

    def node(self, ident, op, props=None):
        ports = template_ports(op)
        for side in ports:
            for p in ports[side]:
                p['id'] = f'{ident}-{side}-{p["name"]}'
        self.edit('add_node', id=ident, function='f', operation=op,
                  properties=props or {}, inputs=ports['inputs'], outputs=ports['outputs'])

    def wire(self, source, output, target, inp, relation='data'):
        self.edit('connect', source=source, source_port=f'{source}-outputs-{output}',
                  target=target, target_port=f'{target}-inputs-{inp}', relation=relation)

    def setup_sequence(self):
        self.node('entry', 'python.entry')
        self.node('local', 'python.local_int')
        self.node('read_before', 'python.read_int', {'local_id': 'local'})
        self.node('assign', 'python.assign_int', {'local_id': 'local'})
        self.node('read_after', 'python.read_int', {'local_id': 'local'})
        self.node('ret', 'python.return_flow')
        self.node('two', 'python.literal', {'value': 2})
        self.node('three', 'python.literal', {'value': 3})
        self.node('result', 'python.add')
        path = ['entry', 'local', 'read_before', 'assign', 'read_after', 'ret']
        for a, b in zip(path, path[1:]):
            self.wire(a, 'then', b, 'exec', 'control')
        self.wire('two', 'value', 'local', 'value')
        self.wire('three', 'value', 'assign', 'value')
        self.wire('read_before', 'value', 'result', 'left')
        self.wire('read_after', 'value', 'result', 'right')
        self.wire('result', 'result', 'ret', 'value')

    def test_execution_order_and_snapshot_values(self):
        self.setup_sequence()
        result = preview_python(self.g.state)
        self.assertIsNotNone(result.source, result.issues)
        scope = {}
        exec(result.source, scope)
        self.assertEqual(scope['calculate'](), 5)  # snapshot 2 + snapshot 3
        self.assertEqual(set(dict(result.node_lines)), {n['id'] for n in self.g.state['nodes']})
        self.assertLess(dict(result.node_lines)['local'], dict(result.node_lines)['assign'])
        self.assertLess(dict(result.node_lines)['assign'], dict(result.node_lines)['read_after'])
        self.assertEqual(result, preview_python(self.g.state))
        self.assertIn('_smi_slot_', result.source)

    def test_read_before_declaration_refused(self):
        self.setup_sequence()
        for edge in [e for e in self.g.state['edges'] if e['relation'] == 'control']:
            self.edit('disconnect', edge=edge['id'])
        path = ['entry', 'read_before', 'local', 'assign', 'read_after', 'ret']
        for a, b in zip(path, path[1:]):
            self.wire(a, 'then', b, 'exec', 'control')
        got = preview_python(self.g.state)
        self.assertIsNone(got.source)
        self.assertIn('before declaration', str(got.issues))

    def test_type_mismatch_refused(self):
        self.setup_sequence()
        self.edit('set_property', node='three', key='value', value=True)
        got = preview_python(self.g.state)
        self.assertIsNone(got.source)
        self.assertIn('local assignment expects py:int', str(got.issues))

    def test_stale_and_mistyped_target_refused(self):
        self.setup_sequence()
        self.edit('set_property', node='assign', key='local_id', value='missing')
        got = preview_python(self.g.state)
        self.assertIsNone(got.source)
        self.assertIn('absent or incompatible', str(got.issues))
        self.edit('set_property', node='assign', key='local_id', value='local')
        self.edit('set_property', node='assign', key='unexpected', value=1)
        self.assertIn('requires exactly one local_id', str(preview_python(self.g.state).issues))

    def test_wrong_branch_refused(self):
        self.setup_sequence()
        self.node('branch', 'python.branch')
        self.node('no', 'python.return_flow')
        self.node('condition', 'python.literal', {'value': True})
        edge = next(e for e in self.g.state['edges'] if e['source'] == 'local' and e['relation'] == 'control')
        self.edit('reconnect', edge=edge['id'], target='branch', target_port='branch-inputs-exec')
        self.wire('condition', 'value', 'branch', 'condition')
        self.wire('branch', 'true', 'read_before', 'exec', 'control')
        self.wire('branch', 'false', 'no', 'exec', 'control')
        # False branch tries to use the true branch read snapshot.
        self.wire('read_after', 'value', 'no', 'value')
        got = preview_python(self.g.state)
        self.assertIsNone(got.source)
        self.assertIn('before its execution', str(got.issues))

    def test_incomplete_save_undo_redo_and_publication(self):
        self.setup_sequence()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'mutable.smi-graph'
            destination = Path(tmp) / 'mutable.py'
            self.g.save_as(path)
            reopened = ProgramGraph.open(path)
            result = preview_python(reopened.state)
            self.assertIsNotNone(result.source, result.issues)
            receipt = publish_python(reopened, destination, expected_revision=reopened.revision)
            self.assertEqual(receipt.source_sha256, __import__('hashlib').sha256(destination.read_bytes()).hexdigest())
            self.assertEqual(set(dict(receipt.node_lines)), {n['id'] for n in reopened.state['nodes']})
            edge = next(e for e in reopened.state['edges'] if e['target'] == 'assign' and e['relation'] == 'data')
            reopened.edit(reopened.revision, 'disconnect', edge=edge['id'])
            validate(reopened.state)
            self.assertIsNone(preview_python(reopened.state).source)
            self.assertTrue(reopened.undo(reopened.revision))
            self.assertIsNotNone(preview_python(reopened.state).source)
            self.assertTrue(reopened.redo(reopened.revision))
            self.assertIsNone(preview_python(reopened.state).source)

    def test_branch_uses_prebranch_slot_but_reassigns_only_true_path(self):
        self.edit('add_parameter', function='f', id='which', name='choose', type='py:bool')
        self.node('entry', 'python.entry')
        self.node('local', 'python.local_int')
        self.node('branch', 'python.branch')
        self.node('assign', 'python.assign_int', {'local_id': 'local'})
        self.node('left_read', 'python.read_int', {'local_id': 'local'})
        self.node('right_read', 'python.read_int', {'local_id': 'local'})
        self.node('left_return', 'python.return_flow')
        self.node('right_return', 'python.return_flow')
        self.node('choose', 'python.parameter', {'parameter_id': 'which'})
        self.node('start', 'python.literal', {'value': 2})
        self.node('updated', 'python.literal', {'value': 9})
        for a, out, b in [('entry','then','local'), ('local','then','branch'),
                          ('branch','true','assign'), ('branch','false','right_read'),
                          ('assign','then','left_read'),('left_read','then','left_return'),
                          ('right_read','then','right_return')]:
            self.wire(a, out, b, 'exec', 'control')
        for a, out, b, inp in [('start','value','local','value'),
                                ('updated','value','assign','value'),
                                ('choose','value','branch','condition'),
                                ('left_read','value','left_return','value'),
                                ('right_read','value','right_return','value')]:
            self.wire(a,out,b,inp)
        result=preview_python(self.g.state)
        self.assertIsNotNone(result.source,result.issues)
        space={}
        exec(result.source,space)
        self.assertEqual(space['calculate'](True),9)
        self.assertEqual(space['calculate'](False),2)
        self.assertEqual(set(dict(result.node_lines)),{n['id'] for n in self.g.state['nodes']})

    def test_stateful_function_is_not_pure_callable(self):
        self.setup_sequence()
        self.edit('add_function', id='caller', name='caller')
        self.edit('set_return_type', function='caller', type='py:int')
        self.edit('add_node', id='call', function='caller', operation='python.call',
                  properties={'callee_id':'f'},inputs=[],
                  outputs=[{'name':'result','id':'call-result','type':'py:int'}])
        self.edit('add_node', id='call_ret', function='caller',operation='python.return',
                  properties={},inputs=[{'name':'value','id':'call_ret-value','type':'py:int'}],outputs=[])
        self.edit('connect',source='call',source_port='call-result',target='call_ret',
                  target_port='call_ret-value',relation='data')
        result=preview_python(self.g.state)
        self.assertIsNone(result.source)
        self.assertIn('effectful function calls',str(result.issues))

    def test_bool_local_and_snapshot(self):
        self.edit('set_return_type', function='f', type='py:bool')
        self.node('entry', 'python.entry')
        self.node('local', 'python.local_bool')
        self.node('assign', 'python.assign_bool', {'local_id': 'local'})
        self.node('read', 'python.read_bool', {'local_id': 'local'})
        self.node('return', 'python.return_flow')
        self.node('before', 'python.literal', {'value': False})
        self.node('after', 'python.literal', {'value': True})
        for a, b in zip(['entry', 'local', 'assign', 'read'], ['local', 'assign', 'read', 'return']):
            self.wire(a, 'then', b, 'exec', 'control')
        self.wire('before', 'value', 'local', 'value')
        self.wire('after', 'value', 'assign', 'value')
        self.wire('read', 'value', 'return', 'value')
        result=preview_python(self.g.state)
        self.assertIsNotNone(result.source, result.issues)
        space={}
        exec(result.source, space)
        self.assertIs(space['calculate'](), True)


if __name__ == '__main__':
    unittest.main()
