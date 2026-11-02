"""v2.5: presentation persistence is a versioned user preference, never source."""
import json
import math
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from studio_native.presentation_state import (
    PresentationStore, blank, validate, default_location, MAX_BYTES)
from studio_native.icon_styles import icon_hint
from studio_native.external_icons import ExternalIconAtlas, PACK_ID


class PresentationTests(unittest.TestCase):
    def test_missing_file_is_empty_and_nonfatal(self):
        with tempfile.TemporaryDirectory() as d:
            store=PresentationStore(Path(d)/'prefs.json')
            self.assertEqual(store.load(),blank())
            self.assertIsNone(store.error)
            self.assertFalse(store.path.exists())

    def test_atomic_roundtrip_all_view_categories(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'settings'/'views.json'
            store=PresentationStore(path)
            value={'version':1,
                'source_positions':[{'path':'/tmp/a.py','view':'whole','node':'a','x':123.5,'y':-4}],
                'resource_positions':[{'node':'resource:file:/tmp/test','x':11,'y':15}],
                'setting_positions':[{'node':'settings:colors','x':31,'y':22}],
                'cameras':[{'path':'/tmp/a.py','graph':'fn','x':-25,'y':6,'zoom':1.25}],
                'sizes':[{'path':'/tmp/a.py','graph':'fn','width':800,'height':400}],
                'front':[{'path':'/tmp/a.py','graph':'fn','node':'var-a'}],
                'documents':{'/tmp/a.py':{'expanded':['fn','fn/nested'],'collapsed':['fn/if']}},
                'resource_expanded':['/tmp/project'], 'resource_path':'/tmp/project'}
            store.save(value)
            self.assertEqual(store.load(),validate(value))
            self.assertEqual(list(path.parent.iterdir()),[path])
            self.assertLess(path.stat().st_size,MAX_BYTES)

    def test_save_preserves_unrelated_user_source(self):
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'main.py';source.write_text('value=3\n')
            before=source.read_bytes()
            PresentationStore(Path(d)/'.settings'/'view.json').save(blank())
            self.assertEqual(source.read_bytes(),before)

    def test_corrupt_or_future_schema_refused_without_deleting(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'prefs.json'
            path.write_text('this is not json')
            store=PresentationStore(path)
            self.assertEqual(store.load(),blank())
            self.assertIsNotNone(store.error)
            self.assertEqual(path.read_text(),'this is not json')
            path.write_text('{"version":999}')
            self.assertEqual(store.load(),blank())
            self.assertIsNotNone(store.error)

    def test_nonfinite_and_invalid_coordinates_refused(self):
        payload=blank()
        payload['resource_positions']=[{'node':'x','x':float('nan'),'y':0}]
        with self.assertRaises(ValueError):validate(payload)
        payload['resource_positions']=[{'node':'x','x':1e100,'y':0}]
        with self.assertRaises(ValueError):validate(payload)

    def test_wrong_version_duplicates_and_nonpositive_dimensions(self):
        with self.assertRaises(ValueError):validate({'version':2})
        payload=blank()
        payload['sizes']=[{'path':'p','graph':'s','width':0,'height':15}]
        with self.assertRaises(ValueError):validate(payload)
        item={'node':'dup','x':4,'y':6}
        payload=blank();payload['resource_positions']=[item,item]
        with self.assertRaises(ValueError):validate(payload)

    def test_distinct_documents_do_not_share_positions(self):
        p=blank()
        p['source_positions']=[{'path':'/one.py','view':'whole','node':'fn','x':10,'y':20},
                               {'path':'/two.py','view':'whole','node':'fn','x':100,'y':200}]
        out=validate(p)
        self.assertEqual(len(out['source_positions']),2)
        self.assertNotEqual(out['source_positions'][0]['x'],out['source_positions'][1]['x'])

    def test_separate_root_view_camera_from_nested_view_camera(self):
        p=blank()
        p['cameras']=[{'path':'/file.py','graph':'@root-view','x':100,'y':200,'zoom':.8},
                      {'path':'/file.py','graph':'scope/fn','x':-40,'y':7,'zoom':1.2}]
        self.assertEqual(len(validate(p)['cameras']),2)

    def test_env_override_for_state_location(self):
        with patch.dict(os.environ,{'SMI_PRESENTATION_STATE_FILE':'~/test_smi_view.json'}):
            self.assertEqual(default_location(),Path.home()/'test_smi_view.json')

    def test_reject_excessive_or_unsafe_records(self):
        p=blank();p['resource_positions']=[{'node':'x','x':1,'y':2,'unexpected':object()}]
        self.assertEqual(validate(p)['resource_positions'][0]['node'],'x')
        p['resource_positions']=[{'node':'bad\x00id','x':1,'y':2}]
        with self.assertRaises(ValueError):validate(p)


class IconHintTests(unittest.TestCase):
    def test_function_and_return_roles_are_distinct(self):
        self.assertEqual(icon_hint('function').icon_id,'icons.programming.oop.function_definition')
        self.assertEqual(icon_hint('return').icon_id,'icons.programming.control.return')

    def test_loop_icon_is_source_aware_not_node_type_specific(self):
        self.assertEqual(icon_hint('loop',source_line='for item in items:').icon_id,
                         'icons.programming.control.for_loop')
        self.assertEqual(icon_hint('loop',source_line='while x > 0:').icon_id,
                         'icons.programming.control.while_loop')

    def test_invalid_tint_falls_back_to_role(self):
        self.assertNotEqual(icon_hint('function',accent='malformed').tint,'malformed')
        self.assertEqual(icon_hint('function',accent='#ABCDEF').tint,'#ABCDEF')

    def test_unrecognized_role_does_not_break_rendering(self):
        self.assertTrue(icon_hint('some-future-language-feature').icon_id)
        self.assertEqual(icon_hint('directory').icon_id,
                         'icons.files.archives-disk-images-and-installers.folder')

    def test_semantic_icon_ids_match_bundled_v4_manifest_fixture(self):
        # Tests use the user's manifest when mounted, but never require it to run.
        locations=[Path('/mnt/data/Superior-MI-Studio-Universal-Icon-Vocabulary-v4.zip')]
        import zipfile
        for archive in locations:
            if not archive.exists():continue
            with zipfile.ZipFile(archive) as z:
                name=next(n for n in z.namelist() if n.endswith('manifest.json'))
                data=json.loads(z.read(name))
            available={item['id'] for sheet in data['sheets'] for item in sheet['assets']}
            for role in ('function','class','if','loop','return','assignment','call','operator'):
                self.assertIn(icon_hint(role).icon_id,available)


if __name__=='__main__':unittest.main()

from studio_native.edge_presentation import edge_style, exit_edge_style

class EdgePresentationTests(unittest.TestCase):
    def test_cross_surface_wires_go_behind_nodes(self):
        local=edge_style('data')
        cross=edge_style('data',crosses_surface=True)
        self.assertLess(cross.z,5)
        self.assertLess(cross.opacity,local.opacity)
        self.assertEqual(local.opacity,1.0)
        self.assertEqual(local.color,cross.color)

    def test_reference_and_import_edges_are_distinct(self):
        self.assertTrue(edge_style('reference').dashed)
        self.assertTrue(edge_style('imports').dashed)
        self.assertFalse(edge_style('data').dashed)
        self.assertFalse(edge_style('control').dashed)

    def test_return_facet_controls_keep_one_style_owner(self):
        self.assertNotEqual(exit_edge_style('control').color,exit_edge_style('value').color)
        with self.assertRaises(ValueError):exit_edge_style('nonexistent')
