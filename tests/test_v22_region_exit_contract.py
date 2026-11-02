"""v2.2: language-neutral composite interfaces and Python return semantics.

These are source/contract tests, not evidence of native Qt rendering.
"""
import copy
import tempfile
import unittest
from pathlib import Path

from studio_native.python_graph import PythonDocument
from studio_native.semantic_contract import ContractError, describe_graph
from studio_native.boundary_edit import terminal_return_target, BoundaryEditError


class RegionExitContractTests(unittest.TestCase):
    def graph(self, source):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'test.py'
            path.write_text(source,encoding='utf-8')
            doc=PythonDocument(path)
            graph=doc.composite_file_graph(expanded=set(doc.scopes)-{'module'})
            return graph,describe_graph(graph,origin='source')

    def function(self, graph, name):
        return next(node for node in graph['nodes']
                    if node.get('source_scope') and node['source_kind']=='function'
                    and node['title']==name.upper())

    def test_single_terminal_return_is_one_exit_and_one_value_port(self):
        graph,contract=self.graph('def choose(a):\n    return a\n')
        fn=self.function(graph,'choose')
        i=next(n.interface for n in contract.nodes if n.id==fn['id'])
        self.assertEqual(i.category,'function')
        self.assertEqual(len(i.exits),1)
        self.assertEqual(i.exits[0].kind,'return')
        self.assertIsNone(i.exits[0].control_port)
        self.assertEqual(len(i.exits[0].sites),1)
        self.assertIn(i.exits[0].value_port,i.outputs)
        folded=[n for n in graph['nodes'] if n.get('terminal_boundary_owner')]
        self.assertEqual(len(folded),1)
        self.assertEqual(folded[0]['exit_target_owner'],fn['id'])
        self.assertEqual(terminal_return_target(graph,fn['id'],i.exits[0].value_port)[0],folded[0]['id'])

    def test_early_and_terminal_returns_share_exit_but_are_distinct_sites(self):
        graph,contract=self.graph('def f(a):\n    if a > 0:\n        return a\n    return 0\n')
        fn=self.function(graph,'f')
        i=next(n.interface for n in contract.nodes if n.id==fn['id'])
        self.assertEqual(len(i.exits[0].sites),2)
        self.assertEqual({n['id'] for n in graph['nodes'] if n.get('exit_target_owner')==fn['id']},set(i.exits[0].sites))
        with self.assertRaises(BoundaryEditError):
            terminal_return_target(graph,fn['id'],i.exits[0].value_port)
        self.assertFalse(any(n.get('terminal_boundary_owner') for n in graph['nodes']))

    def test_nested_if_no_return_port_and_true_false_control_outputs(self):
        graph,contract=self.graph('def f(a):\n    if a:\n        return 1\n    return 2\n')
        branches=[n for n in contract.nodes if n.interface and n.interface.category=='conditional']
        self.assertEqual(len(branches),1)
        branch=branches[0]
        self.assertEqual({e.kind for e in branch.interface.exits},{'true','false'})
        self.assertTrue(all(e.control_port in branch.interface.outputs for e in branch.interface.exits))
        self.assertTrue(all(next(p for p in branch.ports if p.id==e.control_port).type_id=='execution'
                            for e in branch.interface.exits))
        self.assertNotIn('return',[p.label for p in branch.ports])

    def test_loop_body_and_normal_completion_are_distinct(self):
        graph,contract=self.graph('def f(n):\n    while n:\n        n -= 1\n    return n\n')
        loops=[n for n in contract.nodes if n.interface and n.interface.category=='loop']
        self.assertEqual(len(loops),1)
        self.assertEqual({e.kind for e in loops[0].interface.exits},{'body','normal'})
        self.assertTrue(all(e.control_port for e in loops[0].interface.exits))

    def test_return_inside_loop_exits_function_not_loop(self):
        graph,contract=self.graph('def f(n):\n    while n:\n        if n == 1:\n            return n\n        n -= 1\n    return 0\n')
        fn=self.function(graph,'f')
        exits=next(n.interface.exits for n in contract.nodes if n.id==fn['id'])
        self.assertEqual(len(exits[0].sites),2)
        self.assertTrue(all(next(n for n in graph['nodes'] if n['id']==s)['exit_target_owner']==fn['id']
                            for s in exits[0].sites))
        loop=next(n for n in contract.nodes if n.interface and n.interface.category=='loop')
        self.assertFalse(any(e.kind=='return' for e in loop.interface.exits))

    def test_nested_functions_route_to_correct_owner(self):
        graph,contract=self.graph('def outer(a):\n    def inner(b):\n        return b\n    return a\n')
        functions=[n for n in contract.nodes if n.interface and n.interface.category=='function']
        self.assertEqual(len(functions),2)
        sites=[(n.id,n.interface.exits[0].sites) for n in functions]
        self.assertEqual(sum(len(site) for _,site in sites),2)
        self.assertEqual(len({sid for _,ss in sites for sid in ss}),2)

    def test_no_return_has_empty_return_sites(self):
        graph,contract=self.graph('def f(x):\n    y = x + 1\n')
        fn=self.function(graph,'f')
        i=next(n.interface for n in contract.nodes if n.id==fn['id'])
        self.assertEqual(i.exits[0].sites,())

    def test_bare_return_does_not_require_a_value_expression(self):
        graph,contract=self.graph('def f():\n    return\n')
        fn=self.function(graph,'f')
        site=next(n for n in graph['nodes'] if n.get('exit_target_owner')==fn['id'])
        self.assertFalse(any(p['type']!='execution' for p in site['draft_ports']['inputs']))

    def test_contract_does_not_add_programming_nodes_or_edges(self):
        graph,contract=self.graph('def f(n):\n    if n > 1:\n        return n\n    return 0\n')
        self.assertEqual({n['id'] for n in graph['nodes']},{n.id for n in contract.nodes})
        self.assertEqual({e['id'] for e in graph['edges']},{e.id for e in contract.edges})
        self.assertTrue(all(not e.id.startswith('exit:') for e in contract.edges))

    def test_contract_rejects_unknown_return_value_port(self):
        graph,_=self.graph('def f(a):\n    return a\n')
        broken=copy.deepcopy(graph)
        self.function(broken,'f')['graph_interface']['exits'][0]['value_port']='invented'
        with self.assertRaises(ContractError):describe_graph(broken,origin='source')

    def test_contract_rejects_fictitious_exit_site(self):
        graph,_=self.graph('def f(a):\n    return a\n')
        broken=copy.deepcopy(graph)
        self.function(broken,'f')['graph_interface']['exits'][0]['sites'].append('invented-return')
        with self.assertRaises(ContractError):describe_graph(broken,origin='source')

    def test_contract_rejects_wrong_control_type(self):
        graph,_=self.graph('def f(a):\n    if a:\n        return 1\n    return 2\n')
        broken=copy.deepcopy(graph)
        conditional=next(n for n in broken['nodes'] if n.get('graph_interface',{}).get('category')=='conditional')
        control=conditional['graph_interface']['exits'][0]
        control['control_port']=self.function(broken,'f')['draft_ports']['outputs'][0]['id']
        with self.assertRaises(ContractError):describe_graph(broken,origin='source')

    def test_exit_site_cannot_be_attached_to_wrong_function(self):
        graph,_=self.graph('def left(a):\n    return a\n\ndef right(b):\n    return b\n')
        broken=copy.deepcopy(graph)
        left=self.function(broken,'left')
        right=self.function(broken,'right')
        left['graph_interface']['exits'][0]['sites']=list(right['graph_interface']['exits'][0]['sites'])
        right['graph_interface']['exits'][0]['sites']=[]
        with self.assertRaises(ContractError):describe_graph(broken,origin='source')

    def test_exit_control_anchor_is_stable_and_not_forged_source_port(self):
        graph,contract=self.graph('def f(x):\n    return x\n')
        desc=next(n for n in contract.nodes if n.interface and n.interface.category=='function')
        exit_spec=desc.interface.exits[0]
        self.assertEqual(exit_spec.control_anchor_id,exit_spec.id+':control')
        self.assertNotIn(exit_spec.control_anchor_id,desc.interface.outputs)
        self.assertIn(exit_spec.value_port,desc.interface.outputs)
        self.assertEqual(len(graph['nodes']),len(contract.nodes))

    def test_conditional_exit_control_uses_existing_source_port(self):
        graph,contract=self.graph('def f(a):\n    if a:\n        return a\n    return 0\n')
        branch=next(n for n in contract.nodes if n.interface and n.interface.category=='conditional')
        self.assertTrue(all(x.control_anchor_id==x.control_port for x in branch.interface.exits))
        self.assertTrue(all(x.value_port is None for x in branch.interface.exits))

    def test_stable_exit_ids_across_reparses(self):
        source='def f(a):\n    if a == 0:\n        return a\n    return 5\n'
        one,c1=self.graph(source)
        two,c2=self.graph(source)
        def exit_ids(contract):
            return [(n.id,tuple((x.id,x.sites) for x in n.interface.exits)) for n in contract.nodes if n.interface]
        self.assertEqual(exit_ids(c1),exit_ids(c2))


if __name__=='__main__':unittest.main()
