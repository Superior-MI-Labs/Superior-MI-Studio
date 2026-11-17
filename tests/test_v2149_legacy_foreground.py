"""Legacy developer-tab visibility must not replace another selected owner."""
import ast
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/'studio_native/gui.py').read_text(encoding='utf-8')
QT=(ROOT/'studio_native/qt_smoke.py').read_text(encoding='utf-8')


class LegacyForegroundTests(unittest.TestCase):
    def test_only_selected_legacy_page_can_redirect_foreground(self):
        tree=ast.parse(UI)
        lab=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='NativeLab')
        handler=next(n for n in lab.body if isinstance(n,ast.FunctionDef)
                     and n.name=='toggle_legacy_graph')
        body=ast.get_source_segment(UI,handler)
        self.assertIn('closing_selected=self.tabs.currentWidget() is page',body)
        self.assertIn('if index<0:return',body)
        self.assertIn("self.tabs.setCurrentWidget(self._source_tabs['source'].page)",body)
        self.assertNotIn('self.activate_source_tab()',body)
        self.assertNotIn('_view_sessions',body)

    def test_real_qt_menu_close_characterization_remains_required(self):
        self.assertIn('QT_STAGE legacy-visibility-preserves-selected-document',QT)
        self.assertIn('assert w.tabs.currentWidget() is program',QT)
        self.assertIn('assert w.tabs.currentWidget() is resource_root',QT)
        self.assertIn('assert w.tabs.currentWidget() is source_root',QT)
        self.assertIn('assert w._active_source_tab_id==\'source\'',QT)


if __name__=='__main__':unittest.main()
