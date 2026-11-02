"""The overview shares scene geometry and cannot change graph meaning."""
import math
import unittest
from studio_native.graph_surface import overview_map


class OverviewGeometryTests(unittest.TestCase):
    def test_roundtrip_and_stable_projection_across_camera_moves(self):
        nodes=[(0.0,5.0,150.0,70.0),(1300.0,250.0,260.0,230.0)]
        map1=overview_map(nodes,228,154)
        map2=overview_map(nodes,228,154) # camera is not an argument by design
        self.assertEqual(map1,map2)
        for x,y in [(0,0),(320,80),(1200,-400),(-12.5,400.25)]:
            mx,my=map1.to_map(x,y)
            sx,sy=map1.to_scene(mx,my)
            self.assertAlmostEqual(x,sx,places=8)
            self.assertAlmostEqual(y,sy,places=8)

    def test_projection_preserves_rectangles_as_scene_coordinates(self):
        node=(15,50,125,75)
        model=overview_map([node],210,145)
        mx,my,mw,mh=model.project_rect(node)
        self.assertTrue(0 <= mx < 210)
        self.assertTrue(0 <= my < 145)
        self.assertGreater(mw,0)
        self.assertGreater(mh,0)
        self.assertAlmostEqual(mw/model.scale,node[2])
        self.assertAlmostEqual(mh/model.scale,node[3])

    def test_empty_map_is_noop_without_fake_scene_nodes(self):
        self.assertIsNone(overview_map([],228,154))
        self.assertIsNone(overview_map(iter(()),228,154))

    def test_invalid_geometry_rejected_without_silent_fallback(self):
        for rectangles in [[(0,0,0,50)],[(1,2,3,math.inf)],[(0,0,10)],[(3,4,10,-2)]]:
            with self.subTest(rectangles=rectangles), self.assertRaises(ValueError):
                overview_map(rectangles,228,154)
        for width,height in [(0,154),(228,1),(math.nan,154),(228,-10)]:
            with self.subTest(size=(width,height)), self.assertRaises(ValueError):
                overview_map([(0,0,10,10)],width,height)

    def test_node_extent_not_camera_extent(self):
        model=overview_map([(0,0,100,50),(1000,500,100,50)],228,154)
        # An offscreen viewport can extend past the map, but it never moves
        # the nodes or changes mapping when the user pans far away.
        self.assertEqual(model,overview_map([(0,0,100,50),(1000,500,100,50)],228,154))
        self.assertGreater(model.scale,0)

if __name__=='__main__':unittest.main()
