"""Source-tab lifecycle invariants (no Qt required)."""
import tempfile
import unittest
from pathlib import Path
from studio_native.graph_routes import resolve_graph
from studio_native.navigation import GraphViewSessions, Route
from studio_native.python_graph import PythonDocument

DEMO=Path(__file__).resolve().parents[1]/'examples'/'python-v11-bindings-and-returns.py'

class IndependentSourceTabs(unittest.TestCase):
    def setUp(self):
        self.document=PythonDocument(DEMO)
        self.scope=next(k for k,v in self.document.scopes.items() if v.title=='sum_items')
        self.views=GraphViewSessions()
        self.base=self.views.open('source',Route('source',str(DEMO)))
        self.other=self.views.open('source:2',Route('source',str(DEMO),self.scope,'focus'))

    def test_independent_route_and_camera(self):
        self.assertNotEqual(self.base.camera_slot(),self.other.camera_slot())
        self.base.visit(Route('source',str(DEMO),self.scope,'focus'))
        self.assertNotEqual(self.base.camera_slot(),self.other.camera_slot())
        self.assertEqual(self.other.route.mode,'focus')
        self.assertEqual(self.other.peek(-1),None)

    def test_shared_document_but_distinct_graph_projections(self):
        a=resolve_graph(self.base.route,document=self.document)
        b=resolve_graph(self.other.route,document=self.document)
        self.assertIs(a.document,b.document)
        self.assertIsNot(a.graph,b.graph)
        self.assertEqual(b.route.scope,self.scope)
        self.assertEqual(self.document.raw,DEMO.read_bytes())

    def test_closing_one_tab_preserves_other_history(self):
        before=self.other.camera_slot()
        self.base.visit(Route('source',str(DEMO),self.scope,'focus'))
        self.assertTrue(self.views.close('source'))
        self.assertEqual(self.other.camera_slot(),before)
        self.assertIs(self.views.get('source:2'),self.other)

    def test_missing_source_or_wrong_file_does_not_bind_foreign_document(self):
        with tempfile.TemporaryDirectory() as root:
            source=Path(root)/'other.py'
            source.write_text('def other():\n return 3\n',encoding='utf-8')
            route=Route('source',str(source))
            with self.assertRaisesRegex(ValueError,'identity'):
                resolve_graph(route,document=self.document)
            self.assertEqual(self.other.route.path,str(DEMO))

    def test_tabs_keep_source_operation_identities(self):
        a=resolve_graph(self.other.route,document=self.document)
        other=self.views.open('source:3',self.other.route)
        b=resolve_graph(other.route,document=self.document)
        self.assertEqual([n.id for n in a.descriptor.nodes],
                         [n.id for n in b.descriptor.nodes])
        self.assertEqual([e.id for e in a.descriptor.edges],
                         [e.id for e in b.descriptor.edges])
        self.assertNotEqual(self.other.camera_slot(),other.camera_slot())

if __name__=='__main__': unittest.main()
