"""Composite viewport projection: no invented Python operations or duplication."""
import tempfile
import unittest
from pathlib import Path
from studio_native.python_graph import PythonDocument

SOURCE = '''\ndef countdown(n: int) -> int:
    while n > 0:
        n -= 1
    return n

def outer(a):
    def inner(b):
        return a + b
    return inner(3)
'''

class CompositePresentationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.file = Path(self.temp.name) / 'example.py'
        self.file.write_text(SOURCE)
        self.doc = PythonDocument(self.file)
        self.all_expanded = set(self.doc.scopes) - {'module'}
    def tearDown(self): self.temp.cleanup()

    def test_no_new_nodes_or_edges(self):
        old=self.doc.whole_file_graph(self.all_expanded,detail='readable')
        new=self.doc.composite_file_graph(self.all_expanded)
        self.assertEqual({n['id'] for n in old['nodes']},{n['id'] for n in new['nodes']})
        self.assertEqual({e['id'] for e in old['edges']},{e['id'] for e in new['edges']})
        self.assertEqual(len(new['scope_regions']),0)
        self.assertEqual(self.file.read_text(),SOURCE)

    def test_definition_is_single_semantic_owner(self):
        graph=self.doc.composite_file_graph(self.all_expanded)
        ids={n['source_scope'] for n in graph['nodes'] if n.get('source_scope')}
        self.assertEqual(ids,self.all_expanded)
        for scope in self.all_expanded:
            node=next(n for n in graph['nodes'] if n.get('source_scope')==scope)
            self.assertEqual(node['embedded_region']['scope'],scope)
            self.assertGreater(node['embedded_region']['width'],230)
            self.assertGreater(node['embedded_region']['height'],90)

    def test_recursive_ownership_and_local_positions(self):
        graph=self.doc.composite_file_graph(self.all_expanded)
        owners={n['source_scope']:n for n in graph['nodes'] if n.get('source_scope')}
        for node in graph['nodes']:
            parent=owners.get(node.get('containing_scope'))
            if parent:
                self.assertIn('embedded_region',parent)
                self.assertGreaterEqual(node['x'],0)
                self.assertGreaterEqual(node['y'],0)
                self.assertLess(node['x'],parent['embedded_region']['width'])
                self.assertLess(node['y'],parent['embedded_region']['height'])

    def test_collapsing_removes_descendants_only(self):
        collapsed=self.doc.composite_file_graph(set())
        expanded=self.doc.composite_file_graph(self.all_expanded)
        self.assertEqual({n['id'] for n in collapsed['nodes']},
                         {n['id'] for n in self.doc.scope_graph('module')['nodes']})
        self.assertGreater(len(expanded['nodes']),len(collapsed['nodes']))
        self.assertFalse(any(n.get('embedded_region') for n in collapsed['nodes']))

    def test_internal_analysis_stays_authoritative(self):
        src=self.file.read_bytes()
        old=self.doc.scope_graph(next(k for k in self.all_expanded if 'countdown' in k))
        self.doc.composite_file_graph(self.all_expanded)
        self.assertEqual(old,self.doc.scope_graph(next(k for k in self.all_expanded if 'countdown' in k)))
        self.assertEqual(src,self.file.read_bytes())

    def test_loop_is_not_new_lexical_scope(self):
        keys=list(self.doc.scopes)
        self.assertFalse(any('/loop:' in s for s in keys))
        countdown=next(k for k in keys if 'countdown' in k)
        doc=self.doc.composite_file_graph({countdown})
        inner=[n for n in doc['nodes'] if n.get('containing_scope')==countdown]
        self.assertTrue(any(n.get('source_kind')=='loop' for n in inner))
        self.assertFalse(any(n.get('source_scope') for n in inner))

if __name__=='__main__':unittest.main()
