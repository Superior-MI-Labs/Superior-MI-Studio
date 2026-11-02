"""Graph routes use existing providers without introducing a second source authority."""
import tempfile
import unittest
from pathlib import Path

from studio_native.graph_routes import GraphRouteError, resolve_graph
from studio_native.navigation import Route, GraphViewSessions
from studio_native.python_graph import PythonDocument
from studio_native.semantic_contract import describe_graph

DEMO = Path(__file__).resolve().parents[1] / 'examples' / 'python-scope-demo.py'


class RouteResolutionTests(unittest.TestCase):
    def test_source_whole_reuses_existing_document_and_semantics(self):
        doc = PythonDocument(DEMO)
        selected = {k for k,v in doc.scopes.items() if k != 'module' and v.parent == 'module'}
        expected = doc.composite_file_graph(selected,detail='readable',collapsed_regions=set())
        outcome = resolve_graph(Route('source',str(DEMO)), document=doc,expanded_scopes=selected)
        self.assertIs(outcome.document,doc)
        self.assertEqual(outcome.descriptor,describe_graph(expected,origin='source'))
        self.assertEqual(outcome.route,Route('source',str(DEMO)))
        self.assertEqual(doc.raw,DEMO.read_bytes())

    def test_source_focus_returns_exact_source_identities(self):
        doc = PythonDocument(DEMO)
        scope = next(k for k,v in doc.scopes.items() if v.title == 'outer')
        focused = resolve_graph(Route('source',str(DEMO),scope,'focus'),document=doc)
        direct = doc.presentation_graph(scope,detail='readable')
        self.assertEqual([n['id'] for n in focused.graph['nodes']],
                         [n['id'] for n in direct['nodes']])
        self.assertEqual([e['id'] for e in focused.graph['edges']],
                         [e['id'] for e in direct['edges']])
        self.assertEqual(focused.descriptor.origin,'source')

    def test_two_sessions_cannot_cross_bind_documents(self):
        with tempfile.TemporaryDirectory() as tmp:
            other=Path(tmp)/'other.py'
            other.write_text('def outer():\n return 4\n',encoding='utf-8')
            a=PythonDocument(DEMO)
            b=PythonDocument(other)
            sessions=GraphViewSessions()
            sessions.open('a',Route('source',str(DEMO)))
            sessions.open('b',Route('source',str(other)))
            self.assertIs(resolve_graph(sessions.get('a').route,document=a).document,a)
            self.assertIs(resolve_graph(sessions.get('b').route,document=b).document,b)
            with self.assertRaisesRegex(GraphRouteError,'identity'):
                resolve_graph(sessions.get('b').route,document=a)
            self.assertEqual(sessions.get('a').route.path,str(DEMO))

    def test_resource_producer_is_same_validated_graph(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)
            (directory/'nested').mkdir()
            (directory/'file.py').write_text('a=1\n',encoding='utf-8')
            outcome=resolve_graph(Route('resource',str(directory)),resource_expanded={str(directory/'nested')})
            self.assertEqual(outcome.descriptor,describe_graph(outcome.graph,origin='resource'))
            self.assertIsNone(outcome.document)
            self.assertEqual(outcome.graph['path'],str(directory))
            self.assertEqual(set(n['resource_kind'] for n in outcome.graph['nodes']),{'directory','file'})

    def test_unknown_and_invalid_source_views_fail_closed(self):
        with self.assertRaisesRegex(GraphRouteError,'adapter'):
            resolve_graph(Route('source','/tmp/example.js'))
        with self.assertRaisesRegex(GraphRouteError,'Whole-file'):
            resolve_graph(Route('source',str(DEMO),'missing','whole'))
        with self.assertRaisesRegex(GraphRouteError,'scope'):
            resolve_graph(Route('source',str(DEMO),'missing','focus'))
        with self.assertRaisesRegex(GraphRouteError,'region'):
            resolve_graph(Route('region',str(DEMO),region='if#123'))
        with self.assertRaisesRegex(GraphRouteError,'scope'):
            resolve_graph(Route('resource',str(DEMO.parent),'nested'))
        with self.assertRaisesRegex(GraphRouteError,'document'):
            resolve_graph(Route('resource',str(DEMO.parent)),document=PythonDocument(DEMO))

    def test_provider_never_executes_source_for_display(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            marker=folder/'executed.marker'
            source=folder/'unsafe.py'
            source.write_text('from pathlib import Path\nPath('+repr(str(marker))+').write_text("FAIL")\n',encoding='utf-8')
            source_view=resolve_graph(Route('source',str(source)))
            resource_view=resolve_graph(Route('resource',str(folder)))
            self.assertTrue(source_view.graph['nodes'])
            self.assertTrue(resource_view.graph['nodes'])
            self.assertFalse(marker.exists())

    def test_directory_symlinks_do_not_become_navigation_roots(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            target=folder/'actual';target.mkdir()
            link=folder/'linked';link.symlink_to(target,target_is_directory=True)
            with self.assertRaises(ValueError):
                resolve_graph(Route('resource',str(link)))

    def test_document_display_is_not_a_second_source_edit_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            original=Path(tmp)/'test.py'
            original.write_text('def f(x):\n    return x + 1\n',encoding='utf-8')
            doc=PythonDocument(original)
            before=original.read_bytes()
            view=resolve_graph(Route('source',str(original)),document=doc)
            # A mutable layout projection can move, but the source file and
            # document are authoritative and unchanged.
            view.graph['nodes'][0]['x']=99999
            self.assertEqual(original.read_bytes(),before)
            self.assertEqual(doc.raw,before)
            self.assertNotEqual(view.descriptor.version,0)

if __name__=='__main__':unittest.main()
