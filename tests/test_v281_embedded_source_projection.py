"""Phase 5: source-owned nodes and edges inside the one resource canvas."""
import tempfile
import unittest
from pathlib import Path
from studio_native.graph_routes import resolve_graph
from studio_native.navigation import Route
from studio_native.resource_graph import directory_graph, MAX_VISIBLE_NODES
from studio_native.semantic_contract import describe_graph
from studio_native.source_editor import SourceDocumentSession


class EmbeddedPythonResources(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)

    def source(self,name,body):
        path=self.root/name
        path.write_text(body,encoding='utf-8')
        return path

    def test_real_python_flow_projection_reuses_source_authority(self):
        file=self.source('worker.py','def add(x):\n    y = x + 2\n    return y\n\nadd(5)\n')
        before=file.read_bytes()
        graph=directory_graph(self.root,expanded_paths=(file,))
        container=next(n for n in graph['nodes'] if n['title']=='worker.py')
        members=[n for n in graph['nodes'] if n.get('resource_source_path')==str(file)]
        self.assertEqual(container['region_role'],'python-source')
        self.assertTrue(container.get('embedded_region'))
        self.assertIn('assignment',{n['source_kind'] for n in members})
        self.assertIn('return',{n['source_kind'] for n in members})
        self.assertTrue(any(e['relation']=='data' and ':python:' in e['id'] for e in graph['edges']))
        self.assertEqual(len(describe_graph(graph,origin='resource').edges),len(graph['edges']))
        self.assertEqual(before,file.read_bytes())
        self.assertTrue(all('source_span' not in n and n.get('semantic_role')=='unspecified' for n in members))

    def test_live_unsaved_revision_overrides_saved_file(self):
        file=self.source('worker.py','def before():\n    return 1\n')
        session=SourceDocumentSession.open(file)
        session.update('def changed():\n    return 2\n')
        path=str(file)
        graph=resolve_graph(Route('resource',str(self.root)),resource_expanded=(file,),
                            source_documents={path:session}).graph
        names=' '.join(n['title'] for n in graph['nodes'])
        self.assertIn('CHANGED',names)
        self.assertNotIn('BEFORE',names)
        self.assertIn('Live source',graph['nodes'][0]['subtitle'])
        self.assertIn('before',file.read_text())
        session.update('def broken(:\n')
        bad=directory_graph(self.root,expanded_paths=(file,),source_documents={path:session})
        owner=bad['nodes'][0]
        self.assertEqual(len(bad['nodes']),1)
        self.assertIn('no qualified graph',owner['resource_preview']['status'])
        self.assertIn('before',file.read_text())

    def test_two_python_files_cannot_collide_in_node_or_port_id(self):
        one=self.source('one.py','def repeat(x):\n    return x + 1\n')
        two=self.source('two.py','def repeat(x):\n    return x + 1\n')
        graph=directory_graph(self.root,expanded_paths=(one,two))
        desc=describe_graph(graph,origin='resource')
        self.assertEqual(len({n.id for n in desc.nodes}),len(desc.nodes))
        self.assertEqual(len({e.id for e in desc.edges}),len(desc.edges))
        self.assertEqual(len({n['resource_source_path'] for n in graph['nodes']
                              if 'resource_source_path' in n}),2)
        self.assertLessEqual(len(graph['nodes']),MAX_VISIBLE_NODES)

    def test_route_contract_unmodified_and_invalid_source_no_stale_projection(self):
        file=self.source('program.py','def ok():\n    return 1\n')
        result=resolve_graph(Route('resource',str(self.root)),resource_expanded=(file,))
        self.assertEqual(result.descriptor.origin,'resource')
        self.assertIsNone(result.document)
        file.write_text('def invalid(:\n',encoding='utf-8')
        graph=directory_graph(self.root,expanded_paths=(file,))
        self.assertEqual(len(graph['nodes']),1)
        self.assertEqual(graph['nodes'][0]['resource_preview']['status'],'Python analysis unavailable')


if __name__=='__main__':unittest.main()
