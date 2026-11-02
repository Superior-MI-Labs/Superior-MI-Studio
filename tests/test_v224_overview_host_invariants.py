"""Qt-free static QA of the single overlay ownership path."""
import ast
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class OverlayHostTests(unittest.TestCase):
    def test_both_primary_and_legacy_canvases_get_page_hosts(self):
        source=(ROOT/'studio_native/gui.py').read_text()
        self.assertIn('self.source_page=self._graph_page(self.source_canvas)',source)
        self.assertIn('self.resource_page=self._graph_page(self.resource_canvas)',source)
        self.assertIn('page=self._graph_page(canvas)',source)
        self.assertIn('self._legacy_pages[canvas]=page',source)
        self.assertIn('if page is legacy_page:return canvas',source)
        self.assertIn('self._graph_tab_for_page(page)',source)

    def test_overlay_is_not_a_source_graph_owner(self):
        module=ast.parse((ROOT/'studio_native/gui.py').read_text())
        canvas=next(n for n in module.body if isinstance(n,ast.ClassDef) and n.name=='GraphCanvas')
        fn=next(n for n in canvas.body if isinstance(n,ast.FunctionDef) and n.name=='attach_overview_host')
        calls=[node.func.attr for node in ast.walk(fn) if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)]
        self.assertNotIn('setGeometry',calls)
        self.assertNotIn('move',calls)
        self.assertIn('addWidget',calls)

if __name__=='__main__':unittest.main()
