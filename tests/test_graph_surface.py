"""Qt-free regression of the recursive graph viewport/camera contract."""
import tempfile
import unittest
from pathlib import Path
from studio_native.graph_surface import GraphSurfaceState, MIN_ZOOM, MAX_ZOOM
from studio_native.python_graph import PythonDocument


SOURCE = '''\ndef outer(n):
    def inner(v):
        return n + v
    return inner(n)

def count(n):
    while n > 0:
        n -= 1
    return n
'''


class GraphSurfaceGeometryTests(unittest.TestCase):
    def test_camera_can_pan_into_empty_space_after_fitting(self):
        state=GraphSurfaceState(200,100,600,300)
        state.pan(-10000,-10000)
        self.assertEqual((state.offset_x,state.offset_y),(-10000.,-10000.))
        state.pan(10005,10013)
        self.assertEqual((state.offset_x,state.offset_y),(5.,13.))
        state.fit_contents()
        state.pan(30,30)
        self.assertNotEqual((state.offset_x,state.offset_y),
                            ((state.viewport_width-state.content_width*state.zoom)/2,
                             (state.viewport_height-state.content_height*state.zoom)/2))

    def test_pointer_anchored_zoom_and_roundtrip(self):
        state=GraphSurfaceState(200,100,600,300)
        state.pan(-80,-30)
        before=state.map_to_content(95,60)
        state.zoom_at(1.2,95,60)
        after=state.map_to_content(95,60)
        self.assertAlmostEqual(before[0],after[0]);self.assertAlmostEqual(before[1],after[1])
        self.assertEqual(tuple(round(x,6) for x in state.view_position(*after)),(95,60))

    def test_nested_cameras_are_independent(self):
        root=GraphSurfaceState(1200,800,3000,2000)
        inner=GraphSurfaceState(250,150,600,400)
        inner.pan(-20,-30);inner.zoom_at(1.4,100,70)
        self.assertEqual((root.offset_x,root.offset_y,root.zoom),(0,0,1))
        self.assertNotEqual((inner.offset_x,inner.offset_y,inner.zoom),(0,0,1))

    def test_fit_contents_initially_displays_entire_region(self):
        for dims in [(650,320,1500,1200),(250,120,400,280),(200,120,180,100)]:
            state=GraphSurfaceState(*dims)
            state.fit_contents()
            self.assertLessEqual(state.content_width*state.zoom,state.viewport_width+0.01)
            self.assertLessEqual(state.content_height*state.zoom,state.viewport_height+0.01)
            self.assertTrue(abs(state.offset_x)<max(state.viewport_width,state.content_width))
            self.assertTrue(abs(state.offset_y)<max(state.viewport_height,state.content_height))

    def test_resize_is_presentation_only_and_camera_remains_valid(self):
        state=GraphSurfaceState(300,160,540,300)
        state.fit_contents()
        zoom=state.zoom
        state.resize_viewport(760,440)
        self.assertEqual(state.zoom,zoom)
        self.assertEqual((state.content_width,state.content_height),(540,300))
        self.assertEqual((state.viewport_width,state.viewport_height),(760,440))
        with self.assertRaises(ValueError):state.resize_viewport(-5,300)

    def test_bounds_and_invalid_input(self):
        state=GraphSurfaceState(200,100,400,200)
        state.zoom_at(100000,50,40);self.assertEqual(state.zoom,MAX_ZOOM)
        state.zoom_at(.0000001,50,40);self.assertEqual(state.zoom,MIN_ZOOM)
        state.ensure_extent(2000,1000)
        self.assertEqual((state.content_width,state.content_height),(2000,1000))
        with self.assertRaises(ValueError):state.zoom_at(float('nan'),0,0)
        with self.assertRaises(ValueError):GraphSurfaceState(0,1,2,3)


class RecursiveProjectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.source=Path(self.tmp.name)/'example.py';self.source.write_text(SOURCE)
        self.doc=PythonDocument(self.source)
        self.expanded=set(self.doc.scopes)-{'module'}

    def tearDown(self):self.tmp.cleanup()

    def test_every_expanded_scope_is_bounded_surface_with_local_nodes(self):
        graph=self.doc.composite_file_graph(self.expanded)
        owners={node['source_scope']:node for node in graph['nodes'] if node.get('source_scope')}
        self.assertEqual(set(owners),self.expanded)
        for key,owner in owners.items():
            region=owner['embedded_region']
            self.assertLessEqual(region['viewport_width'],810)
            self.assertLessEqual(region['viewport_height'],425)
            self.assertGreater(region['height'],region['surface_top'])
            self.assertEqual(region['width'],region['viewport_width']+12)
            for child in graph['nodes']:
                if child.get('containing_scope')!=key:continue
                self.assertGreaterEqual(child['x'],0)
                self.assertGreaterEqual(child['y'],0)
                self.assertLess(child['x'],region['content_width'])
                self.assertLess(child['y'],region['content_height'])

    def test_visual_camera_has_no_effect_on_python_semantics(self):
        before=self.doc.whole_file_graph(self.expanded,detail='readable')
        after=self.doc.composite_file_graph(self.expanded)
        self.assertEqual({n['id'] for n in before['nodes']},{n['id'] for n in after['nodes']})
        self.assertEqual({e['id'] for e in before['edges']},{e['id'] for e in after['edges']})
        self.assertEqual(self.source.read_text(),SOURCE)


if __name__=='__main__':unittest.main()
