"""Cross-provider Qt replacement is prepared before altering tab authorities.

The headless tests verify production call ordering and the real native Qt smoke
injects failure in the established toolbar constructor. No mocked success is
accepted as native GUI qualification.
"""
import ast
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=(ROOT/'studio_native/gui.py').read_text(encoding='utf-8')
CLASS=next(node for node in ast.parse(SOURCE).body
           if isinstance(node,ast.ClassDef) and node.name=='NativeLab')
TRANSITION=next(node for node in CLASS.body
                if isinstance(node,ast.FunctionDef) and node.name=='_transition_graph_tab')
CODE=ast.unparse(TRANSITION)


class ProviderStagingTests(unittest.TestCase):
    def test_staging_happens_before_registration_and_camera_mutations(self):
        staging=CODE.index('page = self._graph_page(canvas)')
        toolbar=CODE.index('view.toolbar = self._create_navigation_bar')
        mutations=(
            'self._source_documents[str(source_session.path)] = source_session',
            'old.canvas._save_root_view()',
            'del self._source_tabs[old.session_id]',
            'del self._resource_tabs[old.session_id]',
            'session.activate(resolved.route',
            'self.tabs.removeTab(index)',
        )
        for mutation in mutations:
            self.assertLess(staging,CODE.index(mutation),mutation)
            self.assertLess(toolbar,CODE.index(mutation),mutation)

    def test_failed_staging_refuses_and_disposes_only_staged_page(self):
        self.assertIn('except (RuntimeError, ValueError) as exc:',CODE)
        self.assertIn('if page is not None:',CODE)
        self.assertIn('page.deleteLater()',CODE)
        self.assertIn('replacement view unavailable',CODE)
        self.assertLess(CODE.index('page.deleteLater()'),CODE.index('old.canvas._save_root_view()'))
        self.assertLess(CODE.index('index = self.tabs.indexOf(old.page)'),
                        CODE.index('page = self._graph_page(canvas)'))

    def test_native_qt_smoke_proves_refusal_and_later_success(self):
        smoke=(ROOT/'studio_native/qt_smoke.py').read_text(encoding='utf-8')
        self.assertIn('QT_STAGE cross-provider-replacement-staging-refusal',smoke)
        self.assertIn("side_effect=RuntimeError('fixture: toolbar construction failed')",smoke)
        self.assertIn('assert w._resource_tabs[mixed_id] is original_view',smoke)
        self.assertIn('assert w._source_documents==original_source_documents',smoke)
        self.assertIn('assert mixed_session.camera_slot()==original_camera',smoke)
        self.assertIn('assert w.open_resource_node({',smoke)


if __name__=='__main__':unittest.main()
