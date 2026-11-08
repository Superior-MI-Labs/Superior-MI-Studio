"""The established page-to-view registry owns graph-tab close dispatch."""
import ast
import unittest
from pathlib import Path
from studio_native.navigation import GraphViewSessions, Route

ROOT=Path(__file__).resolve().parents[1]
TREE=ast.parse((ROOT/'studio_native/gui.py').read_text(encoding='utf-8'))
UI=next(x for x in TREE.body if isinstance(x,ast.ClassDef) and x.name=='NativeLab')
CLOSE=next(x for x in UI.body if isinstance(x,ast.FunctionDef) and x.name=='_close_graph_tab')
CODE=ast.unparse(CLOSE)


class TabCloseLookupTests(unittest.TestCase):
    def test_close_uses_single_existing_page_registry_lookup(self):
        self.assertIn('view = self._graph_tab_for_page(page)',CODE)
        self.assertNotIn('next((v for v in self._source_tabs.values()',CODE)
        self.assertNotIn('next((v for v in self._resource_tabs.values()',CODE)
        self.assertIn('isinstance(view, ProgramWorkspace)',CODE)
        self.assertIn('isinstance(view, ResourceTabView)',CODE)
        self.assertIn('isinstance(view, SourceTabView)',CODE)

    def test_protected_roots_and_session_close_remain(self):
        self.assertIn("view.session_id == 'source'",CODE)
        self.assertIn("resource.session_id == 'resource'",CODE)
        self.assertIn('self._view_sessions.close(resource.session_id)',CODE)
        self.assertIn('self._view_sessions.close(view.session_id)',CODE)
        sessions=GraphViewSessions()
        root=sessions.open('resource',Route('resource','/tmp'))
        secondary=sessions.open('resource:2',Route('resource','/tmp'))
        self.assertTrue(sessions.close('resource:2'))
        self.assertIsNone(sessions.get('resource:2'))
        self.assertIs(sessions.get('resource'),root)
        self.assertIsNot(root,secondary)

    def test_native_smoke_checks_inactive_page_and_selected_root(self):
        source=(ROOT/'studio_native/qt_smoke.py').read_text(encoding='utf-8')
        self.assertIn('QT_STAGE inactive-resource-view-close-preserves-root',source)
        self.assertIn('assert w.tabs.currentWidget() is root_resource_page',source)
        self.assertIn("assert w._resource_tabs['resource'] is root_resource",source)
        self.assertIn("assert w._view_sessions.get('resource').route==root_route_before",source)


if __name__=='__main__':unittest.main()
