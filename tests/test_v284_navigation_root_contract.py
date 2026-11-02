"""History owns destinations; source sessions own revisions; routes never revive dead scopes.

These tests exercise the exact contract behind repeated v2.82/v2.83 Qt
failures without substituting an on-disk PythonDocument for a live draft.
"""
import ast
import tempfile
from pathlib import Path
import unittest

from studio_native.graph_routes import (
    GraphRouteError, resolve_source_session_route,
)
from studio_native.navigation import GraphViewSessions, Route
from studio_native.source_editor import SourceDocumentSession

ROOT=Path(__file__).resolve().parents[1]


class NavigationSourceOwnerContract(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix='studio-history-owner-')
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.path=self.root/'demo.py'
        self.saved='def before():\n    return 1\n'
        self.draft='def unsaved():\n    return 2\n'
        self.path.write_text(self.saved)
        self.owner=SourceDocumentSession.open(self.path)
        self.workspace=Route('resource',str(self.root))
        self.session=GraphViewSessions().open('secondary',self.workspace)

    def focused_route(self):
        scope=next(key for key,value in self.owner.parsed.scopes.items()
                   if value.title=='unsaved')
        return Route('source',str(self.path),scope,'focus')

    def test_rejected_invalid_and_deleted_scopes_do_not_move_history(self):
        self.owner.update(self.draft)
        focused=self.focused_route()
        self.assertEqual(resolve_source_session_route(focused,self.owner).route,focused)
        self.session.activate(focused)
        self.session.activate(self.workspace,history_direction=-1)
        self.assertEqual(self.session.peek(1),focused)
        original_camera=self.session.camera_slot()
        entries=list(self.session.history._entries)
        index=self.session.history._position

        self.owner.update('def invalid(:\n')
        self.assertFalse(self.owner.graph_ready)
        with self.assertRaisesRegex(GraphRouteError,'no qualified graph'):
            resolve_source_session_route(focused,self.owner)
        self.assertEqual(self.session.history._entries,entries)
        self.assertEqual(self.session.history._position,index)
        self.assertEqual(self.session.camera_slot(),original_camera)

        # This valid edit deletes the focused function. Its historical route
        # remains a valid *history entry*, but is not an executable destination.
        self.owner.update(self.saved)
        self.assertTrue(self.owner.graph_ready)
        with self.assertRaisesRegex(GraphRouteError,'scope is not present'):
            resolve_source_session_route(focused,self.owner)
        self.assertEqual(self.session.history._entries,entries)
        self.assertEqual(self.session.history._position,index)
        self.assertEqual(self.session.camera_slot(),original_camera)

        self.owner.update(self.draft)
        resolved=resolve_source_session_route(focused,self.owner)
        self.session.activate(resolved.route,history_direction=1)
        self.assertEqual(self.session.route,focused)
        self.assertEqual(self.path.read_text(),self.saved)

    def test_never_falls_back_to_saved_source_when_draft_is_invalid(self):
        self.owner.update('def unusable(:\n')
        with self.assertRaisesRegex(GraphRouteError,'no qualified graph'):
            resolve_source_session_route(Route('source',str(self.path)),self.owner)
        self.assertEqual(self.path.read_text(),self.saved)

    def test_live_draft_can_qualify_focus_absent_on_disk(self):
        self.owner.update(self.draft)
        resolved=resolve_source_session_route(self.focused_route(),self.owner)
        self.assertIn('unsaved',resolved.document.source)
        self.assertEqual(self.path.read_text(),self.saved)

    def test_wrong_owner_and_cross_provider_routes_rejected(self):
        self.owner.update(self.draft)
        other=self.root/'different.py'
        other.write_text(self.saved)
        with self.assertRaisesRegex(GraphRouteError,'owner does not match'):
            resolve_source_session_route(Route('source',str(other)),self.owner)
        with self.assertRaisesRegex(GraphRouteError,'only source routes'):
            resolve_source_session_route(self.workspace,self.owner)

    def test_source_history_remains_single_session_across_file_changes(self):
        other=self.root/'second.py'
        other.write_text('def another():\n    return 3\n')
        second_owner=SourceDocumentSession.open(other)
        route_a=resolve_source_session_route(Route('source',str(self.path)),self.owner).route
        route_b=resolve_source_session_route(Route('source',str(other)),second_owner).route
        self.session.activate(route_a)
        self.session.activate(route_b)
        self.assertEqual(self.session.peek(-1),route_a)
        self.session.activate(route_a,history_direction=-1)
        self.session.activate(route_b,history_direction=1)
        self.assertEqual(self.session.session_id,'secondary')
        self.assertIsNot(self.owner,second_owner)

    def test_gui_uses_one_live_route_preflight_for_both_navigation_paths(self):
        tree=ast.parse((ROOT/'studio_native/gui.py').read_text())
        ui=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='NativeLab')
        def fn(name):
            return next(n for n in ui.body if isinstance(n,ast.FunctionDef) and n.name==name)
        def calls(name,target):
            return any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and
                       n.func.attr==target for n in ast.walk(fn(name)))
        self.assertTrue(calls('_transition_graph_tab','_resolve_live_source_route'))
        self.assertTrue(calls('_navigate_source_document_in_tab','_resolve_live_source_route'))
        self.assertTrue(calls('_navigate_history','_navigate_source_document_in_tab'))
        self.assertIn('resolve_source_session_route',ast.unparse(fn('_resolve_live_source_route')))
        # The failed Qt regression is now an explicit expectation of refusal
        # on a valid-but-renamed scope, not a suppressed assertion.
        smoke=(ROOT/'studio_native/qt_smoke.py').read_text()
        self.assertIn("assert not w._navigate_history('resource',1)",smoke)
        self.assertIn('restoring the same scope identity',smoke)


if __name__=='__main__':unittest.main()
