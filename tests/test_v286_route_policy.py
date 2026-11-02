"""v2.86: source-root and secondary open actions use one qualified route path."""
import ast
from pathlib import Path
import unittest
from studio_native.navigation import GraphViewSessions,Route
from studio_native.source_editor import SourceDocumentSession
from studio_native.graph_routes import resolve_source_session_route

ROOT=Path(__file__).resolve().parents[1]
TREE=ast.parse((ROOT/'studio_native/gui.py').read_text())
UI=next(n for n in TREE.body if isinstance(n,ast.ClassDef) and n.name=='NativeLab')
def method(name):return next(n for n in UI.body if isinstance(n,ast.FunctionDef) and n.name==name)
def calls(method_name,attr):
    return any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and
               n.func.attr==attr for n in ast.walk(method(method_name)))

class RouteContract(unittest.TestCase):
    def test_one_selected_source_tab_path_for_root_and_secondary(self):
        source=ast.unparse(method('_open_navigation_route'))
        self.assertIn('isinstance(selected, SourceTabView)',source)
        self.assertIn('self._navigate_source_document_in_tab(route)',source)
        self.assertNotIn("selected.session_id not in ('source', 'resource')",source.split('if isinstance(selected, SourceTabView):')[1])
        self.assertFalse(calls('_open_navigation_route','replace'))

    def test_same_source_navigation_is_a_live_owner_preflight(self):
        self.assertTrue(calls('_navigate_source_document_in_tab','_resolve_live_source_route'))
        self.assertFalse(calls('_navigate_source_document_in_tab','_open_python_source_path'))
        self.assertTrue(calls('_navigate_source_document_in_tab','_store_active_source_view'))

    def test_history_can_return_to_prior_valid_scopes_after_source_switch(self):
        with __import__('tempfile').TemporaryDirectory() as folder:
            root=Path(folder);left=root/'a.py';right=root/'b.py'
            left.write_text('def a(): pass\n');right.write_text('def b(): pass\n')
            owner=SourceDocumentSession.open(left)
            sessions=GraphViewSessions();view=sessions.open('source',Route('source',str(left)))
            valid=resolve_source_session_route(Route('source',str(right)),
                    SourceDocumentSession.open(right))
            view.activate(valid.route)
            self.assertEqual(view.peek(-1),Route('source',str(left)))
            owner.update('def broken(:\n')
            self.assertIsNone(owner.parsed)
            self.assertEqual(view.route,Route('source',str(right)))
            self.assertEqual(view.peek(-1),Route('source',str(left)))

if __name__=='__main__':unittest.main()
