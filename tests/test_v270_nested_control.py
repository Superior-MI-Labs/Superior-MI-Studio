"""Bounded structured execution tree, stable identities, and refusal contracts."""
import ast
import copy
from pathlib import Path
import tempfile
import unittest

from studio_native.program_graph import ProgramGraph, template_ports, validate, GraphConflict
from studio_native.python_lowering import preview_python, publish_python


class NestedControlTests(unittest.TestCase):
    def setUp(self):
        self.graph = ProgramGraph()
        self.edit('add_function', id='func', name='choose')
        self.edit('set_return_type', function='func', type='py:int')
        for label in ('x', 'limit', 'offset'):
            self.edit('add_parameter', function='func', id='p-'+label, name=label, type='py:int')
        for node, operation, props in (
            ('entry','python.entry', {}),
            ('outer','python.branch', {}),
            ('inner','python.branch', {}),
            ('a','python.return_flow', {}),
            ('b','python.return_flow', {}),
            ('c','python.return_flow', {}),
            ('x','python.parameter', {'parameter_id':'p-x'}),
            ('limit','python.parameter', {'parameter_id':'p-limit'}),
            ('offset','python.parameter', {'parameter_id':'p-offset'}),
            ('outer_check','python.less_than', {}),
            ('inner_check','python.less_than', {}),
            ('one','python.literal', {'value':1}),
            ('two','python.literal', {'value':2}),
            ('plus1','python.add', {}),
            ('plus2','python.add', {}),
        ):
            self.node(node, operation, props)
        for source, output, target, pin in (
            ('entry','then','outer','exec'),
            ('outer','true','inner','exec'),
            ('outer','false','c','exec'),
            ('inner','true','a','exec'),
            ('inner','false','b','exec'),
        ):
            self.wire(source, output, target, pin, 'control')
        for source, output, target, pin in (
            ('x','value','outer_check','left'),
            ('limit','value','outer_check','right'),
            ('outer_check','result','outer','condition'),
            ('x','value','inner_check','left'),
            ('offset','value','inner_check','right'),
            ('inner_check','result','inner','condition'),
            ('x','value','plus1','left'),
            ('one','value','plus1','right'),
            ('x','value','plus2','left'),
            ('two','value','plus2','right'),
            ('plus1','result','a','value'),
            ('plus2','result','b','value'),
            ('x','value','c','value'),
        ):
            self.wire(source, output, target, pin)

    def edit(self, action, **kwargs):
        return self.graph.edit(self.graph.revision, action, **kwargs)

    def node(self, node_id, operation, properties=None):
        ports = template_ports(operation)
        for side in ports:
            for port in ports[side]:
                port['id'] = node_id+'-'+port['name']
        self.edit('add_node', id=node_id, function='func', operation=operation,
                  inputs=ports['inputs'], outputs=ports['outputs'], properties=properties or {})

    def wire(self, source, output, target, pin, relation='data'):
        self.edit('connect', source=source, source_port=source+'-'+output,
                  target=target, target_port=target+'-'+pin, relation=relation)

    def preview(self):
        result = preview_python(self.graph.state)
        self.assertFalse(result.issues, result.issues)
        self.assertIsNotNone(result.source)
        return result

    def test_nested_true_branch_emits_real_lazily_executed_if_else(self):
        result = self.preview()
        tree = ast.parse(result.source)
        outer = next(stmt for stmt in tree.body[0].body if isinstance(stmt,ast.If))
        inner = next(stmt for stmt in outer.body if isinstance(stmt,ast.If))
        self.assertEqual(len([n for n in ast.walk(tree) if isinstance(n,ast.If)]),2)
        self.assertTrue(any(isinstance(x,ast.Return) for x in inner.body))
        self.assertTrue(any(isinstance(x,ast.Return) for x in inner.orelse))
        namespace = {}
        exec(result.source,namespace)
        choose = namespace['choose']
        self.assertEqual(choose(1,10,5),2)
        self.assertEqual(choose(7,10,5),9)
        self.assertEqual(choose(13,10,5),13)

    def test_node_source_lines_are_correct_for_nested_branches(self):
        result = self.preview()
        lines = dict(result.node_lines)
        source_lines = result.source.splitlines()
        self.assertEqual(len(lines),len(self.graph.state['nodes']))
        self.assertEqual(len(set(lines)),len(lines))
        self.assertIn('if ',source_lines[lines['outer']-1])
        self.assertIn('if ',source_lines[lines['inner']-1])
        self.assertLess(lines['outer'],lines['inner'])
        for node in ('a','b','c'):
            self.assertIn('return ',source_lines[lines[node]-1])
        self.assertLess(lines['a'],lines['b'])
        self.assertLess(lines['b'],lines['c'])

    def test_nested_branch_on_false_side_has_correct_identity_and_behavior(self):
        # Rewire the same graph so inner becomes the false child of outer;
        # both path mapping and expression dominance must survive.
        for e in list(self.graph.state['edges']):
            if e['relation']=='control' and e['source']=='outer':
                self.edit('disconnect',edge=e['id'])
        self.wire('outer','true','c','exec','control')
        self.wire('outer','false','inner','exec','control')
        result=self.preview()
        namespace={}
        exec(result.source,namespace)
        choose=namespace['choose']
        self.assertEqual(choose(1,10,5),1)
        self.assertEqual(choose(13,10,20),14)
        self.assertEqual(choose(22,10,20),24)
        lines=dict(result.node_lines)
        self.assertLess(lines['c'],lines['inner'])
        self.assertLess(lines['inner'],lines['a'])

    def test_shared_data_producers_are_only_evaluated_as_needed(self):
        result = self.preview()
        tree = ast.parse(result.source)
        outer = next(stmt for stmt in tree.body[0].body if isinstance(stmt,ast.If))
        # plus1/plus2 are entirely inside the nested conditional, not
        # eagerly executed before the outer condition.
        before=tree.body[0].body[:tree.body[0].body.index(outer)]
        self.assertFalse(any(isinstance(x,ast.Add) for stmt in before for x in ast.walk(stmt)))
        self.assertEqual([node for node,_ in result.node_lines].count('x'),1)

    def test_both_arms_can_contain_nested_branches_with_exact_source_mapping(self):
        old=next(e for e in self.graph.state['edges'] if e['source']=='outer' and e['target']=='c')
        self.edit('disconnect',edge=old['id'])
        self.node('right_branch','python.branch')
        self.node('d','python.return_flow')
        self.wire('outer','false','right_branch','exec','control')
        self.wire('right_branch','true','c','exec','control')
        self.wire('right_branch','false','d','exec','control')
        self.wire('inner_check','result','right_branch','condition')
        self.wire('x','value','d','value')
        result=self.preview()
        lines=dict(result.node_lines)
        self.assertEqual(len(lines),len(self.graph.state['nodes']))
        self.assertEqual(len([n for n in ast.walk(ast.parse(result.source)) if isinstance(n,ast.If)]),3)
        self.assertLess(lines['outer'],lines['inner'])
        self.assertLess(lines['b'],lines['right_branch'])
        self.assertLess(lines['right_branch'],lines['c'])
        self.assertLess(lines['c'],lines['d'])
        namespace={}
        exec(result.source,namespace)
        self.assertEqual(namespace['choose'](2,10,5),3)
        self.assertEqual(namespace['choose'](12,10,20),12)
        self.assertEqual(namespace['choose'](12,10,5),12)

    def test_multiple_parent_control_paths_cannot_become_executable(self):
        state=self.graph.state
        edge=next(e for e in state['edges'] if e['source']=='inner' and e['target']=='b')
        edge['target']='c'
        edge['target_port']='c-exec'
        self.assertIsNone(preview_python(state).source)

    def test_data_cycle_is_refused_even_inside_nested_branch(self):
        state=self.graph.state
        edge=next(e for e in state['edges'] if e['source']=='one' and e['target']=='plus1')
        edge['source']='plus1'
        edge['source_port']='plus1-result'
        self.assertIn('cyclic',str(preview_python(state).issues))

    def test_layout_changes_do_not_change_semantics_or_source_map(self):
        original=self.preview()
        self.edit('move_node',node='inner',x=1000,y=-800)
        self.assertEqual(original,self.preview())

    def test_incomplete_nested_branch_can_save_but_cannot_publish(self):
        edge=next(e for e in self.graph.state['edges'] if e['source']=='inner' and e['target']=='b')
        self.edit('disconnect',edge=edge['id'])
        validate(self.graph.state)
        with tempfile.TemporaryDirectory() as tmp:
            graph_path=Path(tmp)/'incomplete.smi-graph'
            self.graph.save(graph_path)
            self.assertIsNone(preview_python(ProgramGraph.open(graph_path).state).source)
            with self.assertRaises(GraphConflict):
                publish_python(self.graph,Path(tmp)/'out.py',expected_revision=self.graph.revision)
            self.assertFalse((Path(tmp)/'out.py').exists())

    def test_missing_leaf_return_refused(self):
        self.edit('remove_node',node='c')
        self.assertIsNone(preview_python(self.graph.state).source)

    def test_orphan_pure_operation_refused(self):
        self.node('unused','python.literal',{'value':999})
        self.assertIn('orphan',str(preview_python(self.graph.state).issues))

    def test_unsupported_execution_join_or_cycle_refused(self):
        state=self.graph.state
        control=next(e for e in state['edges'] if e['source']=='inner' and e['target']=='a')
        control['target']='outer'
        control['target_port']='outer-exec'
        self.assertIsNone(preview_python(state).source)

    def test_nested_execution_node_is_purely_structural_not_a_side_effect(self):
        self.edit('set_property',node='inner',key='unexpected',value=True)
        self.assertIsNone(preview_python(self.graph.state).source)

    def test_explicit_save_reopen_and_publication_retains_graph_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            saved=Path(tmp)/'tree.smi-graph'
            out=Path(tmp)/'tree.py'
            self.graph.save(saved)
            original=copy.deepcopy(self.graph.state)
            reopened=ProgramGraph.open(saved)
            published=publish_python(reopened,out,expected_revision=reopened.revision)
            self.assertEqual(original,reopened.state)
            self.assertEqual(published.node_lines,self.preview().node_lines)
            self.assertEqual(out.read_text(),self.preview().source)

    def test_nested_branch_data_type_refusal(self):
        self.edit('replace_input',source='x',source_port='x-value',target='inner',target_port='inner-condition')
        self.assertIsNone(preview_python(self.graph.state).source)


if __name__ == '__main__':
    unittest.main()
