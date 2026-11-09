"""No second active-view owner: three pathways reuse one binding adapter."""
import ast
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TREE=ast.parse((ROOT/'studio_native/gui.py').read_text(encoding='utf-8'))
UI=next(x for x in TREE.body if isinstance(x,ast.ClassDef) and x.name=='NativeLab')
SMOKE=(ROOT/'studio_native/qt_smoke.py').read_text(encoding='utf-8')


def body(name):
    return ast.unparse(next(x for x in UI.body if isinstance(x,ast.FunctionDef) and x.name==name))


class ActiveViewAliasTests(unittest.TestCase):
    def test_existing_provider_owners_remain_and_binding_is_idempotent(self):
        source=body('_bind_selected_graph_view')
        self.assertIn('isinstance(view, ResourceTabView)',source)
        self.assertIn('isinstance(view, SourceTabView)',source)
        self.assertIn('self._active_resource_tab_id == view.session_id',source)
        self.assertIn('self._active_source_tab_id == view.session_id',source)
        self.assertIn('self._store_active_resource_view()',source)
        self.assertIn('self._activate_resource_view(view)',source)
        self.assertIn('self._store_active_source_view()',source)
        self.assertIn('self._activate_source_view(view)',source)
        self.assertIn('self._refresh_live_source()',source)

    def test_signal_and_navigation_share_binding_not_local_duplicates(self):
        for name in ('_workspace_tab_changed','_open_navigation_route','_navigate_history'):
            code=body(name)
            self.assertIn('self._bind_selected_graph_view(',code,name)
            selected_path=(code.split("root = self._source_tabs['source']",1)[0]
                           if name=='_open_navigation_route' else code)
            self.assertNotIn('self._store_active_resource_view()',selected_path,name)
            self.assertNotIn('self._store_active_source_view()',selected_path,name)
        # The uninitialized source-root exception uses the original source
        # loader, which defers binding until after preflight. No navigation
        # call site may activate a non-selected root prematurely.
        self.assertIn("self._open_python_source_path(route.path, bootstrap_root=True)",
                      body('_open_navigation_route'))
        self.assertNotIn("self._activate_source_view(root)",body('_open_navigation_route'))
        self.assertIn("if bootstrap_root and self._active_source_tab_id != 'source':",
                      body('_open_python_source_path'))

    def test_qt_smoke_checks_real_tab_selection_without_history_mutation(self):
        self.assertIn('QT_STAGE selected-graph-view-binding-idempotence',SMOKE)
        self.assertIn('assert w._bind_selected_graph_view(root_resource_view) is False',SMOKE)
        self.assertIn('assert w._bind_selected_graph_view(python_root) is False',SMOKE)
        self.assertIn('assert source_history.route==source_route',SMOKE)
        self.assertIn('assert root_history.route==root_route',SMOKE)
        self.assertIn("assert w._source_tabs['source'].document is first_doc",SMOKE)


if __name__=='__main__':unittest.main()
