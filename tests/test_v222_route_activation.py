"""Route/camera authority: regress host focus/whole mismatch without Qt."""
import tempfile
import unittest
from pathlib import Path

from studio_native.navigation import Route, GraphViewSession, GraphViewSessions
from studio_native.graph_routes import resolve_graph
from studio_native.python_graph import PythonDocument


class RouteActivationTests(unittest.TestCase):
    def test_focus_and_whole_refresh_use_the_route_actually_displayed(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'sample.py'
            path.write_text('def f(x):\n    return x\n', encoding='utf-8')
            document = PythonDocument(path)
            focus_scope = next(k for k,v in document.scopes.items() if v.title=='f')
            whole = Route('source',str(path))
            focus = Route('source',str(path),focus_scope,'focus')
            sessions = GraphViewSessions()
            session = sessions.open('source',focus)
            focus_camera = session.camera_slot()
            before = path.read_bytes()
            displayed = resolve_graph(whole,document=document)
            session.activate(displayed.route,record_history=False)
            self.assertEqual(session.route,whole)
            whole_camera = session.camera_slot()
            self.assertNotEqual(focus_camera,whole_camera)
            displayed = resolve_graph(focus,document=document)
            session.activate(displayed.route,record_history=False)
            self.assertEqual(session.route,focus)
            self.assertEqual(session.camera_slot(),focus_camera)
            self.assertEqual(before,path.read_bytes())

    def test_back_forward_commits_selected_route_not_previous_route(self):
        start = Route('resource','/tmp')
        target = Route('resource','/tmp/dir')
        session = GraphViewSession('workspace',start)
        session.activate(target)
        before = session.camera_slot()
        self.assertTrue(session.activate(start,record_history=False,history_direction=-1))
        self.assertEqual(session.route,start)
        self.assertNotEqual(session.camera_slot(),before)
        self.assertEqual(session.peek(1),target)
        self.assertTrue(session.activate(target,record_history=False,history_direction=1))
        self.assertEqual(session.route,target)
        self.assertEqual(session.camera_slot(),before)

    def test_repeated_refresh_preserves_forward_back_navigation(self):
        a,b = Route('resource','/a'),Route('resource','/b')
        session=GraphViewSession('workspace',a)
        session.activate(b)
        session.activate(a,record_history=False,history_direction=-1)
        self.assertFalse(session.activate(a,record_history=False))
        self.assertEqual(session.peek(1),b)
        self.assertIsNone(session.peek(-1))

    def test_unrecorded_new_route_replaces_current_without_leaving_stale_history(self):
        a,b,c = (Route('resource','/'+name) for name in 'abc')
        session=GraphViewSession('workspace',a)
        session.activate(b)
        session.activate(a,record_history=False,history_direction=-1)
        session.activate(c,record_history=False)
        self.assertEqual(session.route,c)
        self.assertEqual(session.camera_slot()[0],'/c')
        self.assertIsNone(session.peek(1))
        self.assertIsNone(session.peek(-1))

    def test_failed_or_unresolved_history_destination_never_moves_state(self):
        a,b,c=(Route('resource','/'+name) for name in 'abc')
        session=GraphViewSession('workspace',a)
        session.activate(b)
        key=session.camera_slot()
        with self.assertRaises(ValueError):session.activate(c,record_history=False,history_direction=-1)
        self.assertEqual(session.route,b)
        self.assertEqual(session.camera_slot(),key)
        with self.assertRaises(ValueError):session.activate(a,history_direction=0)
        self.assertEqual(session.route,b)
        with self.assertRaises(TypeError):session.activate('not a Route',record_history=False)
        self.assertEqual(session.route,b)

    def test_multiple_tabs_keep_their_own_routes(self):
        store=GraphViewSessions()
        left=store.open('left',Route('resource','/tmp'))
        right=store.open('right',Route('source','/tmp/a.py'))
        right_key=right.camera_slot()
        left.activate(Route('source','/tmp/a.py'),record_history=False)
        self.assertNotEqual(left.camera_slot(),right_key)
        self.assertEqual(right.route.mode,'whole')


if __name__=='__main__':unittest.main()
