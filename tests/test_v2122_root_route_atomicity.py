"""v2.122: root-provider navigation validates before changing its Qt route.

Native smoke supplies actual widget/camera and dirty-source evidence. These
headless checks characterize the ownership boundary without importing PyQt6.
"""
import ast
import tempfile
import unittest
from pathlib import Path

from studio_native.graph_routes import GraphRouteError, resolve_source_session_route
from studio_native.navigation import GraphViewSessions, Route
from studio_native.source_editor import SourceDocumentSession

ROOT = Path(__file__).resolve().parents[1]
UI = next(node for node in ast.parse((ROOT/'studio_native/gui.py').read_text()).body
          if isinstance(node, ast.ClassDef) and node.name == 'NativeLab')


def method(name):
    return next(node for node in UI.body
                if isinstance(node, ast.FunctionDef) and node.name == name)


def call_line(function, name):
    matches = [node.lineno for node in ast.walk(function)
               if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
               and node.func.attr == name]
    return matches


class RootNavigationAtomicityTests(unittest.TestCase):
    def test_root_source_uses_existing_transaction_not_early_qt_switch(self):
        route = method('_open_navigation_route')
        result = ast.unparse(route)
        self.assertIn('root_anchor=True', result)
        # Only the original never-opened source view may use the legacy file
        # picker adapter. A loaded root must share the live-source resolver.
        self.assertLess(result.index("self._view_sessions.get('source')"),
                        result.index("self._open_python_source_path(route.path, bootstrap_root=True)"))
        # Initial root activation now occurs inside the same source loader
        # after its existing preflight, never in the route dispatcher.
        self.assertNotIn('self._activate_source_view(root)',result)
        commit = method('_navigate_source_document_in_tab')
        self.assertIn('root_anchor', ast.unparse(commit))
        self.assertLess(min(call_line(commit, '_resolve_live_source_route')),
                        min(call_line(commit, 'setCurrentWidget')))
        self.assertLess(min(call_line(commit, '_resolve_live_source_route')),
                        min(call_line(commit, '_store_active_source_view')))
        self.assertLess(min(call_line(commit, 'setCurrentWidget')),
                        min(call_line(commit, 'activate')))

    def test_cross_provider_qualifies_qt_membership_before_mutating_registries(self):
        transition = method('_transition_graph_tab')
        contents = ast.unparse(transition)
        self.assertLess(contents.index('index = self.tabs.indexOf(old.page)'),
                        contents.index('self._source_documents[str(source_session.path)]'))
        self.assertLess(contents.index('index = self.tabs.indexOf(old.page)'),
                        contents.index('del self._source_tabs[old.session_id]'))
        self.assertIn('selected tab is no longer present', contents)

    def test_deleted_or_invalid_focus_never_commits_root_history(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'sample.py'
            text = 'def available():\n    return 1\n'
            path.write_text(text)
            owner = SourceDocumentSession.open(path)
            focus = next(key for key, scope in owner.parsed.scopes.items()
                         if scope.title == 'available')
            root = Route('resource', str(path.parent))
            routes = GraphViewSessions()
            source = routes.open('source', Route('source', str(path)))
            resource = routes.open('resource', root)
            before = (source.route, source.peek(-1), resource.route,
                      tuple(source.history._entries), source.history._position,
                      source.camera_slot())
            with self.assertRaisesRegex(GraphRouteError, 'scope is not present'):
                resolve_source_session_route(Route('source', str(path), 'absent', 'focus'), owner)
            owner.update('def other():\n    return 2\n')
            with self.assertRaisesRegex(GraphRouteError, 'scope is not present'):
                resolve_source_session_route(Route('source', str(path), focus, 'focus'), owner)
            owner.update('def broken(:\n')
            with self.assertRaisesRegex(GraphRouteError, 'no qualified graph'):
                resolve_source_session_route(Route('source', str(path), focus, 'focus'), owner)
            after = (source.route, source.peek(-1), resource.route,
                     tuple(source.history._entries), source.history._position,
                     source.camera_slot())
            self.assertEqual(before, after)
            self.assertEqual(path.read_text(), text)

    def test_native_smoke_exercises_actual_refusal(self):
        smoke = (ROOT/'studio_native/qt_smoke.py').read_text()
        self.assertIn('QT_STAGE protected-root-source-refusal-atomicity', smoke)
        self.assertIn('assert w.tabs.currentWidget() is resource_root_page', smoke)
        self.assertIn('assert w._active_source_tab_id==source_alias_before', smoke)


if __name__ == '__main__':
    unittest.main()
