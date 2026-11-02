"""v2.31 canonical control operations, no implicit IF/loop graph tunnels."""
import copy
import tempfile
import unittest
from pathlib import Path

from studio_native.python_graph import PythonDocument
from studio_native.semantic_contract import describe_graph, ContractError
from studio_native.operation_catalog import observed_operations, function_boundaries
from studio_native.exit_routes import project_exit_routes

SOURCE='''def f(values):
    total = 0
    for value in values:
        if value > 0:
            total += value
        else:
            total -= 1
    return total

def g(flag):
    if flag:
        return 1
    return 2
'''

class CanonicalControlOperationsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'source.py'
        self.path.write_text(SOURCE)
        self.doc=PythonDocument(self.path)
        self.scopes=set(self.doc.scopes)-{'module'}
        self.raw=self.doc.composite_file_graph(self.scopes)
        self.descriptor=describe_graph(self.raw,origin='source')

    def test_control_operations_have_no_implicit_child_graphs(self):
        controls=[n for n in self.descriptor.nodes if n.semantic_role=='control_operation']
        self.assertEqual({n.operation_kind for n in controls},{'branch','loop'})
        self.assertTrue(all(n.child_graph is None and n.child_graph is None and
                            n.interface.category in ('conditional','loop') for n in controls))
        self.assertTrue(all(not n.get('embedded_region') and not n.get('child_region_key')
                            for n in self.raw['nodes'] if n.get('source_kind') in ('branch','loop')))

    def test_statement_bodies_remain_source_backed_in_function_surface(self):
        fscope=next(k for k,s in self.doc.scopes.items() if s.title=='f')
        nodes=[n for n in self.raw['nodes'] if n.get('containing_scope')==fscope]
        self.assertTrue(any(n['source_kind']=='branch' for n in nodes))
        self.assertTrue(any(n['source_kind']=='loop' for n in nodes))
        self.assertTrue(any(n.get('source_construct')=='augmented_assignment' for n in nodes))
        self.assertTrue(all(n['x']>=0 and n['y']>=0 for n in nodes))

    def test_control_edges_and_nodes_match_source_analysis(self):
        fscope=next(k for k,s in self.doc.scopes.items() if s.title=='f')
        focused=self.doc.composite_file_graph(focus_scope=fscope)
        analysis=self.doc.presentation_graph(fscope)
        self.assertEqual({n['id'] for n in focused['nodes']},{n['id'] for n in analysis['nodes']})
        self.assertEqual({e['id'] for e in focused['edges']},{e['id'] for e in analysis['edges']})
        self.assertTrue(any(e['relation']=='control' for e in focused['edges']))
        self.assertEqual(SOURCE,self.path.read_text())

    def test_legacy_collapsed_region_state_cannot_hide_executable_nodes(self):
        other=self.doc.composite_file_graph(self.scopes,collapsed_regions={'legacy:branch','legacy:loop'})
        self.assertEqual(self.descriptor,describe_graph(other,origin='source'))
        self.assertEqual(tuple(n.get('presentation_hidden') for n in self.raw['nodes']),
                         tuple(n.get('presentation_hidden') for n in other['nodes']))

    def test_function_definitions_still_have_real_child_graphs(self):
        definitions=[n for n in self.descriptor.nodes if n.semantic_role=='definition'
                     and n.interface and n.interface.category=='function']
        self.assertEqual(len(definitions),2)
        self.assertTrue(all(n.definition_graph and n.child_graph for n in definitions))
        self.assertEqual(len(function_boundaries(self.descriptor)),2)
        self.assertEqual(len(project_exit_routes(self.descriptor)),3)

    def test_read_only_catalog_shares_validated_operation_contract(self):
        entries=observed_operations(self.descriptor)
        self.assertTrue({'branch','loop','definition'}<={x.kind for x in entries})
        self.assertTrue(all(x.authoring=='not-qualified' for x in entries))
        self.assertEqual({n.id for n in self.descriptor.nodes if n.operation_kind=='branch'},
                         {i for e in entries if e.kind=='branch' for i in e.occurrences})

    def test_contract_rejects_reintroduction_of_control_viewports(self):
        broken=copy.deepcopy(self.raw)
        branch=next(n for n in broken['nodes'] if n.get('source_kind')=='branch')
        branch['embedded_region']={'role':'conditional_body'}
        with self.assertRaisesRegex(ContractError,'nested graph viewport'):
            describe_graph(broken,origin='source')
        broken=copy.deepcopy(self.raw)
        branch=next(n for n in broken['nodes'] if n.get('source_kind')=='branch')
        branch['child_region_key']='fake:control-region'
        with self.assertRaisesRegex(ContractError,'nested graph viewport'):
            describe_graph(broken,origin='source')

    def test_no_unqualified_edit_or_source_modification(self):
        self.assertEqual(self.doc.raw,self.path.read_bytes())
        self.assertFalse(any(getattr(e,'authoring','not-qualified')!='not-qualified'
                             for e in observed_operations(self.descriptor)))

if __name__=='__main__':unittest.main()
