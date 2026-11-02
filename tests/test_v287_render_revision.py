"""v2.87: raw renderer edges and descriptors belong to one canvas revision."""
import ast
import tempfile
import unittest
from pathlib import Path

from studio_native.resource_graph import directory_graph
from studio_native.semantic_contract import (
    ContractError, describe_graph, validated_edge_payloads,
)


class CanvasRevisionTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        (self.root/'assets').mkdir()
        (self.root/'assets'/'icon.png').write_bytes(b'not an actual image')
        (self.root/'main.py').write_text("open('assets/icon.png')\n")

    def two_revisions(self):
        with_relation=directory_graph(self.root,show_imports=True,
                                      expanded_paths=(self.root/'assets',))
        without_relation=directory_graph(self.root,show_imports=False)
        return with_relation,without_relation

    def test_resource_descriptor_and_paint_payloads_share_exact_revision(self):
        graph,other=self.two_revisions()
        contract=describe_graph(graph,origin='resource')
        self.assertEqual(len(contract.edges),1)
        self.assertEqual(validated_edge_payloads(contract,graph)[0]['id'],contract.edges[0].id)
        self.assertEqual(len(other['edges']),0)

    def test_inactive_tab_must_not_resolve_edges_from_new_active_tab(self):
        graph,other=self.two_revisions()
        old_contract=describe_graph(graph,origin='resource')
        new_contract=describe_graph(other,origin='resource')
        # The old graph can still paint correctly after another selected tab
        # updates the window's compatibility resource alias.
        self.assertEqual(len(validated_edge_payloads(old_contract,graph)),1)
        self.assertEqual(validated_edge_payloads(new_contract,other),())
        with self.assertRaisesRegex(ContractError,'differ from the validated'):
            validated_edge_payloads(old_contract,other)

    def test_deleted_relation_in_same_graph_revision_is_detected(self):
        graph,_=self.two_revisions()
        contract=describe_graph(graph,origin='resource')
        graph['edges'].clear()
        with self.assertRaisesRegex(ContractError,'differ from the validated'):
            validated_edge_payloads(contract,graph)

    def test_unexpected_added_relation_is_not_silently_painted(self):
        graph,other=self.two_revisions()
        contract=describe_graph(other,origin='resource')
        other['edges']=graph['edges']
        with self.assertRaisesRegex(ContractError,'differ from the validated'):
            validated_edge_payloads(contract,other)

    def test_changed_identity_or_endpoint_is_refused(self):
        graph,_=self.two_revisions()
        contract=describe_graph(graph,origin='resource')
        graph['edges'][0]['target']='wrong-resource-node'
        with self.assertRaisesRegex(ContractError,'endpoints/relationship changed'):
            validated_edge_payloads(contract,graph)

    def test_duplicate_payload_ids_refused(self):
        graph,_=self.two_revisions()
        contract=describe_graph(graph,origin='resource')
        graph['edges'].append(dict(graph['edges'][0]))
        with self.assertRaisesRegex(ContractError,'differ from the validated'):
            validated_edge_payloads(contract,graph)

    def test_provenance_survives_ordered_presentation(self):
        graph,_=self.two_revisions()
        contract=describe_graph(graph,origin='resource')
        raw=validated_edge_payloads(contract,graph)[0]
        self.assertEqual(raw['certainty'],'literal-path-candidate')
        self.assertEqual(raw['relation'],'reference')
        self.assertEqual(raw['provenance'][0]['syntax'],contract.edges[0].evidence[0].syntax)

    def test_renderer_edge_refresh_has_no_window_graph_alias(self):
        # Native Qt validates behavior. This cheap source boundary check guards
        # against reintroducing the same alias dependency before host testing.
        source=(Path(__file__).resolve().parents[1]/'studio_native'/'gui.py').read_text()
        tree=ast.parse(source)
        canvas=next(node for node in tree.body if isinstance(node,ast.ClassDef)
                    and node.name=='GraphCanvas')
        refresh=next(node for node in canvas.body if isinstance(node,ast.FunctionDef)
                     and node.name=='update_edges')
        body=ast.get_source_segment(source,refresh)
        self.assertIn('self._render_graph',body)
        self.assertNotIn('self.window.resource_graph',body)
        self.assertNotIn('self.window.source_graph',body)


if __name__=='__main__':
    unittest.main()
