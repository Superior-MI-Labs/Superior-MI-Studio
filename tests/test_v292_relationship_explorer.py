"""v2.92: relationship search is a bounded read-only graph projection."""
import tempfile
import unittest
from pathlib import Path
from dataclasses import replace

from studio_native.resource_graph import directory_graph, search_resource_relationships
from studio_native.semantic_contract import ContractError, describe_graph


class RelationshipExplorerContract(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        (self.root/'assets').mkdir()
        (self.root/'assets'/'icon.png').write_bytes(b'PNG')
        (self.root/'main.py').write_text('import helper\nopen("assets/icon.png")\n')
        (self.root/'helper.py').write_text('import other\n')
        (self.root/'other.py').write_text('VALUE=1\n')
        self.refresh()

    def refresh(self,**options):
        self.graph=directory_graph(self.root,show_imports=True,
            expanded_paths=[self.root/'assets'],**options)
        self.descriptor=describe_graph(self.graph,origin='resource')

    def search(self,**options):
        return search_resource_relationships(self.descriptor,self.graph,**options)

    def test_all_edges_once_with_classification(self):
        result=self.search()
        self.assertEqual((result.total,result.imports,result.references),(3,2,1))
        self.assertEqual(len({item.edge_id for item in result.results}),3)

    def test_exact_visible_names_are_searchable(self):
        for term,expected in [('icon.png',1),('helper.py',2),('missing',0)]:
            with self.subTest(term=term):self.assertEqual(self.search(query=term).total,expected)

    def test_syntax_search_uses_existing_source_evidence(self):
        self.assertEqual(self.search(query='import other').total,1)
        self.assertEqual(self.search(query='assets/icon.png').references,1)

    def test_search_is_case_insensitive(self):
        self.assertEqual(self.search(query='IMPORT HELPER').imports,1)
        self.assertEqual(self.search(query='ICON.PNG').references,1)

    def test_kind_and_certainty_are_searchable(self):
        self.assertEqual(self.search(query='literal-path-candidate').references,1)
        self.assertEqual(self.search(query='local-file-candidate').imports,2)

    def test_visible_file_focus_one_hop(self):
        result=self.search(focus=self.root/'helper.py')
        self.assertEqual((result.total,result.imports,result.references),(2,2,0))
        result=self.search(focus=self.root/'assets'/'icon.png')
        self.assertEqual((result.total,result.imports,result.references),(1,0,1))

    def test_two_hop_visible_chain_includes_next_direct_edge(self):
        main=self.root/'main.py'
        self.assertEqual(self.search(focus=main,direction='outgoing',hops=1).total,2)
        result=self.search(focus=main,direction='outgoing',hops=2)
        self.assertEqual((result.total,result.imports,result.references),(3,2,1))
        self.assertTrue(any(item.source.name=='helper.py' and item.target.name=='other.py'
                            for item in result.results))

    def test_incoming_two_hop_chain_from_terminal(self):
        result=self.search(focus=self.root/'other.py',direction='incoming',hops=2)
        self.assertEqual((result.total,result.imports),(2,2))
        self.assertEqual({item.source.name for item in result.results},{'helper.py','main.py'})

    def test_two_hop_never_creates_transitive_edge(self):
        result=self.search(focus=self.root/'main.py',direction='outgoing',hops=2)
        self.assertFalse(any(item.source.name=='main.py' and item.target.name=='other.py'
                             for item in result.results))

    def test_invalid_hop_and_direction_refused(self):
        for hops in (0,3,True,1.5):
            with self.subTest(hops=hops),self.assertRaises(ValueError):
                self.search(focus=self.root/'main.py',hops=hops)
        for direction in ('sideways',None):
            with self.subTest(direction=direction),self.assertRaises(ValueError):
                self.search(focus=self.root/'main.py',direction=direction)
        with self.assertRaises(ValueError):self.search(hops=2)
        with self.assertRaises(ValueError):self.search(direction='incoming')

    def test_two_hop_respects_filtered_snapshot(self):
        self.refresh(relationship_kinds=('references',))
        result=self.search(focus=self.root/'main.py',direction='outgoing',hops=2)
        self.assertEqual((result.total,result.imports,result.references),(1,0,1))

    def test_cycle_does_not_duplicate_edges(self):
        (self.root/'other.py').write_text('import helper\n')
        self.refresh()
        result=self.search(focus=self.root/'helper.py',hops=2)
        self.assertEqual(len({item.edge_id for item in result.results}),result.total)

    def test_missing_or_unexpanded_focus_fails(self):
        for target in [self.root/'assets'/'invisible.png',self.root/'assets',self.root/'missing.py']:
            with self.subTest(target=target),self.assertRaises(ContractError):self.search(focus=target)

    def test_result_limit_does_not_fake_total(self):
        result=self.search(limit=1)
        self.assertEqual(result.total,3)
        self.assertEqual(len(result.results),1)
        self.assertEqual(result.limit,1)
        self.assertEqual(len(self.search(limit=48).results),3)

    def test_reject_unbounded_or_malformed_queries(self):
        for value in ['x'*129,42,None]:
            with self.subTest(value=value),self.assertRaises(ValueError):self.search(query=value)
        for value in [-1,0,49,1.5,True]:
            with self.subTest(value=value),self.assertRaises(ValueError):self.search(limit=value)

    def test_untrusted_descriptor_or_revision_fails(self):
        with self.assertRaises(ContractError):search_resource_relationships(None,self.graph)
        with self.assertRaises(ContractError):search_resource_relationships(replace(self.descriptor,origin='source'),self.graph)
        copied={**self.graph,'edges':[dict(edge) for edge in self.graph['edges']]}
        copied['edges'][0]['target']='resource:forged'
        with self.assertRaises(ContractError):search_resource_relationships(self.descriptor,copied)

    def test_mutated_endpoint_identity_fails_closed(self):
        target=next(node for node in self.graph['nodes'] if node.get('resource_path')==str(self.root/'helper.py'))
        target['resource_path']=str(self.root/'other.py')
        with self.assertRaises(ContractError):self.search()

    def test_symlink_swap_after_graph_build_refused(self):
        asset=self.root/'assets'/'icon.png'
        asset.unlink()
        (self.root/'assets'/'other.png').write_bytes(b'PNG')
        asset.symlink_to(self.root/'assets'/'other.png')
        with self.assertRaises(ContractError):self.search()

    def test_removed_endpoint_refuses_stale_search(self):
        (self.root/'helper.py').unlink()
        with self.assertRaisesRegex(ContractError,'no longer a regular file'):
            self.search()

    def test_workspace_root_symlink_swap_refuses_search(self):
        # A previously trusted workspace root must not become a redirect.
        relocated=self.root.with_name(self.root.name+'-moved')
        self.root.rename(relocated)
        self.addCleanup(lambda:relocated.rename(self.root) if relocated.exists() else None)
        self.root.symlink_to(relocated,target_is_directory=True)
        self.addCleanup(lambda:self.root.unlink() if self.root.is_symlink() else None)
        with self.assertRaisesRegex(ContractError,'workspace root changed'):
            self.search()

    def test_search_reads_no_unshown_directory(self):
        hidden=self.root/'hidden';hidden.mkdir()
        (hidden/'secret.py').write_text('import helper\n')
        self.assertEqual(self.search(query='secret.py').total,0)
        self.assertFalse(any('secret.py' in str(item.source) for item in self.search().results))

    def test_overlay_off_yields_no_candidates(self):
        self.graph=directory_graph(self.root,show_imports=False)
        self.descriptor=describe_graph(self.graph,origin='resource')
        self.assertEqual(self.search().total,0)

    def test_query_is_projection_without_file_writes(self):
        old=(self.root/'main.py').read_bytes()
        self.search(query='import')
        self.assertEqual(old,(self.root/'main.py').read_bytes())

    def test_active_draft_changes_visible_results(self):
        class Owner:
            text='import other\n'
        self.refresh(source_documents={str(self.root/'main.py'):Owner()})
        self.assertEqual(self.search(query='assets/icon.png').total,0)
        self.assertEqual(self.search(query='import other').total,2)

    def test_layer_filter_respected(self):
        self.refresh(relationship_kinds=('imports',))
        self.assertEqual(self.search().references,0)
        self.refresh(relationship_kinds=('references',))
        self.assertEqual(self.search().imports,0)

    def test_source_scope_is_not_fabricated_as_dependency(self):
        self.assertTrue(all(item.relation in ('imports','reference') for item in self.search().results))
        self.assertFalse(any(item.certainty=='runtime-proven' for item in self.search().results))

if __name__=='__main__':unittest.main()
