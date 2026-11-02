"""One source-backed operation graph under full-file and focused navigation.

Focus is a viewport/root change, never a second IF/LOOP interpretation.
"""
import unittest
from pathlib import Path

from studio_native.graph_routes import resolve_graph
from studio_native.navigation import Route
from studio_native.python_graph import PythonDocument, SourceError
from studio_native.semantic_contract import describe_graph

ROOT = Path(__file__).resolve().parents[1]


class CanonicalRecursiveProjectionTests(unittest.TestCase):
    def setUp(self):
        self.doc = PythonDocument(ROOT / 'examples' / 'python-v15-boundary-regions.py')
        self.before = self.doc.path.read_bytes()

    def scope(self, name):
        return next(k for k, s in self.doc.scopes.items() if s.title == name)

    def test_focus_does_not_replace_control_operation_with_a_second_model(self):
        key=self.scope('nested')
        flat=self.doc.presentation_graph(key)
        focused=resolve_graph(Route('source',str(self.doc.path),key,'focus'),document=self.doc)
        self.assertEqual({n['id'] for n in flat['nodes']},{n['id'] for n in focused.graph['nodes']})
        self.assertEqual({e['id'] for e in flat['edges']},{e['id'] for e in focused.graph['edges']})
        self.assertEqual(focused.descriptor,describe_graph(focused.graph,origin='source'))
        nested=[n for n in focused.graph['nodes'] if n['source_kind'] in ('branch','loop')]
        self.assertEqual([n['source_kind'] for n in nested],['loop','loop','branch'])
        self.assertTrue(all(n.get('graph_interface') and not n.get('child_region_key') for n in nested))
        self.assertTrue(all(n['containing_scope']==key for n in nested))
        self.assertEqual(self.before,self.doc.path.read_bytes())


    def test_whole_file_and_focus_use_same_node_and_port_identity(self):
        key = self.scope('accumulate')
        full = self.doc.composite_file_graph(expanded={key})
        focus = self.doc.composite_file_graph(focus_scope=key)
        a = {n['id']: n for n in full['nodes'] if n['id'] in {x['id'] for x in focus['nodes']}}
        b = {n['id']: n for n in focus['nodes']}
        self.assertEqual(a.keys(), b.keys())
        for node_id in b:
            self.assertEqual(a[node_id]['source_kind'], b[node_id]['source_kind'])
            self.assertEqual(a[node_id]['draft_ports'], b[node_id]['draft_ports'])
            self.assertEqual(a[node_id].get('child_region_key'), b[node_id].get('child_region_key'))
        self.assertEqual({e['id'] for e in full['edges'] if e['source'] in b and e['target'] in b},
                         {e['id'] for e in focus['edges']})

    def test_collapsing_a_region_hides_visual_contents_without_rewriting_edges(self):
        key=self.scope('nested')
        normal=self.doc.composite_file_graph(focus_scope=key)
        closed=self.doc.composite_file_graph(focus_scope=key,collapsed_regions={'obsolete/region'})
        self.assertEqual({n['id'] for n in normal['nodes']},{n['id'] for n in closed['nodes']})
        self.assertEqual(normal['edges'],closed['edges'])
        self.assertTrue(all(not n.get('child_region_key') for n in closed['nodes'] if n['source_kind'] in ('branch','loop')))
        self.assertEqual(self.before,self.doc.path.read_bytes())


    def test_module_focus_preserves_the_valid_module_graph_path(self):
        focused = resolve_graph(Route('source', str(self.doc.path), 'module', 'focus'), document=self.doc)
        direct = self.doc.presentation_graph('module')
        self.assertEqual({n['id'] for n in focused.graph['nodes']},
                         {n['id'] for n in direct['nodes']})
        self.assertEqual({e['id'] for e in focused.graph['edges']},
                         {e['id'] for e in direct['edges']})
        self.assertEqual(focused.graph['presentation'], 'composite')

    def test_unresolved_region_route_is_not_misrepresented_as_a_scope(self):
        with self.assertRaisesRegex(ValueError, 'region'):
            resolve_graph(Route('region', str(self.doc.path), region='if:unknown'))
        with self.assertRaisesRegex(SourceError, 'lexical scope'):
            self.doc.composite_file_graph(focus_scope='definitely-not-a-scope')


if __name__ == '__main__':
    unittest.main()
