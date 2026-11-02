"""Headless regressions for native Qt preflight and per-route camera identity."""
import ast
import symtable
import tempfile
import unittest
from pathlib import Path

from studio_native.navigation import Route, root_camera_slot
from studio_native.graph_routes import resolve_graph
from studio_native.python_graph import PythonDocument

ROOT = Path(__file__).resolve().parents[1]


def shadowed_imports(source: str) -> set[str]:
    """Detect imported names rebound as locals by the smoke entrypoint.

    `symtable` uses Python's *actual* lexical resolution, catching the very
    UnboundLocalError that ast.parse/compileall cannot catch. No Qt required.
    """
    tree = ast.parse(source)
    imported = set()
    for statement in tree.body:
        if isinstance(statement, ast.Import):
            imported.update(alias.asname or alias.name.partition('.')[0]
                            for alias in statement.names)
        elif isinstance(statement, ast.ImportFrom):
            imported.update(alias.asname or alias.name for alias in statement.names
                            if alias.name != '*')
    code_table = symtable.symtable(source, '<smoke>', 'exec')
    main = next((child for child in code_table.get_children()
                 if child.get_name() == 'main'), None)
    if main is None:
        raise AssertionError('Qt smoke entrypoint main() not found')
    return {name for name in imported if name in main.get_identifiers()
            and main.lookup(name).is_local()}


class SmokeNamespaceTests(unittest.TestCase):
    def test_qt_main_does_not_shadow_imported_names(self):
        text = (ROOT/'studio_native'/'qt_smoke.py').read_text(encoding='utf-8')
        self.assertEqual(shadowed_imports(text), set(),
                         'Qt smoke locally shadows module imports, breaking early use')

    def test_preflight_detects_python_scoping_bug_without_qt(self):
        collision = '''import model\ndef main():\n    model.validate(1)\n    model = object()\n'''
        self.assertEqual(shadowed_imports(collision), {'model'})
        self.assertEqual(shadowed_imports('import model\ndef main():\n    model.validate(1)\n'), set())
        self.assertEqual(shadowed_imports('from .navigation import Route as R\ndef main():\n    R(1)\n    R = 2\n'), {'R'})


class CameraAuthorityTests(unittest.TestCase):
    def test_route_and_tab_camera_keys_are_independent(self):
        path = '/tmp/same.py'
        whole = Route('source', path)
        focus = Route('source', path, 'module/function:x', 'focus')
        self.assertNotEqual(root_camera_slot('tab-a', whole), root_camera_slot('tab-a', focus))
        self.assertNotEqual(root_camera_slot('tab-a', focus), root_camera_slot('tab-b', focus))
        self.assertEqual(root_camera_slot('tab-a', whole), root_camera_slot('tab-a', whole))
        self.assertNotEqual(root_camera_slot('tab-a', Route('resource','/tmp')),
                            root_camera_slot('tab-a', whole))

    def test_scope_names_with_separators_do_not_collide(self):
        a = Route('source','/tmp/a.py','a:b','focus')
        b = Route('source','/tmp/a.py','a','focus',region='b')
        self.assertNotEqual(root_camera_slot('tab:1',a),root_camera_slot('tab:1',b))
        with self.assertRaises(TypeError):root_camera_slot('tab:1','not a Route')
        with self.assertRaises(ValueError):root_camera_slot('',a)

    def test_per_route_view_state_never_mutates_source(self):
        with tempfile.TemporaryDirectory() as td:
            sample = Path(td)/'prog.py'
            sample.write_text('def f(x):\n    return x + 1\n',encoding='utf-8')
            doc = PythonDocument(sample)
            scope = next(k for k,v in doc.scopes.items() if v.title=='f')
            whole = Route('source',str(sample))
            focus = Route('source',str(sample),scope,'focus')
            before = sample.read_bytes()
            a = resolve_graph(whole,document=doc)
            b = resolve_graph(focus,document=doc)
            cameras={root_camera_slot('source',a.route):(5.,10.,.8),
                     root_camera_slot('source',b.route):(20.,35.,1.4)}
            self.assertEqual(len(cameras),2)
            self.assertEqual(cameras[root_camera_slot('source',a.route)],(5.,10.,.8))
            self.assertEqual(before,sample.read_bytes())
            self.assertEqual(a.document,b.document)


if __name__=='__main__':
    unittest.main()
