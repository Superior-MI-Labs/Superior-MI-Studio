"""Protected filesystem root must not navigate the last-active secondary resource tab."""
import ast
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TREE=ast.parse((ROOT/'studio_native/gui.py').read_text(encoding='utf-8'))
LAB=next(n for n in TREE.body if isinstance(n,ast.ClassDef) and n.name=='NativeLab')
SMOKE=(ROOT/'studio_native/qt_smoke.py').read_text(encoding='utf-8')

def method(name):
    return ast.unparse(next(n for n in LAB.body if isinstance(n,ast.FunctionDef)
                            and n.name==name))

class ResourceRootRouteTests(unittest.TestCase):
    def test_dispatch_explicitly_targets_root_only_from_source_anchor(self):
        route=method('_open_navigation_route')
        self.assertIn('self.browse_resource(route.path, root_anchor=True)',route)
        self.assertIn('self._bind_selected_graph_view(selected)',route)
        self.assertIn('return self.browse_resource(route.path)',route)
        self.assertLess(route.index('self._transition_graph_tab(route)'),
                        route.index('self.browse_resource(route.path, root_anchor=True)'))
        self.assertLess(route.index('if new_tab:'),
                        route.index('self.browse_resource(route.path, root_anchor=True)'))

    def test_provider_resolves_target_root_preferences_before_binding(self):
        browse=method('browse_resource')
        self.assertIn('root_anchor=False',browse)
        self.assertIn("self._resource_tabs['resource'] if root_anchor else None",browse)
        self.assertIn('root.relationship_layers if root is not None',browse)
        self.assertIn('root.expanded if root is not None',browse)
        self.assertIn('root.relationship_direction if root is not None',browse)
        self.assertLess(browse.index('graph = resolve_graph('),
                        browse.index("if root_anchor and self._active_resource_tab_id != 'resource':"))
        self.assertIn("self._activate_resource_view(self._resource_tabs['resource'], reproject=False)",browse)
        self.assertLess(browse.index('if root_anchor and self._active_resource_tab_id'),
                        browse.index('self._active_resource_session().activate('))

    def test_prequalified_root_binding_does_not_reparse_stale_previous_path(self):
        activate=method('_activate_resource_view')
        self.assertIn('reproject=True',activate)
        self.assertIn('if reproject and',activate)
        self.assertIn("if reproject:\n        self._refresh_navigation('resource')",activate)

    def test_native_stage_proves_refusal_success_and_secondary_independence(self):
        self.assertIn('QT_STAGE source-root-resource-anchor-isolation',SMOKE)
        for marker in (
            'assert w._active_resource_tab_id==extra_sid',
            "assert w._active_resource_tab_id=='resource'",
            "assert w.tabs.currentWidget() is resource_root.page",
            'assert extra_view.path==extra_path',
            'assert extra_history.route==extra_route and extra_history.camera_slot()==extra_camera',
            'assert w._view_sessions.get(extra_sid) is None',
        ):
            self.assertIn(marker,SMOKE)

if __name__=='__main__':unittest.main()
