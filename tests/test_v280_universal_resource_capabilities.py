"""Universal resource presentation: one canvas, bounded providers, verified evidence."""
import tempfile
import unittest
from pathlib import Path

from studio_native.resource_graph import directory_graph, MAX_EMBEDDED_SOURCE_NODES, preview_kind
from studio_native.semantic_contract import describe_graph
from studio_native.source_associations import local_python_literal_files


class ResourceCapabilities(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root=Path(folder.name)

    def write(self,name,body):
        file=self.root/name
        if isinstance(body,bytes):file.write_bytes(body)
        else:file.write_text(body,encoding='utf-8')
        return file

    def test_image_and_python_expand_without_second_graph_or_file_write(self):
        py=self.write('main.py','def render():\n    return 3\n\nclass Game:\n    pass\n')
        image=self.write('icon.png',b'not-an-image-yet')
        original=(py.read_bytes(),image.read_bytes())
        collapsed=directory_graph(self.root)
        expanded=directory_graph(self.root,expanded_paths=(py,image))
        by_name={n['title']:n for n in expanded['nodes']}
        self.assertEqual(by_name['icon.png']['preview_kind'],'image')
        self.assertEqual(by_name['icon.png']['resource_preview']['kind'],'image')
        self.assertNotIn('pixels',by_name['icon.png']['resource_preview'])
        self.assertEqual(by_name['main.py']['preview_kind'],'python-graph')
        self.assertEqual(by_name['main.py']['region_role'],'python-source')
        nested=[n for n in expanded['nodes'] if n.get('resource_source_path')==str(py)]
        self.assertIn('function',{n['source_kind'] for n in nested})
        self.assertTrue(any('render' in n['title'].lower() for n in nested))
        self.assertEqual([n['id'] for n in expanded['nodes'] if n.get('resource_kind')],
                         [n['id'] for n in collapsed['nodes']])
        self.assertEqual(len(describe_graph(expanded,origin='resource').nodes),len(expanded['nodes']))
        self.assertEqual(original,(py.read_bytes(),image.read_bytes()))

    def test_only_explicit_files_are_analyzed(self):
        self.write('first.py','def valid(): pass\n')
        self.write('second.py','def invalid(: pass\n')
        listing=directory_graph(self.root)
        self.assertTrue(all(n['resource_preview'] is None for n in listing['nodes']))
        expanded=directory_graph(self.root,expanded_paths=(self.root/'second.py',))
        previews={n['title']:n['resource_preview'] for n in expanded['nodes']}
        self.assertIsNone(previews['first.py'])
        self.assertEqual(previews['second.py']['status'],'Python analysis unavailable')

    def test_symbol_limit_is_bounded(self):
        py=self.write('huge.py','\n'.join('def f%d(): pass'%i for i in range(22)))
        preview=next(n['resource_preview'] for n in directory_graph(
            self.root,expanded_paths=(py,))['nodes'] if n['title']=='huge.py')
        graph=directory_graph(self.root,expanded_paths=(py,))
        embedded=[n for n in graph['nodes'] if n.get('resource_source_path')==str(py)]
        self.assertLessEqual(len(embedded),MAX_EMBEDDED_SOURCE_NODES)
        self.assertTrue(embedded)
        self.assertIn('source', next(n for n in graph['nodes'] if n['title']=='huge.py')['subtitle'].lower())

    def test_symlink_and_large_file_never_decode_or_expand(self):
        image=self.write('good.png',b'png')
        (self.root/'link.png').symlink_to(image)
        large=self.write('huge.png',b'0'*8_000_001)
        graph=directory_graph(self.root,expanded_paths=(self.root/'link.png',large))
        entries={n['title']:n for n in graph['nodes']}
        self.assertEqual(entries['link.png']['preview_kind'],'none')
        self.assertEqual(entries['huge.png']['resource_preview']['status'],'Preview exceeds 8 MB limit')
        self.assertEqual(preview_kind(self.root/'good.png','file'),'image')

    def test_asset_reference_has_evidence_and_distinct_non_exec_type(self):
        py=self.write('main.py',"from helper import draw\n\nwith open('hero.png', 'rb') as f: pass\nPath('settings.json')\n")
        self.write('helper.py','def draw(): pass\n')
        image=self.write('hero.png',b'png')
        self.write('settings.json','{}')
        plain=directory_graph(self.root)
        self.assertEqual(plain['edges'],[])
        annotated=directory_graph(self.root,show_imports=True)
        self.assertEqual({e['relation'] for e in annotated['edges']},{'imports','reference'})
        assets=[e for e in annotated['edges'] if e['relation']=='reference']
        self.assertEqual(len(assets),2)
        self.assertTrue(all(e['certainty']=='literal-path-candidate' for e in assets))
        self.assertEqual({e['provenance'][0]['line'] for e in assets},{3,4})
        self.assertEqual(len(describe_graph(annotated,origin='resource').edges),3)
        self.assertEqual({n['id'] for n in plain['nodes']},{n['id'] for n in annotated['nodes']})
        self.assertTrue(local_python_literal_files(py,{py,image}))

    def test_dynamic_traversal_and_unrelated_strings_never_create_edges(self):
        py=self.write('main.py',"open('../secret.png')\nopen(base + '.png')\nmessage='asset.png'\nopen('/tmp/asset.png')\n")
        other=self.write('asset.png',b'png')
        self.assertEqual(local_python_literal_files(py,{py,other}),[])
        self.assertEqual(directory_graph(self.root,show_imports=True)['edges'],[])

    def test_expansion_inside_folder_keeps_single_resource_owner(self):
        folder=self.root/'nested';folder.mkdir()
        py=folder/'module.py';py.write_text('def run(): pass\n')
        graph=directory_graph(self.root,expanded_paths=(folder,py))
        parent,child=graph['nodes'][:2]
        self.assertEqual(child['containing_scope'],parent['child_region_key'])
        self.assertEqual(child['region_role'],'python-source')
        self.assertTrue(any(n.get('resource_source_path')==str(py) for n in graph['nodes']))
        self.assertEqual(len(describe_graph(graph,origin='resource').nodes),len(graph['nodes']))


if __name__=='__main__':unittest.main()
