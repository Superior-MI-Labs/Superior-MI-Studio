"""v2.55 regression gates for previously missed native tab and source lifecycle errors.

Qt is deliberately not imported: headless qualification must still detect an
unbound route in the native tab method and session identity replacement on reload.
"""
import ast
import tempfile
import unittest
from pathlib import Path

from studio_native.graph_routes import resolve_graph
from studio_native.navigation import GraphViewSessions, Route
from studio_native.python_graph import SourceError
from studio_native.source_editor import SourceDocumentSession


ROOT = Path(__file__).resolve().parents[1]


def native_method(name):
    tree = ast.parse((ROOT / 'studio_native' / 'gui.py').read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'NativeLab')
    return next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)


class ResourceTabPublicationTests(unittest.TestCase):
    def test_native_directory_tab_publishes_the_provider_resolved_route(self):
        """Prevent a no-PyQt packaging run from missing undefined `route` again."""
        method = native_method('open_resource_in_new_tab')
        opens = [n for n in ast.walk(method)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                 and n.func.attr == 'open' and isinstance(n.func.value, ast.Attribute)
                 and n.func.value.attr == '_view_sessions']
        self.assertEqual(len(opens), 1)
        self.assertEqual(len(opens[0].args), 2)
        self.assertIsInstance(opens[0].args[1], ast.Attribute)
        self.assertEqual(opens[0].args[1].attr, 'route')
        self.assertIsInstance(opens[0].args[1].value, ast.Name)
        self.assertEqual(opens[0].args[1].value.id, 'resolved')

    def test_resource_provider_route_is_canonical_and_session_is_independent(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            child = root / 'nested'
            child.mkdir()
            resolved = resolve_graph(Route('resource', str(child)))
            views = GraphViewSessions()
            parent = views.open('resource', Route('resource', str(root)))
            sibling = views.open('resource:2', resolved.route)
            self.assertEqual(sibling.route, resolved.route)
            self.assertEqual(parent.route, Route('resource', str(root)))
            self.assertNotEqual(sibling.camera_slot(), parent.camera_slot())


class SourceReloadIdentityTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / 'example.py'
        self.path.write_text('value=1\n')

    def test_explicit_discard_reloads_shared_session_in_place(self):
        owner = SourceDocumentSession.open(self.path)
        views = {'first': owner, 'second': owner}
        owner.update('value=2\n')
        self.path.write_text('value=3\n')
        with self.assertRaisesRegex(SourceError, 'explicitly discarded'):
            owner.discard_and_reload()
        self.assertEqual(owner.text, 'value=2\n')
        owner.discard_and_reload(discard_unsaved=True)
        self.assertIs(views['first'], views['second'])
        self.assertIs(views['first'], owner)
        self.assertEqual(owner.text, 'value=3\n')
        self.assertTrue(owner.graph_ready)
        self.assertFalse(owner.dirty)
        self.assertEqual(owner.revision, 2)

    def test_failed_explicit_discard_cannot_destroy_unsaved_text(self):
        owner = SourceDocumentSession.open(self.path)
        owner.update('value=unsaved\n')
        self.path.unlink()
        with self.assertRaises(OSError):
            owner.discard_and_reload(discard_unsaved=True)
        self.assertEqual(owner.text, 'value=unsaved\n')
        self.assertTrue(owner.dirty)

    def test_native_reload_uses_existing_session_instead_of_replacing_dict_entry(self):
        method = native_method('reload_python_source')
        assignments = [n for n in ast.walk(method) if isinstance(n, ast.Assign)]
        for node in assignments:
            self.assertFalse(any(isinstance(t, ast.Subscript) and
                                 isinstance(t.value, ast.Attribute) and
                                 t.value.attr == '_source_documents'
                                 for t in node.targets),
                             'Reload must not replace the shared source document owner')
        reload_calls = [n for n in ast.walk(method)
                        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                        and n.func.attr == 'discard_and_reload']
        self.assertEqual(len(reload_calls), 1)


if __name__ == '__main__':
    unittest.main()
