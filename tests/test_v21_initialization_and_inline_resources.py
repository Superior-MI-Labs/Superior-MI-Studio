"""v2.1 regression: empty canvas authorities and recursive directory resources."""
import tempfile
import unittest
from pathlib import Path
from studio_native.resource_graph import directory_graph
from studio_native.semantic_contract import describe_graph, canvas_graph_source, ContractError


class CanvasAuthorityTests(unittest.TestCase):
    def test_unloaded_source_never_uses_draft_nodes(self):
        draft={'nodes':[{'id':'draft-id'}],'edges':[]}
        self.assertEqual(canvas_graph_source(source_view=True,state=draft), (None,'source'))
        self.assertEqual(canvas_graph_source(resource_view=True,state=draft), (None,'resource'))
        self.assertEqual(canvas_graph_source(settings_view=True,state=draft), (None,None))
        self.assertIs(canvas_graph_source(state=draft)[0],draft)
        document={'nodes':[], 'edges':[]}
        self.assertIs(canvas_graph_source(source_view=True,state=draft,source_graph=document)[0],document)
        with self.assertRaises(ContractError):
            canvas_graph_source(resource_view=True,source_view=True,state=draft)


class InlineFilesTests(unittest.TestCase):
    def test_expanding_directory_preserves_file_ids_and_ownership(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            folder=root/'folder';folder.mkdir()
            (folder/'hello.py').write_text('def hello(): return 4\n')
            first=directory_graph(root)
            expanded=directory_graph(root, expanded_paths={str(folder)})
            parent=first['nodes'][0]
            owner=expanded['nodes'][0]
            assert parent['id']==owner['id']
            assert owner['child_region_key']==owner['embedded_region']['scope']
            child=next(n for n in expanded['nodes'] if n['title']=='hello.py')
            assert child['containing_scope']==owner['child_region_key']
            assert child['id'] not in {n['id'] for n in first['nodes']}
            assert len(describe_graph(expanded,origin='resource').nodes)==2
            assert not any(n.get('source_span') for n in expanded['nodes'])

    def test_only_explicitly_expanded_directories_traverse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            outer=root/'outer';outer.mkdir()
            inner=outer/'inner';inner.mkdir()
            (inner/'a.py').write_text('pass\n')
            g=directory_graph(root,expanded_paths={str(outer)})
            assert {n['title'] for n in g['nodes']}=={'outer','inner'}
            deep=directory_graph(root,expanded_paths={str(outer),str(inner)})
            assert {n['title'] for n in deep['nodes']}=={'outer','inner','a.py'}
            assert all(n['id'].startswith('resource:') for n in deep['nodes'])
            assert len({n['id'] for n in deep['nodes']})==3
            assert deep['nodes'][-1]['containing_scope'] == ('resource-region:'+deep['nodes'][1]['id'])

    def test_symlink_is_never_traversed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            d=root/'real';d.mkdir();(d/'file.py').write_text('pass')
            alias=root/'link';alias.symlink_to(d)
            graph=directory_graph(root,expanded_paths={str(alias)})
            assert not any(n['title']=='file.py' for n in graph['nodes'])
            assert next(n for n in graph['nodes'] if n['title']=='link')['resource_kind']=='symlink'

    def test_bounded_inline_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for i in range(50):
                d=root/f'd{i:02}';d.mkdir()
                for j in range(30):(d/f'item{j:02}.py').write_text('pass')
            graph=directory_graph(root,expanded_paths={str(root/f'd{i:02}') for i in range(50)})
            assert len(graph['nodes'])<=180
            assert len({n['id'] for n in graph['nodes']})==len(graph['nodes'])
            assert describe_graph(graph,origin='resource')


if __name__=='__main__':unittest.main()
