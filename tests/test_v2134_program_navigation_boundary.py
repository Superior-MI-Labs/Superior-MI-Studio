"""Program-owned tabs must not impersonate resource/source navigation views."""
import ast
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TREE=ast.parse((ROOT/'studio_native/gui.py').read_text(encoding='utf-8'))
UI=next(n for n in TREE.body if isinstance(n,ast.ClassDef) and n.name=='NativeLab')
PROGRAM=next(n for n in TREE.body if isinstance(n,ast.ClassDef) and n.name=='ProgramWorkspace')
ROUTE=ast.unparse(next(n for n in UI.body
    if isinstance(n,ast.FunctionDef) and n.name=='_open_navigation_route'))
SMOKE=(ROOT/'studio_native/qt_smoke.py').read_text(encoding='utf-8')


class ProgramNavigationBoundaryTests(unittest.TestCase):
    def test_native_program_does_not_own_provider_session_identity(self):
        assigned={n.attr for method in PROGRAM.body if isinstance(method,ast.FunctionDef)
                  for n in ast.walk(method)
                  if isinstance(n,ast.Attribute) and isinstance(n.ctx,ast.Store)
                  and isinstance(n.value,ast.Name) and n.value.id=='self'}
        self.assertNotIn('session_id',assigned)

    def test_selected_tab_type_is_checked_before_session_access(self):
        guard='if not isinstance(selected, (ResourceTabView, SourceTabView)):'
        self.assertIn(guard,ROUTE)
        self.assertLess(ROUTE.index(guard),ROUTE.index('selected.session_id'))
        self.assertIn('select a resource or Python graph tab',ROUTE)
        self.assertIn('return False',ROUTE[ROUTE.index(guard):ROUTE.index('selected.session_id')])
        # New-tab intent is independent of the foreground provider.
        self.assertLess(ROUTE.index('if new_tab:'),ROUTE.index(guard))

    def test_native_qt_refusal_and_new_tab_stage(self):
        self.assertIn('QT_STAGE program-owned-navigation-refusal',SMOKE)
        self.assertIn('w.tabs.setCurrentWidget(reopened)',SMOKE)
        self.assertIn("assert not w._open_navigation_route(Route('resource',str(directory)))",SMOKE)
        self.assertIn("assert not w._open_navigation_route(Route('source',str(python_fixture)))",SMOKE)
        for name in ('before_program','before_routes','before_owners','before_bindings'):
            self.assertIn(name,SMOKE)
        self.assertIn("w._open_navigation_route(Route('resource',str(directory)),new_tab=True)",SMOKE)


if __name__=='__main__':unittest.main()
