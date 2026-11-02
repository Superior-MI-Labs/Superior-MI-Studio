"""Qt-free minimap geometry and per-session route identity regressions."""
import unittest
from studio_native.graph_surface import overview_viewport_size
from studio_native.navigation import GraphViewSessions,Route,root_camera_slot

class ViewportGeometryTests(unittest.TestCase):
    def test_new_viewport_geometry_replaces_stale_large_tab_coordinates(self):
        old=overview_viewport_size(3061,2040)
        current=overview_viewport_size(809,789)
        self.assertEqual(old,(228,154))
        self.assertEqual(current,(228,154))
        # Position is no longer computed in application code. Qt owns it.

    def test_small_tab_never_clips_overlay(self):
        for width in (0,50,100,115,116,119,120,150,240,300,809):
            for height in (0,40,70,90,96,160,210,789):
                result=overview_viewport_size(width,height)
                if result is None:
                    self.assertTrue(width<120 or height<96)
                    continue
                w,h=result
                self.assertLessEqual(w+24,width)
                self.assertLessEqual(h+24,height)
                self.assertGreaterEqual(w,96)
                self.assertGreaterEqual(h,72)

    def test_overview_geometry_refuses_invalid_values(self):
        for width,height in ((-1,200),(200,-1),(float('nan'),200),(200,float('inf'))):
            with self.assertRaises(ValueError):overview_viewport_size(width,height)

class SessionCameraTests(unittest.TestCase):
    def test_current_route_owns_camera_slot_across_history(self):
        store=GraphViewSessions()
        start=Route('resource','/tmp')
        source=Route('source','/tmp/demo.py')
        a=store.open('tab-1',start)
        b=store.open('tab-2',source)
        self.assertEqual(a.camera_slot(),root_camera_slot('tab-1',start))
        self.assertNotEqual(a.camera_slot(),b.camera_slot())
        a.visit(source)
        self.assertEqual(a.camera_slot(),root_camera_slot('tab-1',source))
        self.assertNotEqual(a.camera_slot(),b.camera_slot())
        self.assertTrue(a.commit_history_move(-1,start))
        self.assertEqual(a.camera_slot(),root_camera_slot('tab-1',start))

if __name__=='__main__':unittest.main()
