"""v2.26 source-neutral graph tab contract (no native Qt required)."""
from pathlib import Path
import tempfile
import unittest
from studio_native.graph_routes import GraphRouteError, resolve_graph
from studio_native.navigation import GraphViewSessions, Route


class ResourceTabSessionTests(unittest.TestCase):
    def test_directory_tabs_reuse_provider_but_not_camera_or_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            nested=root/'child'
            nested.mkdir()
            registry=GraphViewSessions()
            first=registry.open('resource',Route('resource',str(root)))
            second=registry.open('resource:2',Route('resource',str(root)))
            before=resolve_graph(first.route)
            separate=resolve_graph(second.route)
            self.assertEqual(before.descriptor.nodes,separate.descriptor.nodes)
            self.assertIsNot(before.graph,separate.graph)
            self.assertNotEqual(first.camera_slot(),second.camera_slot())
            qualified=resolve_graph(Route('resource',str(nested)))
            second.activate(qualified.route)
            self.assertEqual(first.route.path,str(root))
            self.assertEqual(second.peek(-1),Route('resource',str(root)))
            self.assertNotEqual(first.camera_slot(),second.camera_slot())
            self.assertTrue(registry.close('resource:2'))
            self.assertIs(registry.get('resource'),first)

    def test_refused_destination_does_not_advance_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            session=GraphViewSessions().open('resource',Route('resource',str(root)))
            with self.assertRaises((OSError,ValueError)):
                resolve_graph(Route('resource',str(root/'missing')))
            self.assertIsNone(session.peek(-1))
            self.assertEqual(session.route.path,str(root))

    def test_resource_and_source_camera_slots_do_not_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            file=root/'example.py'
            file.write_text('def f():\n    return 3\n',encoding='utf-8')
            views=GraphViewSessions()
            directory=views.open('resource',Route('resource',str(root)))
            source=views.open('source',Route('source',str(file)))
            self.assertNotEqual(directory.camera_slot(),source.camera_slot())
            self.assertEqual(resolve_graph(source.route).route.kind,'source')
            self.assertEqual(resolve_graph(directory.route).route.kind,'resource')

if __name__=='__main__':unittest.main()
