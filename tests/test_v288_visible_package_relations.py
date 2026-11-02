"""v2.88: opt-in visible package evidence and layer-qualified resource graphs."""
import tempfile
import unittest
from pathlib import Path
from studio_native.resource_graph import directory_graph,ResourceError
from studio_native.semantic_contract import describe_graph
from studio_native.graph_routes import resolve_graph
from studio_native.navigation import Route
from studio_native.source_associations import (local_python_imports,local_python_symbol_candidates)
from studio_native.source_editor import SourceDocumentSession


class VisiblePackageRelationships(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.src=self.root/'main.py'
        self.pkg=self.root/'pkg';self.pkg.mkdir()
        self.pkg_init=self.pkg/'__init__.py';self.pkg_init.write_text('')
        self.worker=self.pkg/'worker.py'
        self.worker.write_text('def render():\n    return 1\n')
        self.src.write_text('import pkg.worker\nfrom pkg.worker import render\n')

    def graph(self,**kwargs):
        return directory_graph(self.root,show_imports=True,**kwargs)

    def test_imports_need_explicitly_visible_package_and_target(self):
        self.assertEqual(self.graph()['edges'],[])
        graph=self.graph(expanded_paths=(self.pkg,))
        imports=[e for e in graph['edges'] if e['relation']=='imports']
        self.assertEqual(len(imports),1)
        self.assertEqual(len(imports[0]['provenance']),3)
        self.assertEqual(imports[0]['certainty'],'local-file-candidate')
        self.assertIn('syntactic declaration match',imports[0]['provenance'][-1]['syntax'])
        self.assertEqual(len(describe_graph(graph,origin='resource').edges),1)

    def test_standalone_provider_remains_sibling_only(self):
        available={self.src,self.worker,self.pkg_init}
        self.assertFalse(local_python_imports(self.src,available))
        matches=local_python_imports(self.src,available,workspace_root=self.root)
        self.assertEqual([p.target for p in matches],[self.worker,self.worker])
        self.assertFalse(local_python_symbol_candidates(self.src,available))
        self.assertEqual(local_python_symbol_candidates(
            self.src,available,workspace_root=self.root)[0].symbol,'render')

    def test_unexpanded_package_initialization_is_not_guessed(self):
        visible={self.src,self.worker}
        self.assertEqual(local_python_imports(self.src,visible,workspace_root=self.root),[])

    def test_nested_packages_require_each_visible_init(self):
        sub=self.pkg/'inner';sub.mkdir()
        init=sub/'__init__.py';init.write_text('')
        nested=sub/'core.py';nested.write_text('value=1\n')
        self.src.write_text('import pkg.inner.core\n')
        self.assertFalse(self.graph(expanded_paths=(self.pkg,))['edges'])
        both=self.graph(expanded_paths=(self.pkg,sub))
        self.assertEqual(len(both['edges']),1)
        self.assertEqual(both['edges'][0]['relation'],'imports')
        init.unlink()
        self.assertFalse(self.graph(expanded_paths=(self.pkg,sub))['edges'])

    def test_relative_single_dot_import_and_declaration(self):
        caller=self.pkg/'client.py'
        caller.write_text('from .worker import render\n')
        graph=self.graph(expanded_paths=(self.pkg,))
        matches=[e for e in graph['edges'] if 'resource-import:' in e['id']
                 and e['source']!=e['target']]
        self.assertGreaterEqual(len(matches),1)
        one=local_python_imports(caller,{caller,self.worker,self.pkg_init},workspace_root=self.root)
        self.assertEqual(one[0].target,self.worker)
        symbols=local_python_symbol_candidates(caller,{caller,self.worker,self.pkg_init},workspace_root=self.root)
        self.assertEqual(symbols[0].symbol,'render')
        caller.write_text('from ..worker import render\n')
        self.assertFalse(local_python_imports(caller,{caller,self.worker,self.pkg_init},workspace_root=self.root))

    def test_package_init_is_candidate_for_bare_package_import(self):
        self.src.write_text('import pkg\n')
        graph=self.graph(expanded_paths=(self.pkg,))
        self.assertEqual(len(graph['edges']),1)
        path_to_id={n['resource_path']:n['id'] for n in graph['nodes'] if n.get('resource_path')}
        self.assertEqual(graph['edges'][0]['target'],path_to_id[str(self.pkg_init)])

    def test_symlink_package_cannot_be_used_as_module(self):
        alias=self.root/'alias';alias.symlink_to(self.pkg,target_is_directory=True)
        self.src.write_text('import alias.worker\n')
        self.assertEqual(local_python_imports(self.src,{self.src,alias/'__init__.py',alias/'worker.py'},
            workspace_root=self.root),[])

    def test_live_source_revision_replaces_saved_relationships(self):
        owner=SourceDocumentSession.open(self.src)
        owner.update('import pkg.worker\n')
        graph=self.graph(expanded_paths=(self.pkg,),source_documents={str(self.src):owner})
        self.assertEqual(len(graph['edges']),1)
        owner.update('import pkg.missing\n')
        self.assertFalse(self.graph(expanded_paths=(self.pkg,),
                                    source_documents={str(self.src):owner})['edges'])
        owner.update('def bad(:\n')
        self.assertFalse(self.graph(expanded_paths=(self.pkg,),
                                    source_documents={str(self.src):owner})['edges'])
        self.assertIn('pkg.worker',self.src.read_text())

    def test_layer_filter_preserves_well_formed_ports(self):
        asset=self.root/'icon.png';asset.write_bytes(b'icon')
        self.src.write_text('import pkg.worker\nopen("icon.png")\n')
        expanded=(self.pkg,)
        all_graph=self.graph(expanded_paths=expanded)
        self.assertEqual({e['relation'] for e in all_graph['edges']},{'imports','reference'})
        for layers,expected in ((('imports',),{'imports'}),
                                (('references',),{'reference'}),
                                ((),set())):
            graph=self.graph(expanded_paths=expanded,relationship_kinds=layers)
            self.assertEqual({e['relation'] for e in graph['edges']},expected)
            self.assertEqual(len(describe_graph(graph,origin='resource').edges),len(expected))
            self.assertEqual(set(graph['relationship_layers']),set(layers))
        with self.assertRaises(ResourceError):self.graph(relationship_kinds=('unknown',))

    def test_route_adapter_passes_filter_to_resource_owner(self):
        self.src.write_text('import pkg.worker\n')
        route=resolve_graph(Route('resource',str(self.root)),resource_imports=True,
                            resource_expanded=(self.pkg,),
                            resource_relationship_kinds=('references',))
        self.assertEqual(route.graph['edges'],[])
        self.assertEqual(route.graph['relationship_layers'],['references'])
        self.assertEqual(route.descriptor.origin,'resource')

    def test_missing_module_does_not_probe_nonvisible_children(self):
        hidden=self.pkg/'private.py';hidden.write_text('value=42\n')
        self.src.write_text('import pkg.private\n')
        self.assertFalse(self.graph()['edges'])
        self.assertEqual(len(self.graph(expanded_paths=(self.pkg,))['edges']),1)

    def test_disabling_overlay_clears_filtered_relations(self):
        graph=directory_graph(self.root,show_imports=False,relationship_kinds=('imports',),
                              expanded_paths=(self.pkg,))
        self.assertFalse(graph['edges'])
        self.assertFalse(graph['relationship_layers'])

    def test_candidate_limit_and_no_dynamic_import_execution(self):
        self.src.write_text('import importlib\nimportlib.import_module("pkg.worker")\n')
        self.assertFalse(self.graph(expanded_paths=(self.pkg,))['edges'])

    def test_source_text_encoding_and_bounded_regular_file(self):
        self.src.write_bytes(b'# coding: latin-1\nimport pkg.worker # caf\xe9\n')
        graph=self.graph(expanded_paths=(self.pkg,))
        self.assertEqual(len(graph['edges']),1)
        self.src.write_bytes(b'x'*512001)
        self.assertFalse(self.graph(expanded_paths=(self.pkg,))['edges'])
        self.src.write_bytes(b'\x00\x01')
        self.assertFalse(self.graph(expanded_paths=(self.pkg,))['edges'])

if __name__=='__main__':unittest.main()
