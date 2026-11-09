"""Secondary source/resource tabs stage their Qt view before publishing it.

Static ordering complements the real Qt failure injection in qt_smoke.py.
"""
import ast
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TREE=ast.parse((ROOT/'studio_native/gui.py').read_text(encoding='utf-8'))
UI=next(x for x in TREE.body if isinstance(x,ast.ClassDef) and x.name=='NativeLab')
SMOKE=(ROOT/'studio_native/qt_smoke.py').read_text(encoding='utf-8')


def method(name):
    code=next(n for n in UI.body if isinstance(n,ast.FunctionDef) and n.name==name)
    return ast.unparse(code)


class NewTabStagingTests(unittest.TestCase):
    def test_resource_view_preparation_precedes_any_registry_or_history_mutation(self):
        source=method('open_resource_in_new_tab')
        toolbar=source.index("view.toolbar = self._create_navigation_bar(page, 'ResourceNavigationBar')")
        for mutation in ('self._store_active_resource_view()',
                         'self._next_resource_tab_number += 1',
                         'self._resource_tabs[sid] = view',
                         'self._view_sessions.open(sid, resolved.route)',
                         'self.tabs.addTab(page'):
            self.assertLess(toolbar,source.index(mutation),mutation)
        self.assertIn('if page is not None:',source)
        self.assertIn('page.deleteLater()',source)
        self.assertIn('view unavailable',source)

    def test_source_view_and_shared_document_precede_no_mutable_publication(self):
        source=method('open_source_in_new_tab')
        toolbar=source.index("view.toolbar = self._create_navigation_bar(page, 'PythonNavigationBar')")
        for mutation in ('self._source_documents[str(requested)] = source',
                         'self._store_active_source_view()',
                         'self._next_source_tab_number += 1',
                         'self._source_tabs[sid] = view',
                         'self._view_sessions.open(sid, route)',
                         'self.tabs.addTab(page'):
            self.assertLess(toolbar,source.index(mutation),mutation)
        self.assertIn('if page is not None:',source)
        self.assertIn('page.deleteLater()',source)
        self.assertIn('view unavailable',source)

    def test_qt_failure_injection_and_recovery_for_both_providers(self):
        self.assertIn('QT_STAGE new-secondary-tab-staging-refusal',SMOKE)
        self.assertIn("fixture: new resource toolbar failed",SMOKE)
        self.assertIn("fixture: new source toolbar failed",SMOKE)
        self.assertIn('assert w._source_documents==documents',SMOKE)
        self.assertIn('assert w.tabs.currentWidget() is root_selection',SMOKE)
        self.assertIn('assert w._view_sessions.get(opened_source.session_id) is None',SMOKE)
        self.assertIn('assert w._view_sessions.get(opened_resource.session_id) is None',SMOKE)


if __name__=='__main__':unittest.main()
