"""A first source-root focus must qualify before publishing a source session."""
import ast
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
UI=next(node for node in ast.parse((ROOT/'studio_native/gui.py').read_text()).body
        if isinstance(node,ast.ClassDef) and node.name=='NativeLab')
SMOKE=(ROOT/'studio_native/qt_smoke.py').read_text(encoding='utf-8')

def method(name):
    return ast.unparse(next(node for node in UI.body
        if isinstance(node,ast.FunctionDef) and node.name==name))

class InitialRootFocusTests(unittest.TestCase):
    def test_dispatch_passes_focus_to_existing_file_opening_transaction(self):
        route=method('_open_navigation_route')
        self.assertIn("focus_scope=route.scope if route.mode == 'focus' else None",route)
        self.assertIn('self.navigate_source(route.scope)',route)
        self.assertLess(route.index('focus_scope=route.scope'),
                        route.index('self.navigate_source(route.scope)'))
        self.assertIn("if self._view_sessions.get('source') is not None:",route)

    def test_current_revision_scope_is_qualified_before_any_publication(self):
        source=method('_open_python_source_path')
        self.assertIn('focus_scope=None',source)
        self.assertIn('if focus_scope is not None:',source)
        self.assertIn('resolve_source_session_route(',source)
        self.assertIn("Route('source', str(doc.path), focus_scope, 'focus')",source)
        self.assertIn('session, detail=detail, expanded_scopes=expanded',source)
        self.assertIn("raise SourceError('Cannot focus invalid Python source')",source)
        self.assertLess(source.index('resolve_source_session_route('),
                        source.index('self._source_documents[str(requested)]'))
        self.assertLess(source.index('resolve_source_session_route('),
                        source.index("if bootstrap_root and self._active_source_tab_id != 'source':"))
        self.assertLess(source.index('resolve_source_session_route('),
                        source.index('self._view_sessions.open('))

    def test_real_qt_proves_refusal_and_valid_root_history(self):
        self.assertIn('QT_STAGE uninitialized-source-root-focus-atomicity',SMOKE)
        for marker in (
            'assert not other._open_navigation_route(missing_focus)',
            'assert other._view_sessions.get(\'source\') is None',
            'assert other._source_documents==before_owners',
            'assert other.tabs.currentWidget() is resource_root_page',
            'assert other._open_navigation_route(valid_focus)',
            "assert other._view_sessions.get('source').route==valid_focus",
            "assert other._view_sessions.get('source').peek(-1)==Route('source',str(root_file))",
            'assert secondary_session.camera_slot()==secondary_camera',
        ):
            self.assertIn(marker,SMOKE)

if __name__=='__main__':unittest.main()
