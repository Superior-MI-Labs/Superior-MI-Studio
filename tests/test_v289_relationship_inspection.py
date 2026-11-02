"""Inspect only validated, visible file relationships from a single canvas revision."""
import tempfile
import unittest
from pathlib import Path

from studio_native.resource_graph import directory_graph, inspect_resource_relationship
from studio_native.semantic_contract import ContractError,describe_graph


class RelationshipInspectionContract(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        (self.root/'assets').mkdir()
        self.src=self.root/'main.py'
        self.src.write_text('import helper\nopen("assets/icon.png")\n')
        self.target=self.root/'helper.py';self.target.write_text('value=1\n')
        self.asset=self.root/'assets'/'icon.png';self.asset.write_bytes(b'png')
        self.graph=directory_graph(self.root,show_imports=True,expanded_paths=[self.root/'assets'])
        self.contract=describe_graph(self.graph,origin='resource')

    def get(self,relation='imports'):
        edge=next(e for e in self.contract.edges if e.relation==relation)
        return inspect_resource_relationship(self.contract,self.graph,edge.id)

    def test_existing_imports_use_exact_contract_evidence(self):
        item=self.get()
        self.assertEqual(item.source,self.src)
        self.assertEqual(item.target,self.target)
        self.assertEqual(item.relation,'imports')
        self.assertEqual(item.certainty,'local-file-candidate')
        self.assertEqual(item.evidence[0].line,1)
        self.assertEqual(item.evidence[0].syntax,'import helper')

    def test_asset_endpoint_and_syntax_have_no_runtime_claim(self):
        item=self.get('reference')
        self.assertEqual(item.target,self.asset)
        self.assertEqual(item.certainty,'literal-path-candidate')
        self.assertIn('assets/icon.png',item.evidence[0].syntax)

    def test_unknown_hidden_and_unvalidated_edge_refused(self):
        with self.assertRaisesRegex(ContractError,'No inspectable'):
            inspect_resource_relationship(self.contract,self.graph,'missing')
        other=directory_graph(self.root,show_imports=False)
        with self.assertRaisesRegex(ContractError,'differ from the validated'):
            inspect_resource_relationship(self.contract,other,self.contract.edges[0].id)

    def test_mutated_edges_cannot_be_interpreted_from_stale_revision(self):
        self.graph['edges'][0]['target']='resource:tampered'
        with self.assertRaisesRegex(ContractError,'changed after validation'):
            self.get()

    def test_mutated_resource_node_path_cannot_redirect_navigation(self):
        victim=next(n for n in self.graph['nodes'] if n.get('resource_path')==str(self.target))
        victim['resource_path']=str(self.asset)
        with self.assertRaisesRegex(ContractError,'identity changed'):
            self.get()

    def test_symlink_retarget_refused_after_evidence_collected(self):
        self.asset.unlink()
        (self.root/'sneaky.png').write_bytes(b'other')
        self.asset.symlink_to(self.root/'sneaky.png')
        with self.assertRaisesRegex(ContractError,'symlink'):
            self.get('reference')

    def test_directory_symlink_retarget_refused(self):
        (self.root/'assets'/'icon.png').unlink()
        (self.root/'assets').rmdir()
        real=self.root/'relocated';real.mkdir()
        (real/'icon.png').write_bytes(b'png')
        (self.root/'assets').symlink_to(real,target_is_directory=True)
        with self.assertRaisesRegex(ContractError,'symlink'):
            self.get('reference')

    def test_empty_layer_graph_has_no_inspectable_candidates(self):
        graph=directory_graph(self.root,show_imports=True,relationship_kinds=())
        contract=describe_graph(graph,origin='resource')
        with self.assertRaises(ContractError):
            inspect_resource_relationship(contract,graph,self.contract.edges[0].id)

    def test_source_descriptor_cannot_inspect_resource_edges(self):
        from dataclasses import replace
        wrong=replace(self.contract,origin='source')
        with self.assertRaisesRegex(ContractError,'requires a resource graph'):
            inspect_resource_relationship(wrong,self.graph,self.contract.edges[0].id)


if __name__=='__main__':unittest.main()
