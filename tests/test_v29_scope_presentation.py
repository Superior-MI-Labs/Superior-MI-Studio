"""The host Qt smoke must interrogate the graph view that owns the node.

These pure-Python assertions run without PyQt6, protecting view and semantic
contracts independently of the native GUI test runner.
"""
from pathlib import Path
import unittest

from studio_native.python_graph import PythonDocument
from studio_native.semantic_contract import describe_graph, port_presentation_role


DEMO = Path(__file__).resolve().parents[1] / 'examples' / 'python-scope-demo.py'


class NestedViewScopeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = PythonDocument(DEMO)
        cls.outer_key = next(k for k, v in cls.doc.scopes.items() if v.title == 'outer')

    def test_expanded_whole_file_contains_the_nested_function_surface(self):
        whole = self.doc.composite_file_graph(set(self.doc.scopes) - {'module'}, detail='readable')
        inner = [n for n in whole['nodes'] if n['source_kind'] == 'nested' and n['title'] == 'INNER']
        self.assertEqual(len(inner), 1)
        self.assertEqual(inner[0]['embedded_region']['role'], 'definition')
        self.assertEqual(inner[0]['embedded_region']['scope'], inner[0]['source_scope'])

    def test_module_focus_does_not_contain_nested_function(self):
        module = self.doc.presentation_graph('module')
        outer = self.doc.presentation_graph(self.outer_key)
        self.assertFalse(any(n['source_kind'] == 'nested' for n in module['nodes']))
        self.assertEqual([n['title'] for n in outer['nodes'] if n['source_kind'] == 'nested'], ['INNER'])

    def test_nested_identity_and_interface_roles_remain_source_backed(self):
        whole = self.doc.composite_file_graph(set(self.doc.scopes) - {'module'}, detail='readable')
        outer = self.doc.presentation_graph(self.outer_key)
        inner = next(n for n in whole['nodes'] if n['source_kind'] == 'nested')
        focused_inner = next(n for n in outer['nodes'] if n['source_kind'] == 'nested')
        self.assertEqual(inner['id'], focused_inner['id'])
        self.assertEqual(inner['draft_ports'], focused_inner['draft_ports'])
        desc = describe_graph(whole, origin='source')
        definition = next(n for n in desc.nodes if n.id == inner['id'])
        self.assertEqual(definition.semantic_role, 'definition')
        role_by_id = {p.id: port_presentation_role(definition, p.id) for p in definition.ports}
        exec_ids = [p['id'] for side in ('inputs', 'outputs')
                    for p in inner['draft_ports'][side] if p['type'] == 'execution']
        self.assertEqual(len(exec_ids), 2)
        self.assertTrue(all(role_by_id[p] == 'definition-time-execution' for p in exec_ids))
        result_id = next(p['id'] for p in inner['draft_ports']['outputs'] if p['label'] == 'return')
        self.assertEqual(role_by_id[result_id], 'definition-result-interface')


if __name__ == '__main__':
    unittest.main()
