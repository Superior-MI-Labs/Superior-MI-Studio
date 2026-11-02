"""Cross-provider Qt tab contract, checked without requiring PyQt6 on CI.

Host smoke still owns real Qt clicks, focus, canvas rendering and containment.
"""
import ast
from pathlib import Path
import tempfile
import unittest
from studio_native.graph_routes import resolve_graph
from studio_native.navigation import GraphViewSessions, Route

ROOT=Path(__file__).resolve().parents[1]


def method(name):
    tree=ast.parse((ROOT/'studio_native/gui.py').read_text())
    shell=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='NativeLab')
    return next(node for node in shell.body if isinstance(node,ast.FunctionDef) and node.name==name)


def called(fn, method_name):
    return any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
               and n.func.attr==method_name for n in ast.walk(fn))


class UnifiedTabActionTests(unittest.TestCase):
    def test_both_source_and_resource_derive_from_one_qt_view_contract(self):
        tree=ast.parse((ROOT/'studio_native/gui.py').read_text())
        classes={c.name:c for c in tree.body if isinstance(c,ast.ClassDef)}
        for name in ('SourceTabView','ResourceTabView'):
            self.assertTrue(any(isinstance(base,ast.Name) and base.id=='GraphTabView'
                                for base in classes[name].bases),name)

    def test_current_canvas_uses_tab_registry_not_legacy_source_page(self):
        fn=method('current_canvas')
        self.assertTrue(called(fn,'_graph_tab_for_page'))
        self.assertFalse(any(isinstance(n,ast.Attribute) and n.attr=='source_page'
                             for n in ast.walk(fn)))
        self.assertTrue(called(method('_workspace_tab_changed'),'_graph_tab_for_page'))

    def test_generic_frame_and_zoom_use_current_canvas(self):
        for name in ('_frame_current_graph','reset_current_zoom'):
            self.assertTrue(called(method(name),'current_canvas'),name)

    def test_breadcrumb_dispatch_uses_existing_provider_entrypoints(self):
        fn=method('_open_navigation_route')
        for target in ('open_resource_in_new_tab','browse_resource',
                       'open_source_in_new_tab','_open_python_source_path'):
            self.assertTrue(called(fn,target),target)
        self.assertTrue(called(method('_open_breadcrumb'),'_open_navigation_route'))

    def test_cross_provider_routes_share_session_history_without_copying_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            source=root/'sample.py'
            source.write_text('def f(x):\n    return x\n',encoding='utf8')
            views=GraphViewSessions()
            tab=views.open('tab',resolve_graph(Route('resource',str(root))).route)
            before=source.read_bytes()
            resolved=resolve_graph(Route('source',str(source)))
            self.assertEqual(resolved.descriptor.origin,'source')
            tab.activate(resolved.route)
            self.assertEqual(tab.peek(-1).kind,'resource')
            self.assertNotEqual(tab.camera_slot(),views.open('second',Route('source',str(source))).camera_slot())
            self.assertEqual(source.read_bytes(),before)


if __name__=='__main__':unittest.main()
