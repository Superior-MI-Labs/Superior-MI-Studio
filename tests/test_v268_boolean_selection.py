"""Pure graph-owned Boolean and eager selection qualification, no execution branching."""
import ast
from pathlib import Path
import tempfile
import unittest

from studio_native.program_graph import ProgramGraph, template_ports, validate
from studio_native.python_lowering import preview_python, publish_python
from studio_native.program_graph import GraphConflict


class EagerValueSelectionTests(unittest.TestCase):
    def setUp(self):
        self.graph = ProgramGraph()
        self.edit('add_function', id='fn-choose', name='choose')
        self.edit('add_parameter', function='fn-choose', id='p-x', name='x', type='py:int')
        self.edit('add_parameter', function='fn-choose', id='p-limit', name='limit', type='py:int')
        self.edit('set_return_type', function='fn-choose', type='py:int')
        self.node('arg', 'python.parameter', {'parameter_id': 'p-x'})
        self.node('bound', 'python.parameter', {'parameter_id': 'p-limit'})
        self.node('condition', 'python.less_than')
        self.node('one', 'python.literal', {'value': 1})
        self.node('sum', 'python.add')
        self.node('select', 'python.select_int')
        self.node('ret', 'python.return')
        self.wire('arg', 'value', 'condition', 'left')
        self.wire('bound', 'value', 'condition', 'right')
        self.wire('arg', 'value', 'sum', 'left')
        self.wire('one', 'value', 'sum', 'right')
        self.wire('condition', 'result', 'select', 'condition')
        self.wire('sum', 'result', 'select', 'true_value')
        self.wire('arg', 'value', 'select', 'false_value')
        self.wire('select', 'result', 'ret', 'value')

    def edit(self, action, **options):
        return self.graph.edit(self.graph.revision, action, **options)

    def node(self, node_id, op, properties=None, function='fn-choose'):
        ports = template_ports(op)
        for direction in ports:
            for port in ports[direction]:
                port['id'] = f'{node_id}-{port["name"]}'
        self.edit('add_node', id=node_id, function=function, operation=op,
                  inputs=ports['inputs'], outputs=ports['outputs'],
                  properties=properties or {})

    def wire(self, source, source_port, target, target_port):
        self.edit('connect', source=source, source_port=f'{source}-{source_port}',
                  target=target, target_port=f'{target}-{target_port}')

    def preview(self):
        result = preview_python(self.graph.state)
        self.assertFalse(result.issues, result.issues)
        self.assertIsNotNone(result.source)
        return result

    def test_select_integer_behavior_and_eager_bound_producers(self):
        preview = self.preview()
        tree = ast.parse(preview.source)
        nodes = tree.body[0].body
        selections = [n for n in nodes if isinstance(n, ast.Assign) and
                      isinstance(n.value, ast.IfExp)]
        self.assertEqual(len(selections), 1)
        self.assertEqual(len(nodes), 7)  # six values, then Return
        self.assertTrue(all(isinstance(node, ast.Assign) for node in nodes[:-1]))
        namespace = {}
        exec(preview.source, namespace)
        self.assertEqual(namespace['choose'](3, 10), 4)
        self.assertEqual(namespace['choose'](10, 10), 10)
        self.assertEqual(namespace['choose'](-4, 2), -3)
        self.assertEqual(preview.source, preview_python(self.graph.state).source)
        self.assertEqual(len(preview.node_lines), len(self.graph.state['nodes']))

    def test_equality_and_not_with_boolean_result(self):
        self.edit('remove_node', node='condition')
        self.node('equal', 'python.equal_int')
        self.wire('arg', 'value', 'equal', 'left')
        self.wire('bound', 'value', 'equal', 'right')
        self.edit('remove_node', node='select')
        self.edit('remove_node', node='sum')
        self.edit('remove_node', node='one')
        self.node('not', 'python.not')
        self.wire('equal', 'result', 'not', 'value')
        self.edit('set_return_type', function='fn-choose', type='py:bool')
        self.wire('not', 'result', 'ret', 'value')
        result = self.preview()
        namespace = {}
        exec(result.source, namespace)
        self.assertIs(namespace['choose'](4, 4), False)
        self.assertIs(namespace['choose'](4, 5), True)

    def test_boolean_selection_and_type_preservation(self):
        self.edit('remove_node', node='select')
        self.edit('remove_node', node='sum')
        self.edit('remove_node', node='one')
        self.node('truth', 'python.literal', {'value': True})
        self.node('falsity', 'python.literal', {'value': False})
        self.node('choice', 'python.select_bool')
        self.wire('condition', 'result', 'choice', 'condition')
        self.wire('truth', 'value', 'choice', 'true_value')
        self.wire('falsity', 'value', 'choice', 'false_value')
        self.edit('set_return_type', function='fn-choose', type='py:bool')
        self.wire('choice', 'result', 'ret', 'value')
        result = self.preview()
        namespace = {}
        exec(result.source, namespace)
        self.assertIs(namespace['choose'](1, 2), True)
        self.assertIs(namespace['choose'](3, 2), False)

    def test_disconnected_select_saves_but_refuses_compilation(self):
        selected = next(e for e in self.graph.state['edges'] if e['target']=='select' and
                        e['target_port']=='select-false_value')
        self.edit('disconnect', edge=selected['id'])
        validate(self.graph.state)
        with tempfile.TemporaryDirectory() as directory:
            self.graph.save(Path(directory)/'incomplete.smi-graph')
            restored=ProgramGraph.open(self.graph.path)
            self.assertEqual(self.graph.state, restored.state)
            preview=preview_python(restored.state)
            self.assertIsNone(preview.source)
            self.assertIn('missing input false_value', preview.issues[0])
            with self.assertRaises(GraphConflict):
                publish_python(restored,Path(directory)/'out.py',expected_revision=restored.revision)
            self.assertFalse((Path(directory)/'out.py').exists())

    def test_selection_refuses_wrong_type_and_extraneous_properties(self):
        self.edit('replace_input', source='sum', source_port='sum-result',
                  target='select', target_port='select-false_value')
        self.edit('replace_input', source='condition', source_port='condition-result',
                  target='select', target_port='select-true_value')
        self.assertIn('expects integer py:int', str(preview_python(self.graph.state).issues))
        self.edit('replace_input', source='sum', source_port='sum-result',
                  target='select', target_port='select-true_value')
        self.edit('set_property', node='select', key='python_expression', value='__import__("os")')
        self.assertIn('unknown value-selection properties', str(preview_python(self.graph.state).issues))

    def test_port_signature_and_version_rejections(self):
        state=self.graph.state
        next(n for n in state['nodes'] if n['id']=='select')['ports']['inputs'][0]['name']='test'
        self.assertIn('signature', str(preview_python(state).issues))
        state=self.graph.state
        next(n for n in state['nodes'] if n['id']=='select')['operation_version']=2
        self.assertIn('unsupported operation version', str(preview_python(state).issues))

    def test_geometry_does_not_change_compiled_program_or_source_map(self):
        initial=self.preview()
        self.edit('move_node', node='select', x=-800, y=450)
        self.edit('move_node', node='arg', x=890, y=-120)
        self.assertEqual(self.preview(), initial)

    def test_unknown_execution_node_cannot_be_silently_lowered(self):
        state=self.graph.state
        select=next(n for n in state['nodes'] if n['id']=='select')
        select['operation']='python.execute_arbitrary'
        self.assertIsNone(preview_python(state).source)
        self.assertIn('not qualified', str(preview_python(state).issues))

    def test_saved_graph_publishes_and_reopens_with_same_graph_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            self.graph.save(root/'choose.smi-graph')
            preview=self.preview()
            receipt=publish_python(self.graph,root/'choose.py',expected_revision=self.graph.revision)
            self.assertEqual(receipt.node_lines,preview.node_lines)
            self.assertEqual((root/'choose.py').read_text(),preview.source)
            restored=ProgramGraph.open(self.graph.path)
            self.assertEqual(restored.state['id'],self.graph.state['id'])
            self.assertEqual(preview_python(restored.state).source,preview.source)
            self.assertFalse(restored.dirty)
            self.assertFalse((root/'choose.py').is_symlink())


if __name__ == '__main__':
    unittest.main()
