"""A last-active provider alias is not permission to steal Qt foreground focus."""
import ast
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TREE=ast.parse((ROOT/'studio_native/gui.py').read_text(encoding='utf-8'))
UI=next(x for x in TREE.body if isinstance(x,ast.ClassDef) and x.name=='NativeLab')
CLOSE=ast.unparse(next(x for x in UI.body if isinstance(x,ast.FunctionDef) and x.name=='_close_graph_tab'))
SMOKE=(ROOT/'studio_native/qt_smoke.py').read_text(encoding='utf-8')


class ForegroundClosePolicyTests(unittest.TestCase):
    def test_closing_provider_alias_may_not_select_its_root_when_tab_inactive(self):
        self.assertIn('closing_selected = self.tabs.currentWidget() is page',CLOSE)
        self.assertEqual(CLOSE.count('if closing_selected:'),2)
        self.assertEqual(CLOSE.count('self.tabs.setCurrentWidget(target.page)'),2)
        self.assertIn('self._activate_resource_view(target)',CLOSE)
        self.assertIn('self._activate_source_view(target)',CLOSE)

    def test_protected_roots_and_session_ownership_not_changed(self):
        self.assertIn("resource.session_id == 'resource'",CLOSE)
        self.assertIn("view.session_id == 'source'",CLOSE)
        self.assertIn('self._view_sessions.close(resource.session_id)',CLOSE)
        self.assertIn('self._view_sessions.close(view.session_id)',CLOSE)
        self.assertIn('if isinstance(view, ProgramWorkspace):',CLOSE)
        self.assertIn('if not view.confirm_close():',CLOSE)

    def test_real_qt_stage_tests_both_cross_provider_inactive_close_cases(self):
        self.assertIn('QT_STAGE inactive-other-provider-close-preserves-foreground',SMOKE)
        self.assertIn('assert w._active_source_tab_id==source_sid',SMOKE)
        self.assertIn('assert w._active_resource_tab_id==resource_sid',SMOKE)
        self.assertIn('assert w.tabs.currentWidget() is root_resource_page',SMOKE)
        self.assertIn('assert w.tabs.currentWidget() is python_root.page',SMOKE)
        self.assertIn("assert w._active_source_tab_id=='source'",SMOKE)
        self.assertIn("assert w._active_resource_tab_id=='resource'",SMOKE)


if __name__=='__main__':unittest.main()
