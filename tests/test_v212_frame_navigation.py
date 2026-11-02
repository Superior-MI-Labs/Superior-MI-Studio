"""v2.12: viewport navigation invariants independent of Qt and language adapters."""
import math
import unittest
from studio_native.graph_surface import frame_visible_bounds


class FramePolicyTests(unittest.TestCase):
    def test_empty_is_a_noop(self):
        self.assertIsNone(frame_visible_bounds([],1000,600))

    def test_frame_node_bounds_not_background(self):
        target=frame_visible_bounds([(400,100,220,100)],1200,750)
        self.assertEqual(target[:2],(510,150))
        self.assertEqual(target[2],1.3)
        self.assertTrue(target[3])

    def test_dense_graph_never_creates_unusable_zoom(self):
        center_x,center_y,zoom,fits=frame_visible_bounds([(0,0,15000,6000)],1400,800)
        self.assertEqual((center_x,center_y),(7500,3000))
        self.assertEqual(zoom,.3)
        self.assertFalse(fits)

    def test_two_nodes_have_combined_center_and_nonzero_zoom(self):
        cx,cy,z,fits=frame_visible_bounds([(100,100,100,100),(600,300,100,100)],1000,800)
        self.assertEqual((cx,cy),(400,250))
        self.assertGreater(z,.3)
        self.assertTrue(fits)

    def test_nested_readability_floor_does_not_change_true_fit_default(self):
        from studio_native.graph_surface import GraphSurfaceState
        nested=GraphSurfaceState(450,300,9000,5000)
        nested.fit_contents()
        self.assertLess(nested.zoom,.1)
        nested.fit_contents(min_readable_zoom=.32)
        self.assertEqual(nested.zoom,.32)
        self.assertEqual((nested.offset_x,nested.offset_y),(8.0,8.0))
        nested.pan(-500,-200)
        self.assertGreater(nested.zoom,.3)
        with self.assertRaises(ValueError):nested.fit_contents(min_readable_zoom=float('nan'))

    def test_reject_bad_geometry_and_viewport(self):
        for rectangles in ([(0,0,0,10)],[(0,0,float('nan'),10)],[(0,0,10,float('inf'))]):
            with self.assertRaises(ValueError):frame_visible_bounds(rectangles,1000,600)
        with self.assertRaises(ValueError):frame_visible_bounds([(0,0,1,1)],0,400)
        with self.assertRaises(ValueError):frame_visible_bounds([(0,0,1,1)],100,400,min_zoom=2,max_zoom=1)


if __name__ == '__main__':unittest.main()
