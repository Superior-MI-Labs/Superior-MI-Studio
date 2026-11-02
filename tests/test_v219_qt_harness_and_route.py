"""Host-only GUI dependencies must be importable by the smoke test at module scope."""
import ast
from pathlib import Path
import tempfile
import unittest
from studio_native.navigation import Route
from studio_native.graph_routes import resolve_graph
from studio_native.python_graph import PythonDocument

ROOT=Path(__file__).resolve().parents[1]

class QtHarnessAndRouteTests(unittest.TestCase):
    def test_qt_smoke_imports_route_resolution_at_module_scope(self):
        tree=ast.parse((ROOT/'studio_native'/'qt_smoke.py').read_text())
        names={(n.module,alias.name) for n in tree.body if isinstance(n,ast.ImportFrom)
               for alias in n.names}
        self.assertIn(('navigation','Route'),names)
        self.assertIn(('graph_routes','resolve_graph'),names)
        self.assertTrue(any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name)
                            and n.func.id=='Route' for n in ast.walk(tree)))
        self.assertTrue(any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name)
                            and n.func.id=='resolve_graph' for n in ast.walk(tree)))

    def test_source_scope_route_resolution_is_one_canonical_graph(self):
        path=ROOT/'examples'/'python-v15-boundary-regions.py'
        doc=PythonDocument(path)
        before=path.read_bytes()
        scope=next(k for k,v in doc.scopes.items() if v.title=='nested')
        whole=resolve_graph(Route('source',str(path)),document=doc,expanded_scopes={scope})
        focus=resolve_graph(Route('source',str(path),scope,'focus'),document=doc)
        common=set(n.id for n in whole.descriptor.nodes)&set(n.id for n in focus.descriptor.nodes)
        self.assertTrue(common)
        # Hidden/expanded is presentation state, not part of the source contract.
        def semantic_signature(n):
            return (n.id,n.construct,n.origin,n.ports,n.source,n.child_graph,
                    n.semantic_role,n.effect_verification)
        self.assertEqual({n.id:semantic_signature(n) for n in whole.descriptor.nodes if n.id in common},
                         {n.id:semantic_signature(n) for n in focus.descriptor.nodes if n.id in common})
        self.assertEqual(before,path.read_bytes())

    def test_invalid_scope_does_not_require_qt_or_change_file(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'sample.py'
            path.write_text('def real():\n    return 3\n')
            before=path.read_bytes()
            with self.assertRaisesRegex(ValueError,'scope'):
                resolve_graph(Route('source',str(path),'missing','focus'))
            self.assertEqual(path.read_bytes(),before)

if __name__=='__main__':unittest.main()
