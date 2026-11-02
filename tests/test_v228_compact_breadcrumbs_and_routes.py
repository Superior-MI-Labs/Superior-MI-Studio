"""Presentation navigation is compact while routes remain lossless."""
import ast
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from studio_native.navigation import (
    Crumb, GraphViewSessions, Route, shorten_crumb, visible_breadcrumbs,
    resource_crumbs, source_crumbs,
)
from studio_native.graph_routes import resolve_graph
from studio_native.python_graph import PythonDocument

ROOT=Path(__file__).resolve().parents[1]


def method(name):
    tree=ast.parse((ROOT/'studio_native/gui.py').read_text())
    shell=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='NativeLab')
    return next(n for n in shell.body if isinstance(n,ast.FunctionDef) and n.name==name)


def calls(node,name):
    return any(isinstance(n,ast.Call) and
               ((isinstance(n.func,ast.Attribute) and n.func.attr==name) or
                (isinstance(n.func,ast.Name) and n.func.id==name)) for n in ast.walk(node))

class CompactRoutesTests(unittest.TestCase):
    def test_short_labels_bound_width_without_changing_name_or_route(self):
        word='massive_example_filename_with_a_long_name.py'
        label=shorten_crumb(word)
        self.assertEqual(len(label),22)
        self.assertTrue(label.endswith('name.py'))
        self.assertEqual(word,'massive_example_filename_with_a_long_name.py')
        self.assertEqual(shorten_crumb('short'), 'short')

    def test_unicode_names_and_invalid_limits(self):
        word='αβγδεζηθικλμνξοπρστυφχψω-file.py'
        self.assertLessEqual(len(shorten_crumb(word)),22)
        self.assertTrue(shorten_crumb(word).endswith('file.py'))
        with self.assertRaises(ValueError):shorten_crumb(word,4)
        with self.assertRaises(ValueError):visible_breadcrumbs((),2)

    def test_hidden_ancestor_keeps_identity_and_order(self):
        crumbs=tuple(Crumb(f'folder-{x}',Route('resource',f'/tmp/folder-{x}')) for x in range(12))
        displayed,hidden=visible_breadcrumbs(crumbs)
        self.assertEqual(len(displayed),4)
        self.assertEqual(displayed[0],crumbs[0])
        self.assertIsNone(displayed[1])
        self.assertEqual(displayed[-2:],crumbs[-2:])
        self.assertEqual(hidden,crumbs[1:-2])
        self.assertEqual(visible_breadcrumbs(crumbs[:3]),(crumbs[:3],()))

    def test_real_filesystem_routes_survive_visual_truncation(self):
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/('long-directory-'*6)
            path.mkdir()
            original=resource_crumbs(path)
            displayed,hidden=visible_breadcrumbs(original)
            self.assertEqual(original[-1].route.path,str(path))
            self.assertIn(original[-1],displayed)
            self.assertNotEqual(shorten_crumb(original[-1].text), original[-1].route.path)

    def test_source_path_and_scope_ancestors_are_lossless(self):
        doc=PythonDocument(ROOT/'examples/python-v11-bindings-and-returns.py')
        scope=next(k for k,v in doc.scopes.items() if v.title=='sum_items')
        crumbs=source_crumbs(doc,scope,'focus')
        self.assertEqual(crumbs[-1].route.scope,scope)
        self.assertEqual(crumbs[-1].route.kind,'source')

    def test_single_session_changes_provider_and_recovers_history(self):
        with TemporaryDirectory() as directory:
            root=Path(directory)
            script=root/'source.py'
            script.write_text('def f():\n    return 7\n',encoding='utf8')
            sessions=GraphViewSessions()
            resource=resolve_graph(Route('resource',str(root)))
            source=resolve_graph(Route('source',str(script)))
            session=sessions.open('view-2',resource.route)
            self.assertTrue(session.activate(source.route))
            self.assertEqual(session.peek(-1),resource.route)
            camera= session.camera_slot()
            self.assertTrue(session.activate(resource.route,history_direction=-1))
            self.assertEqual(session.route,resource.route)
            self.assertNotEqual(session.camera_slot(),camera)
            self.assertTrue(session.activate(source.route,history_direction=1))
            self.assertEqual(session.camera_slot(),camera)
            self.assertEqual(script.read_text(),'def f():\n    return 7\n')

    def test_cross_kind_qt_switch_reuses_session_and_resolves_first(self):
        fn=method('_transition_graph_tab')
        for name in ('resolve_graph','_graph_tab_for_page','_activate_source_view',
                     '_activate_resource_view','_add_tab_close_button','refresh_inspector'):
            self.assertTrue(calls(fn,name),name)
        # No new graph parser, source editor, camera store or tab registry.
        self.assertTrue(calls(method('_open_navigation_route'),'_transition_graph_tab'))
        self.assertTrue(calls(method('_navigate_history'),'_transition_graph_tab'))
        self.assertTrue(calls(method('open_resource_node'),'_open_navigation_route'))
        # Resource-card clicks now follow the common dispatcher rather than
        # retaining a second direct provider-transition decision.

    def test_invalid_resource_does_not_mutate_history(self):
        with TemporaryDirectory() as directory:
            root=Path(directory)
            session=GraphViewSessions().open('only',Route('resource',str(root)))
            with self.assertRaises((OSError,ValueError)):
                resolve_graph(Route('resource',str(root/'absent')))
            self.assertEqual(session.route,Route('resource',str(root)))
            self.assertIsNone(session.peek(-1))

    def test_main_root_tabs_remain_compatibility_anchors(self):
        text=(ROOT/'studio_native/gui.py').read_text()
        self.assertIn("old.session_id in ('source','resource')",text)
        self.assertIn("self._view_sessions.get(old.session_id)",text)
        self.assertIn("session.activate(resolved.route",text)

if __name__=='__main__':unittest.main()
