"""v1.9 resource graph / semantic contract: read-only by construction."""
import tempfile
import unittest
from pathlib import Path
from studio_native.resource_graph import directory_graph, snapshot, ResourceError
from studio_native.semantic_contract import describe_graph, ContractError

class ResourceTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.root=Path(self.t.name)
        (self.root/'alpha').mkdir()
        (self.root/'zeta').mkdir()
        (self.root/'main.py').write_text("raise RuntimeError('must not run')\n",encoding='utf-8')
        (self.root/'notes.txt').write_text('text')
    def tearDown(self):self.t.cleanup()

    def test_browsing_never_executes_python(self):
        g=directory_graph(self.root)
        self.assertEqual(len(g['nodes']),4)
        self.assertEqual((self.root/'main.py').read_text(),"raise RuntimeError('must not run')\n")
        self.assertEqual(len(g['edges']),0)

    def test_identity_is_stable_and_contract_accepts_resource(self):
        first=directory_graph(self.root);second=directory_graph(self.root)
        self.assertEqual([n['id'] for n in first['nodes']],[n['id'] for n in second['nodes']])
        descriptor=describe_graph(first,origin='resource')
        self.assertEqual(descriptor.origin,'resource')
        self.assertEqual(len(descriptor.nodes),4)
        self.assertTrue(all(n.source is None for n in descriptor.nodes))

    def test_directories_first_and_name_sort(self):
        g=directory_graph(self.root)
        self.assertEqual([n['title'] for n in g['nodes']],['alpha','zeta','main.py','notes.txt'])

    def test_symlink_is_leaf_and_traversal_refused(self):
        link=self.root/'loop';link.symlink_to(self.root, target_is_directory=True)
        g=directory_graph(self.root)
        node=next(n for n in g['nodes'] if n['title']=='loop')
        self.assertEqual(node['resource_kind'],'symlink')
        with self.assertRaises(ResourceError):directory_graph(link)

    def test_pagination_and_limits(self):
        for i in range(90):(self.root/f'file-{i:03d}.py').touch()
        first=directory_graph(self.root);second=directory_graph(self.root,offset=72)
        self.assertTrue(first['truncated']);self.assertFalse(first['has_previous'])
        self.assertTrue(second['has_previous']);self.assertFalse(second['truncated'])
        self.assertFalse(set(n['id'] for n in first['nodes']) & set(n['id'] for n in second['nodes']))
        self.assertEqual(len(first['nodes'])+len(second['nodes']),94)

    def test_limits_fail_closed(self):
        for invalid in [0,-1,73]:
            with self.assertRaises(ResourceError):directory_graph(self.root,limit=invalid)
        for invalid in [-1,721]:
            with self.assertRaises(ResourceError):directory_graph(self.root,offset=invalid)

    def test_non_directory_refused(self):
        with self.assertRaises(ResourceError):directory_graph(self.root/'notes.txt')

    def test_resources_cannot_claim_python_source_spans(self):
        g=directory_graph(self.root)
        g['nodes'][0]['source_span']={'line':1,'col':0,'end_line':2,'end_col':1}
        with self.assertRaises(ContractError):describe_graph(g,origin='resource')

    def test_relative_path_and_parent_consistency(self):
        g=directory_graph(self.root)
        self.assertEqual(g['path'],str(self.root))
        self.assertTrue(all(Path(n['resource_path']).parent==self.root for n in g['nodes']))

if __name__=='__main__': unittest.main()
