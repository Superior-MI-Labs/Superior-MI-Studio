"""v2.3: semantic exit routes and normalised presentation contract.

All tests are Qt-free; live paint/mouse qualification belongs to qt_smoke.py.
"""
import copy
import tempfile
import unittest
from pathlib import Path
from studio_native.python_graph import PythonDocument
from studio_native.semantic_contract import describe_graph, ContractError
from studio_native.exit_routes import project_exit_routes


class ExitRoutingTests(unittest.TestCase):
    @staticmethod
    def project(source):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'example.py'
            path.write_text(source, encoding='utf-8')
            doc=PythonDocument(path)
            raw=doc.composite_file_graph(set(doc.scopes)-{'module'})
            return raw,describe_graph(raw,origin='source')

    def test_folds_single_terminal_site_without_exposed_terminal_facets(self):
        raw,contract=self.project('def f(a):\n    return a\n')
        routes=project_exit_routes(contract)
        self.assertEqual(len(routes),1)
        self.assertTrue(routes[0].folded)
        self.assertIsNotNone(routes[0].value_input)
        self.assertTrue(routes[0].value_port)
        self.assertEqual({n.id for n in contract.nodes},{n['id'] for n in raw['nodes']})

    def test_early_and_final_returns_have_distinct_routes_same_boundary(self):
        _,contract=self.project('def f(a):\n    if a > 0:\n        return a\n    return 0\n')
        routes=project_exit_routes(contract)
        self.assertEqual(len(routes),2)
        self.assertEqual(len({r.owner_node for r in routes}),1)
        self.assertEqual(len({r.control_anchor for r in routes}),1)
        self.assertEqual(len({r.site_node for r in routes}),2)
        self.assertTrue(all(r.value_input and r.value_port for r in routes))
        self.assertTrue(all(not r.folded for r in routes))

    def test_loop_nesting_routes_return_to_function(self):
        _,contract=self.project('def f(n):\n    while n:\n        if n > 2:\n            return n\n        n -= 1\n    return 0\n')
        routes=project_exit_routes(contract)
        self.assertEqual(len(routes),2)
        fn=next(n for n in contract.nodes if n.construct=='function' and n.interface)
        self.assertTrue(all(r.owner_node==fn.id for r in routes))
        self.assertNotIn(r'loop', {r.kind for r in routes})

    def test_nested_functions_do_not_share_exit_owner(self):
        raw,contract=self.project('def outer(a):\n    def inner(b):\n        return b\n    return a\n')
        routes=project_exit_routes(contract)
        self.assertEqual(len(routes),2)
        self.assertEqual(len({r.owner_node for r in routes}),2)
        self.assertEqual(len({r.control_anchor for r in routes}),2)
        nested=next(n for n in raw['nodes'] if n.get('source_kind')=='nested')
        self.assertEqual(nested['graph_interface']['category'],'function')
        self.assertIn('return',[p['label'] for p in nested['draft_ports']['outputs']])
        from studio_native.boundary_edit import terminal_return_target, parameter_source
        return_port=next(p['id'] for p in nested['draft_ports']['outputs'] if p['label']=='return')
        resolved=terminal_return_target(raw,nested['id'],return_port)
        self.assertEqual(resolved[0],next(r.site_node for r in routes if r.owner_node==nested['id']))
        argument_port=next(p['id'] for p in nested['draft_ports']['inputs'] if p['label']=='b')
        self.assertTrue(parameter_source(raw,nested['id'],argument_port))

    def test_bare_return_only_has_control_facet(self):
        _,contract=self.project('def f():\n    if True:\n        return\n    return\n')
        routes=project_exit_routes(contract)
        self.assertEqual(len(routes),2)
        self.assertTrue(all(r.value_input is None for r in routes))
        self.assertTrue(all(r.control_anchor for r in routes))

    def test_no_return_does_not_fabricate_a_site(self):
        _,contract=self.project('def f(a):\n    b = a + 1\n')
        self.assertEqual(project_exit_routes(contract),())

    def test_return_projection_is_stable_across_reparses(self):
        code='def f(a):\n    if a == 0:\n        return 4\n    return a\n'
        self.assertEqual(project_exit_routes(self.project(code)[1]),
                         project_exit_routes(self.project(code)[1]))

    def test_projection_keeps_canonical_node_and_edge_counts(self):
        raw,contract=self.project('def f(a):\n    if a > 0:\n        return a\n    return 4\n')
        ids=({n.id for n in contract.nodes},{e.id for e in contract.edges})
        project_exit_routes(contract)
        self.assertEqual(ids,({n.id for n in contract.nodes},{e.id for e in contract.edges}))
        self.assertEqual(len(contract.nodes),len(raw['nodes']))
        self.assertEqual(len(contract.edges),len(raw['edges']))

    def test_wrong_construct_is_rejected_by_contract(self):
        raw,_=self.project('def f(a):\n    return a\n')
        broken=copy.deepcopy(raw)
        fake=next(n for n in broken['nodes'] if n.get('source_kind')=='param')
        fn=next(n for n in broken['nodes'] if n.get('graph_interface',{}).get('category')=='function')
        fn['graph_interface']['exits'][0]['sites']=[fake['id']]
        with self.assertRaises(ContractError):describe_graph(broken,origin='source')

    def test_return_value_cannot_point_to_execution_port(self):
        raw,_=self.project('def f(a):\n    return a\n')
        fn=next(n for n in raw['nodes'] if n.get('graph_interface',{}).get('category')=='function')
        fn['draft_ports']['outputs'].append({'id':'fake-flow','label':'completion','type':'execution'})
        fn['graph_interface']['outputs'].append('fake-flow')
        fn['graph_interface']['exits'][0]['value_port']='fake-flow'
        with self.assertRaises(ContractError):describe_graph(raw,origin='source')


class AppearanceContractTests(unittest.TestCase):
    def test_source_operator_metadata_is_normalized(self):
        raw,contract=ExitRoutingTests.project('def add(a,b):\n    return a+b\n')
        operations=[n for n in contract.nodes if n.construct=='operation']
        self.assertTrue(operations)
        self.assertTrue(all(n.appearance is not None for n in operations))
        self.assertEqual({n.id for n in contract.nodes},{n['id'] for n in raw['nodes']})

    def test_resource_nodes_receive_common_appearance(self):
        from studio_native.resource_graph import directory_graph
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp,'test.py').write_text('pass\n')
            # A resource is a data provider, not an executable node.
            graph=directory_graph(Path(tmp))
            contract=describe_graph(graph,origin='resource')
            self.assertTrue(contract.nodes)
            self.assertTrue(all(n.appearance and n.appearance.title for n in contract.nodes))
            self.assertTrue(all(n.origin=='resource' for n in contract.nodes))

    def test_invalid_appearance_symbol_rejected(self):
        raw,_=ExitRoutingTests.project('def f(x):\n    return x\n')
        broken=copy.deepcopy(raw)
        broken['nodes'][0]['display_symbol']=['not','a','symbol']
        with self.assertRaises(ContractError):describe_graph(broken,origin='source')


if __name__=='__main__': unittest.main()
