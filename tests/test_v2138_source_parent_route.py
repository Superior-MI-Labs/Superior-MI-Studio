"""Source parent navigation must use the selected tab's provider session."""
import ast
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
UI=next(n for n in ast.parse((ROOT/'studio_native/gui.py').read_text()).body
        if isinstance(n,ast.ClassDef) and n.name=='NativeLab')
SMOKE=(ROOT/'studio_native/qt_smoke.py').read_text(encoding='utf-8')

def code(name):
    return ast.unparse(next(n for n in UI.body if isinstance(n,ast.FunctionDef)
                            and n.name==name))

class SourceParentNavigationTests(unittest.TestCase):
    def test_whole_source_go_parent_uses_canonical_route_dispatch(self):
        parent=code('source_go_parent')
        self.assertIn("self._open_navigation_route(Route('resource', str(self.python_doc.path.parent)))",parent)
        self.assertNotIn('self.browse_resource(',parent)
        self.assertIn("if self.source_view_mode == 'whole':",parent)
        self.assertIn('self.navigate_source(parent)',parent)

    def test_shared_dispatch_preserves_both_root_and_secondary_policy(self):
        route=code('_open_navigation_route')
        self.assertIn('return self._transition_graph_tab(route)',route)
        self.assertIn('return self.browse_resource(route.path, root_anchor=True)',route)
        self.assertLess(route.index('self._transition_graph_tab(route)'),
                        route.index('self.browse_resource(route.path, root_anchor=True)'))

    def test_native_source_parent_history_and_root_isolation(self):
        self.assertIn('QT_STAGE source-parent-uses-selected-graph-session',SMOKE)
        for marker in (
            'assert w.source_go_parent()',
            "assert sid in w._resource_tabs and sid not in w._source_tabs",
            "assert session.peek(-1)==Route('source',str(script))",
            "assert w._view_sessions.get('resource').route==root_resource_route",
            "assert w._view_sessions.get('source').route==root_source_route",
            "assert w._navigate_history('resource',-1)",
            'assert w._view_sessions.get(sid) is None',
        ):
            self.assertIn(marker,SMOKE)

if __name__=='__main__':unittest.main()
