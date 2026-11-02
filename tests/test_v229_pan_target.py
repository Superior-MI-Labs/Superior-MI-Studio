"""Selection-aware recursive graph navigation without Qt dependency."""
from __future__ import annotations
import unittest
from studio_native.graph_surface import selected_pan_surface


class Surface:
    def __init__(self, name: str, parent: 'Surface | None' = None, selected=False):
        self.name, self.parent, self.selected = name, parent, selected


class SelectedPanSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.root = Surface('root')
        self.fn = Surface('function', self.root)
        self.branch = Surface('branch', self.fn)
        self.loop = Surface('loop', self.branch)

    def choose(self, hovered):
        return selected_pan_surface(hovered, lambda s: s.parent, lambda s: s.selected)

    def test_hovering_unselected_graph_pans_root(self):
        self.assertIs(self.choose(self.loop), self.root)

    def test_selected_parent_owns_pan_when_descendants_unselected(self):
        self.fn.selected = True
        self.assertIs(self.choose(self.loop), self.fn)

    def test_deepest_selected_graph_wins(self):
        self.fn.selected = self.branch.selected = True
        self.assertIs(self.choose(self.loop), self.branch)
        self.loop.selected = True
        self.assertIs(self.choose(self.loop), self.loop)

    def test_falls_back_after_deselection_without_state_registry(self):
        self.loop.selected = True
        self.assertIs(self.choose(self.loop), self.loop)
        self.loop.selected = False
        self.assertIs(self.choose(self.loop), self.root)

    def test_root_is_usable_without_selection(self):
        self.assertIs(self.choose(self.root), self.root)

    def test_rejects_missing_root(self):
        with self.assertRaisesRegex(ValueError, 'no graph root'):
            selected_pan_surface(None, lambda s: None, lambda s: False)


if __name__ == '__main__':
    unittest.main()
