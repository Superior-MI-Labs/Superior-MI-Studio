"""Qt-free v2.6 regression: source-owned folded exits never become new edges."""
import copy
import tempfile
import unittest
from pathlib import Path
from studio_native.python_graph import PythonDocument
from studio_native.exit_routes import project_exit_routes, project_folded_exit_connections
from studio_native.semantic_contract import describe_graph, ContractError


class FoldedReturnConnectionsTests(unittest.TestCase):
    def graph(self, code, *, collapsed=()):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/'sample.py'
            file.write_text(code,encoding='utf-8')
            document=PythonDocument(file)
            raw=document.composite_file_graph(set(document.scopes)-{'module'},
                                              detail='readable',collapsed_regions=set(collapsed))
            return raw,describe_graph(raw,origin='source')

    @staticmethod
    def connections(contract):
        return project_folded_exit_connections(contract,project_exit_routes(contract))

    def test_nested_expression_folds_existing_data_and_control_edges(self):
        raw,contract=self.graph('def f(a,b):\n    total = a + b\n    return total\n')
        connections=self.connections(contract)
        self.assertEqual({c.facet for c in connections},{'value','control'})
        self.assertEqual({c.edge_id for c in connections},
                         {e.id for e in contract.edges if e.target_node==connections[0].route.site_node})
        self.assertTrue(all(c.route.folded for c in connections))

    def test_folded_connections_resolve_actual_declared_interface(self):
        _,contract=self.graph('def f(a):\n    x = a * 2\n    return x\n')
        for connection in self.connections(contract):
            owner=next(n for n in contract.nodes if n.id==connection.route.owner_node)
            self.assertTrue(any(p.id==connection.route.value_port for p in owner.ports))
            self.assertTrue(any(e.id==connection.edge_id and e.target_node==connection.route.site_node
                                for e in contract.edges))

    def test_parameter_return_does_not_fabricate_control_edge(self):
        _,contract=self.graph('def f(a):\n    return a\n')
        connections=self.connections(contract)
        self.assertEqual([c.facet for c in connections],['value'])
        self.assertTrue(connections[0].route.control_anchor)

    def test_literal_return_has_no_fabricated_value_edge(self):
        _,contract=self.graph('def f():\n    return 7\n')
        connections=self.connections(contract)
        self.assertEqual(connections,())
        self.assertEqual(len(project_exit_routes(contract)),1)

    def test_early_return_sites_are_not_folded(self):
        _,contract=self.graph('def f(n):\n    if n < 0:\n        return 0\n    return n\n')
        self.assertEqual(self.connections(contract),())
        self.assertTrue(all(not route.folded for route in project_exit_routes(contract)))

    def test_collapsed_conditional_must_not_be_rebound_as_terminal_return(self):
        code='def f(n):\n    if n:\n        return n\n    return 0\n'
        raw,_=self.graph(code)
        branch=next(n for n in raw['nodes'] if n.get('source_kind')=='branch')
        _,collapsed=self.graph(code,collapsed={'obsolete/region:'+branch['id']})
        self.assertFalse(any(route.folded for route in project_exit_routes(collapsed)))
        self.assertEqual(self.connections(collapsed),())


    def test_nested_function_return_routes_never_cross_owners(self):
        _,contract=self.graph('def outer(a):\n    def inner(b):\n        return b\n    return a\n')
        routes=project_exit_routes(contract)
        self.assertEqual(len(routes),2)
        self.assertEqual(len({r.owner_node for r in routes}),2)
        self.assertEqual(len({r.route.owner_node for r in self.connections(contract)}),2)

    def test_projection_preserves_canonical_graph_and_edge_identity(self):
        raw,contract=self.graph('def f(a):\n    b = a + 3\n    return b\n')
        before=(tuple(n.id for n in contract.nodes),tuple(e.id for e in contract.edges))
        self.connections(contract)
        after=(tuple(n.id for n in contract.nodes),tuple(e.id for e in contract.edges))
        self.assertEqual(before,after)
        self.assertEqual(len(raw['edges']),len(contract.edges))

    def test_forged_folded_owner_is_rejected(self):
        raw,_=self.graph('def f(a):\n    return a\n')
        broken=copy.deepcopy(raw)
        site=next(n for n in broken['nodes'] if n.get('terminal_boundary_owner'))
        site['terminal_boundary_owner']='a different function'
        with self.assertRaises(ContractError):
            describe_graph(broken,origin='source')


if __name__=='__main__':
    unittest.main()
