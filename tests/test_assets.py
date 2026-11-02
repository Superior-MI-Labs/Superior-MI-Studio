import sys
import tempfile
import json
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from studio_native.assets import AssetIndex
from studio_native import model as m
ROOT=Path(__file__).resolve().parents[1]

class AssetTests(unittest.TestCase):
    def test_existing_atlas_sheet_ids_and_crops(self):
        index=AssetIndex(ROOT/'packs'/'sci-fi')
        self.assertEqual(len(index.entries),378)
        self.assertGreater(len(index.find('ui.icon')),100)
        self.assertIn('shell.corner.tl',index.entries)
    def test_refuses_traversal(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'pack.json').write_text(json.dumps({'schema_version':1,
                  'sheets':[{'image':'../secret.png','cell_px':128,'width_px':128,'height_px':128,'assets':[]}]}))
            with self.assertRaises(ValueError):AssetIndex(root)
    def test_can_open_actual_browser_export(self):
        state=m.read_state(ROOT/'examples'/'browser-v0.1-export.json')
        self.assertEqual(len(state['nodes']),3)
        self.assertEqual(m.validate(state),[])
if __name__=='__main__':unittest.main()
