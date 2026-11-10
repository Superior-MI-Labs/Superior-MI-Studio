"""Root bootstrap commits a new provider alias only after source preflight."""
import ast
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TREE=ast.parse((ROOT/'studio_native/gui.py').read_text(encoding='utf-8'))
UI=next(n for n in TREE.body if isinstance(n,ast.ClassDef) and n.name=='NativeLab')
SMOKE=(ROOT/'studio_native/qt_smoke.py').read_text(encoding='utf-8')


def method(name):
    return ast.unparse(next(n for n in UI.body
        if isinstance(n,ast.FunctionDef) and n.name==name))


class SourceRootBootstrapTests(unittest.TestCase):
    def test_ordinary_file_open_still_owns_source_preflight(self):
        source=method('_open_python_source_path')
        self.assertIn('bootstrap_root=False',source)
        self.assertIn("if bootstrap_root and self._active_source_tab_id != 'source':",source)
        self.assertIn('self._activate_source_view(self._source_tabs[\'source\'])',source)
        self.assertLess(source.index('except (OSError, ValueError) as exc:'),
                        source.index("if bootstrap_root and self._active_source_tab_id"))
        self.assertLess(source.index('self._remember_document_view()'),
                        source.index("if bootstrap_root and self._active_source_tab_id"))
        self.assertIn("self._source_tabs['source'].detail if bootstrap_root else self.source_detail",source)

    def test_uninitialized_root_calls_single_owned_file_open(self):
        source=method('_open_navigation_route')
        self.assertIn("self._open_python_source_path(route.path, bootstrap_root=True, focus_scope=route.scope if route.mode == 'focus' else None)",source)
        self.assertNotIn('self._activate_source_view(root)',source)
        self.assertIn("if self._view_sessions.get('source') is not None:",source)
        self.assertIn("self._navigate_source_document_in_tab(route, root_anchor=True)",source)

    def test_real_qt_covers_refusal_recovery_and_independent_view(self):
        self.assertIn('QT_STAGE uninitialized-source-root-bootstrap-refusal',SMOKE)
        for expected in (
            "other._view_sessions.get('source') is None",
            "other._active_source_tab_id=='source'",
            "other._source_documents==before_owners",
            "secondary_session.camera_slot()==secondary_camera",
            "other._source_documents[str(secondary_file)] is secondary_owner",
            "warnings.warning.assert_called_once()",
        ):
            self.assertIn(expected,SMOKE)


if __name__=='__main__':unittest.main()
