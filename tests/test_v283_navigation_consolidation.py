"""Universal view history and source-owner safety, including absent-Qt CI."""
import ast
import tempfile
from pathlib import Path
import unittest

from studio_native.graph_routes import resolve_graph
from studio_native.navigation import GraphViewSessions, Route
from studio_native.source_editor import SourceDocumentSession

ROOT=Path(__file__).resolve().parents[1]


def method(name):
    tree=ast.parse((ROOT/'studio_native/gui.py').read_text())
    ui=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='NativeLab')
    return next(node for node in ui.body if isinstance(node,ast.FunctionDef) and node.name==name)


def calls(node,name):
    return any(isinstance(item,ast.Call) and
               ((isinstance(item.func,ast.Attribute) and item.func.attr==name) or
                (isinstance(item.func,ast.Name) and item.func.id==name)) for item in ast.walk(node))


class UniversalNavigationConsolidation(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.first=self.root/'one.py'
        self.second=self.root/'two.py'
        self.first.write_text('def first():\n    return 1\n')
        self.second.write_text('def second():\n    return 2\n')

    def test_mixed_history_keeps_one_cursor_and_document_owner(self):
        owner=SourceDocumentSession.open(self.second)
        owner.update('def edited():\n    return 3\n')
        session=GraphViewSessions().open('secondary',Route('resource',str(self.root)))
        one=resolve_graph(Route('source',str(self.first)))
        two=resolve_graph(Route('source',str(self.second)),document=owner.parsed)
        session.activate(one.route)
        session.activate(two.route)
        self.assertEqual(two.document.source,owner.text)
        self.assertTrue(session.activate(one.route,history_direction=-1))
        self.assertTrue(session.activate(two.route,history_direction=1))
        self.assertEqual(owner.parsed.source,'def edited():\n    return 3\n')
        self.assertIn('second',self.second.read_text())
        self.assertEqual(session.peek(-1),one.route)

    def test_mixed_resource_source_and_scope_identity(self):
        owner=SourceDocumentSession.open(self.first)
        scope=next(key for key,value in owner.parsed.scopes.items() if value.title=='first')
        resource=resolve_graph(Route('resource',str(self.root))).route
        focused=resolve_graph(Route('source',str(self.first),scope,'focus'),document=owner.parsed).route
        session=GraphViewSessions().open('secondary',resource)
        session.activate(focused)
        camera=session.camera_slot()
        self.assertEqual(session.peek(-1),resource)
        session.activate(resource,history_direction=-1)
        self.assertNotEqual(session.camera_slot(),camera)
        session.activate(focused,history_direction=1)
        self.assertEqual(session.camera_slot(),camera)

    def test_invalid_source_cannot_qualify_old_graph(self):
        owner=SourceDocumentSession.open(self.second)
        before=owner.parsed
        owner.update('def broken(:\n')
        self.assertIsNone(owner.parsed)
        self.assertIsNotNone(before)
        session=GraphViewSessions().open('secondary',Route('source',str(self.first)))
        entries=list(session.history._entries)
        # The route provider accepts no in-memory document as a request to
        # read disk. The UI transaction MUST explicitly refuse this case.
        fn=method('_navigate_source_document_in_tab')
        self.assertTrue(calls(fn,'_resolve_live_source_route'))
        self.assertIn('resolve_source_session_route',ast.unparse(method('_resolve_live_source_route')))
        self.assertEqual(entries,session.history._entries)

    def test_selected_tab_not_stale_provider_alias_is_history_authority(self):
        fn=method('_navigate_history')
        self.assertTrue(calls(fn,'_graph_tab_for_page'))
        self.assertTrue(calls(fn,'currentWidget'))
        self.assertTrue(calls(fn,'_navigate_source_document_in_tab'))
        self.assertFalse(any(isinstance(x,ast.IfExp) and any(isinstance(c,ast.Attribute) and
                         c.attr=='_active_resource_tab_id' for c in ast.walk(x)) for x in ast.walk(fn)))

    def test_same_provider_file_changes_keep_session_and_validate_first(self):
        fn=method('_navigate_source_document_in_tab')
        for needed in ('_resolve_live_source_route','_store_active_source_view',
                       '_load_source_editor','_activate_source_view','_update_source_tab_title'):
            self.assertTrue(calls(fn,needed),needed)
        self.assertTrue(calls(method('_open_navigation_route'),'_navigate_source_document_in_tab'))
        self.assertFalse(calls(fn,'replace'))

    def test_source_owner_unchanged_by_resource_projection(self):
        owner=SourceDocumentSession.open(self.first)
        owner.update('def fresh():\n    return 10\n')
        source=resolve_graph(Route('source',str(self.first)),document=owner.parsed)
        resource=resolve_graph(Route('resource',str(self.root)),resource_expanded=(self.first,),
                               source_documents={str(self.first):owner})
        self.assertEqual(source.document.source,owner.text)
        self.assertTrue(any('FRESH' in node['title'] for node in resource.graph['nodes']))
        self.assertEqual(self.first.read_text(),'def first():\n    return 1\n')


if __name__=='__main__':unittest.main()
