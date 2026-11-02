"""The overview drag's scene offset must not become a second graph camera."""
import unittest
from studio_native.graph_surface import overview_map,overview_drag_offset

class OverviewDragTests(unittest.TestCase):
    def setUp(self):
        self.projection=overview_map([(0,0,150,80),(1100,600,200,100)],228,154)
        self.viewport=(100.,200.,220.,170.)

    def test_inside_viewport_grab_preserves_camera_center(self):
        model=self.projection
        old_center=(self.viewport[0]+self.viewport[2]/2,
                    self.viewport[1]+self.viewport[3]/2)
        pointer_scene=(self.viewport[0]+30,self.viewport[1]+40)
        pos=model.to_map(*pointer_scene)
        offset=overview_drag_offset(model,self.viewport,pos)
        scene=model.to_scene(*pos)
        self.assertAlmostEqual(scene[0]+offset[0],old_center[0])
        self.assertAlmostEqual(scene[1]+offset[1],old_center[1])
        moved=(pos[0]+10,pos[1]+5)
        new_scene=model.to_scene(*moved)
        self.assertAlmostEqual(new_scene[0]+offset[0]-old_center[0],10/model.scale)
        self.assertAlmostEqual(new_scene[1]+offset[1]-old_center[1],5/model.scale)

    def test_click_outside_box_jumps_to_clicked_location(self):
        point=self.projection.to_map(1000,600)
        self.assertEqual(overview_drag_offset(self.projection,self.viewport,point),(0.,0.))
        self.assertAlmostEqual(self.projection.to_scene(*point)[0],1000)

    def test_invalid_rectangles_fail_closed(self):
        with self.assertRaises(ValueError):overview_drag_offset(self.projection,(1,2,0,40),(5,5))
        with self.assertRaises(ValueError):overview_drag_offset(self.projection,(1,2,30,40),(float('nan'),5))
        with self.assertRaises(TypeError):overview_drag_offset(None,self.viewport,(4,5))

if __name__=='__main__':unittest.main()
