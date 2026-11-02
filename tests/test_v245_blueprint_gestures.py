"""Unreal-style graph selection is a presentation concern, not a Python edit."""
import unittest

from studio_native.graph_surface import marquee_selection


class BlueprintMarqueeSelectionTests(unittest.TestCase):
    def test_replace_drops_prior_selection(self):
        self.assertEqual(marquee_selection({'old', 'wire'}, {'new'}), {'new'})

    def test_shift_add_keeps_existing_selection(self):
        self.assertEqual(marquee_selection({'old'}, {'new'}, 'add'), {'old', 'new'})

    def test_ctrl_toggle_removes_hits_already_selected(self):
        self.assertEqual(marquee_selection({'a', 'b'}, {'b', 'c'}, 'toggle'), {'a', 'c'})

    def test_empty_blank_click_replaces_with_no_selection(self):
        self.assertEqual(marquee_selection({'a'}, set()), set())

    def test_shift_and_ctrl_blank_drag_preserve_selection(self):
        self.assertEqual(marquee_selection({'a'}, set(), 'add'), {'a'})
        self.assertEqual(marquee_selection({'a'}, set(), 'toggle'), {'a'})

    def test_invalid_mode_is_not_silently_coerced(self):
        with self.assertRaises(ValueError):
            marquee_selection(set(), set(), 'pan')


if __name__ == '__main__':
    unittest.main()
