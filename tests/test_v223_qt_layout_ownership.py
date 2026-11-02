"""Prevent regressions to manual minimap placement on Qt widgets.

Pure viewport geometry tests cannot prove QWidget placement correctness. These
source-level gates protect the ownership rule until the Mint Qt smoke runs.
"""
import ast
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


class OverviewQtOwnershipTests(unittest.TestCase):
    def test_graph_page_layout_owns_minimap_not_internal_viewport(self):
        source=(ROOT/'studio_native/gui.py').read_text(encoding='utf-8')
        tree=ast.parse(source)
        canvas=next(n for n in ast.walk(tree) if isinstance(n,ast.ClassDef) and n.name=='GraphCanvas')
        window=next(n for n in ast.walk(tree) if isinstance(n,ast.ClassDef) and n.name=='NativeLab')
        methods={n.name:n for n in canvas.body if isinstance(n,ast.FunctionDef)}
        page=next(n for n in window.body if isinstance(n,ast.FunctionDef) and n.name=='_graph_page')
        self.assertIn('attach_overview_host',methods)
        self.assertIn('GraphViewportHost',source)
        self.assertNotIn('QGridLayout(self.viewport())',source)
        self.assertNotIn('overview.move(',source)
        self.assertNotIn('overview.setGeometry(',source)
        self.assertIn('overlay_layout.addWidget(canvas,0,0)',source)
        self.assertIn('canvas.attach_overview_host(host,overlay_layout)',source)
        calls=[node.func.attr for node in ast.walk(methods['_place_overview'])
               if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)]
        self.assertFalse({'setGeometry','move','resize','setPos','activate','invalidate'} & set(calls),calls)
        self.assertTrue(any(isinstance(n,ast.Call) for n in ast.walk(page)))

    def test_qt_smoke_checks_real_host_transitions(self):
        source=(ROOT/'studio_native/qt_smoke.py').read_text()
        self.assertIn('Minimap outside graph host',source)
        self.assertIn('w.resize(1170,820)',source)
        self.assertIn('w.resize(1780,1090)',source)
        self.assertIn('Minimap outside graph host after tab reactivation',source)
        self.assertNotIn('viewport_widget.resize(809,789)',source)
        self.assertNotIn('overview.move(2821,1874)',source)

    def test_route_and_camera_authority_remains_outside_overview(self):
        source=(ROOT/'studio_native/gui.py').read_text()
        tree=ast.parse(source)
        overview=next(n for n in ast.walk(tree) if isinstance(n,ast.ClassDef) and n.name=='GraphOverview')
        methods={n.name for n in overview.body if isinstance(n,ast.FunctionDef)}
        self.assertNotIn('graph_camera_key',methods)
        self.assertNotIn('navigate_source',methods)
        self.assertNotIn('resolve_graph',methods)

if __name__=='__main__':unittest.main()
