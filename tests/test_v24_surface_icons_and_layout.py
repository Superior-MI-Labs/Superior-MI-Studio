"""v2.4: shared graph gestures, optional manifests, stable resources."""
import json
import tempfile
import unittest
from pathlib import Path
from studio_native.graph_surface import (resize_handle, resize_rectangle,
                                          RESOURCE_COMPACT_WIDTH, RESOURCE_COMPACT_HEIGHT)
from studio_native.external_icons import (ExternalIconAtlas, icon_id_for_resource,
                                          icon_id_for_source, PACK_ID)
from studio_native.resource_graph import directory_graph


class GraphGeometryTests(unittest.TestCase):
    def test_edges_and_corners_are_all_resizable(self):
        width,height=300.,160.
        positions={
            'nw':(2,2),'n':(150,2),'ne':(298,2),
            'e':(298,80),'se':(298,158),'s':(150,158),
            'sw':(2,158),'w':(2,80)}
        for handle,(x,y) in positions.items():
            with self.subTest(handle=handle):
                self.assertEqual(resize_handle(x,y,width,height),handle)
        self.assertIsNone(resize_handle(150,80,width,height))
        self.assertIsNone(resize_handle(-30,40,width,height))

    def test_resizing_keeps_opposite_edge_fixed(self):
        for handle in ('w','e','n','s','nw','ne','sw','se'):
            with self.subTest(handle=handle):
                w,h,x,y=resize_rectangle(handle,300,160,20,12)
                if 'w' in handle:self.assertAlmostEqual(x+w,300)
                if 'n' in handle:self.assertAlmostEqual(y+h,160)
                if 'e' in handle:self.assertEqual(w,320)
                if 's' in handle:self.assertEqual(h,172)
                if 'w' not in handle:self.assertEqual(x,0)
                if 'n' not in handle:self.assertEqual(y,0)
        self.assertEqual(resize_rectangle('w',200,160,1000,0),(180,160,20,0))
        with self.assertRaises(ValueError):resize_rectangle('diagonal',300,160,10,10)


class ResourceLayoutTests(unittest.TestCase):
    def test_expansion_does_not_push_unrelated_resource_positions(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for i in range(8):
                folder=root/f'folder{i:02}';folder.mkdir()
                (folder/'child.txt').write_text('content')
            before=directory_graph(root)
            after=directory_graph(root,expanded_paths={str(root/'folder00')})
            positions=lambda g: {n['id']:(n['x'],n['y']) for n in g['nodes']
                                 if not n.get('containing_scope')}
            self.assertEqual(positions(before),positions(after))
            self.assertEqual(len(positions(before)),8)
            self.assertLess(RESOURCE_COMPACT_WIDTH,200)
            self.assertLess(RESOURCE_COMPACT_HEIGHT,40)

    def test_resource_filename_is_not_destroyed_for_display(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/('a'*67+'.py');p.write_text('pass\n')
            item=directory_graph(temp)['nodes'][0]
            self.assertEqual(item['title'],p.name)
            self.assertEqual(item['display_title'],p.name)
            self.assertEqual(item['resource_path'],str(p))


class ExternalAtlasTests(unittest.TestCase):
    def test_not_installed_is_optional(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertIsNone(ExternalIconAtlas.discover(Path(temp)/'absent'))

    def make_pack(self,root,*,escape=False):
        folder=root/'Universal-Atlas';folder.mkdir()
        path=folder/'sheet.png';path.write_bytes(b'png-image-placeholder')
        asset={'id':'icons.files-formats.python-source','rect_px':{'x':0,'y':0,'w':96,'h':96}}
        data={'schema_version':'4.0.0','pack_id':PACK_ID,'version':'4.0.0',
              'sheets':[{'files':{'rgba':'../outside.png' if escape else 'sheet.png'},
                         'assets':[asset]}]}
        (folder/'manifest.json').write_text(json.dumps(data))
        return folder

    def test_manifest_discovery_nested_in_install_root(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);folder=self.make_pack(root)
            pack=ExternalIconAtlas.discover(root)
            self.assertIsNotNone(pack)
            self.assertEqual(pack.root,folder.resolve())
            self.assertEqual(pack.lookup('icons.files-formats.python-source')[1],(0,0,96,96))
            self.assertIsNone(pack.lookup('missing'))

    def test_manifest_refuses_path_escape(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);folder=self.make_pack(root,escape=True)
            (root/'outside.png').write_bytes(b'x')
            with self.assertRaises(ValueError):ExternalIconAtlas.from_directory(folder)
            self.assertIsNone(ExternalIconAtlas.discover(root))

    def test_semantic_mappings_are_canonical(self):
        self.assertEqual(icon_id_for_resource('file','.json'),'icons.files-formats.json-file')
        self.assertEqual(icon_id_for_source('if'),'icons.programming.control.if')


if __name__=='__main__':unittest.main()
