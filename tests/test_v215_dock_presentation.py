"""Dock region preferences remain presentation-only and backward compatible."""
from __future__ import annotations
import json
from pathlib import Path
import tempfile
import unittest
from studio_native.presentation_state import PresentationStore, validate, blank


class DockPresentationTests(unittest.TestCase):
    def test_previous_versions_default_to_pinned(self):
        old={'version':1,'resource_path':'/tmp'}
        self.assertEqual(validate(old)['dock_modes'],{'left':'pinned','right':'pinned'})

    def test_exactly_three_unambiguous_modes(self):
        for mode in ('pinned','collapsed','auto-hide'):
            state=validate({'version':1,'dock_modes':{'left':mode,'right':mode}})
            self.assertEqual(state['dock_modes']['left'],mode)

    def test_one_region_does_not_replace_other(self):
        self.assertEqual(validate({'version':1,'dock_modes':{'right':'auto-hide'}})['dock_modes'],
                         {'left':'pinned','right':'auto-hide'})

    def test_invalid_mode_is_rejected(self):
        for invalid in ('hide','shown','hover',None,True,1,[]):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):
                validate({'version':1,'dock_modes':{'left':invalid}})

    def test_unknown_region_and_malformed_mapping_refuse(self):
        for invalid in ({'code_editor':'collapsed'},[],None,{'left':{'enabled':True}}):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):
                validate({'version':1,'dock_modes':invalid})

    def test_atomic_round_trip_with_original_view_state(self):
        with tempfile.TemporaryDirectory() as location:
            store=PresentationStore(Path(location)/'view-state.json')
            payload=blank()
            payload['dock_modes']={'left':'collapsed','right':'auto-hide'}
            payload['resource_expanded']=['/tmp/example']
            store.save(payload)
            self.assertEqual(store.load(),payload)
            self.assertEqual(json.loads(store.path.read_text())['dock_modes']['right'],'auto-hide')


if __name__=='__main__':unittest.main()
