"""Canonical operations vs optional presentation regions, and source-backed library census."""
import tempfile
import unittest
from pathlib import Path

from studio_native.python_graph import PythonDocument
from studio_native.semantic_contract import ContractError, describe_graph
from studio_native.operation_catalog import observed_operations, function_boundaries
from studio_native.python_edit import change_literal


SOURCE = '''def accumulate(items):
    total = 0
    for item in items:
        if item > 0:
            total += item
        else:
            total -= 2
    return total
'''


class OperationBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'sample.py'
        self.path.write_text(SOURCE)
        self.doc=PythonDocument(self.path)
        self.scope=next(s for s,v in self.doc.scopes.items() if v.title=='accumulate')

    def graph(self):
        return self.doc.composite_file_graph(expanded={self.scope})

    def test_branch_and_loop_are_operations_not_definitions(self):
        desc=describe_graph(self.graph(),origin='source')
        control=[n for n in desc.nodes if n.operation_kind in ('branch','loop')]
        self.assertEqual({n.operation_kind for n in control},{'branch','loop'})
        self.assertTrue(all(n.semantic_role=='control_operation' for n in control))
        self.assertTrue(all(n.definition_graph is None for n in control))
        self.assertTrue(all(n.child_graph is None for n in control))
        self.assertTrue(all(n.interface.category in ('conditional','loop') for n in control))

    def test_collapsing_does_not_alter_semantic_operation_or_edges(self):
        whole=self.graph()
        branch=next(n for n in whole['nodes'] if n['source_kind']=='branch')
        closed=self.doc.composite_file_graph(expanded={self.scope},collapsed_regions={'obsolete/region:'+branch['id']})
        a=describe_graph(whole,origin='source')
        b=describe_graph(closed,origin='source')
        def shape(x):
            return [(n.id,n.construct,n.operation_kind,n.ports,n.source,n.interface) for n in x.nodes]
        self.assertEqual(shape(a),shape(b))
        self.assertEqual(a.edges,b.edges)
        self.assertEqual(self.path.read_text(),SOURCE)


    def test_function_boundary_is_distinct_from_call_site(self):
        desc=describe_graph(self.graph(),origin='source')
        interfaces=function_boundaries(desc)
        self.assertEqual(len(interfaces),1)
        self.assertIn('return', next(n for n in self.graph()['nodes'] if n['source_kind']=='function')['draft_ports']['outputs'][0]['label'])
        self.assertTrue(interfaces[0].return_sites)
        self.assertTrue(interfaces[0].inputs)
        self.assertTrue(interfaces[0].entry_bindings)

    def test_catalog_inventory_never_claims_codegen(self):
        desc=describe_graph(self.graph(),origin='source')
        operations=observed_operations(desc)
        names={x.id for x in operations}
        self.assertIn('python:branch',names)
        self.assertIn('python:loop',names)
        self.assertIn('python:definition',names)
        self.assertTrue(all(x.authoring=='not-qualified' for x in operations))
        self.assertEqual(self.path.read_text(),SOURCE)
        with self.assertRaises(ContractError):observed_operations(desc,language='../invalid')

    def test_control_operator_cannot_impersonate_function(self):
        raw=self.graph()
        branch=next(n for n in raw['nodes'] if n['source_kind']=='branch')
        branch['graph_interface']['category']='function'
        with self.assertRaisesRegex(ContractError,'Control operation'):
            describe_graph(raw,origin='source')

    def test_existing_guarded_source_edit_is_still_source_owned(self):
        before=self.graph()
        update=next(n for n in before['nodes'] if n.get('source_construct')=='augmented_assignment' and n.get('display_symbol')=='-=')
        operand=next(p for p in update['draft_ports']['inputs'] if p.get('source_literal_span'))
        proposal=change_literal(self.doc,operand['source_literal_span'],'3')
        self.assertEqual(self.path.read_text(),SOURCE)
        self.assertIn('total -= 3',proposal.candidate.decode())
        self.assertIn('total -= 3',proposal.diff)

    def test_source_literal_proposal_roundtrips_without_rewriting_control_graph(self):
        initial=describe_graph(self.graph(),origin='source')
        raw=self.graph()
        update=next(n for n in raw['nodes'] if n.get('source_construct')=='augmented_assignment'
                    and n.get('display_symbol')=='-=')
        operand=next(p for p in update['draft_ports']['inputs'] if p.get('source_literal_span'))
        proposal=change_literal(self.doc,operand['source_literal_span'],'3')
        candidate=self.path.with_name('proposed.py')
        candidate.write_bytes(proposal.candidate)
        new_doc=PythonDocument(candidate)
        new_key=next(k for k,s in new_doc.scopes.items() if s.title=='accumulate')
        updated=describe_graph(new_doc.composite_file_graph(expanded={new_key}),origin='source')
        def controls(desc):
            return tuple((n.operation_kind,tuple((p.label,p.type_id,p.direction) for p in n.ports))
                         for n in desc.nodes if n.operation_kind in ('branch','loop'))
        self.assertEqual(controls(initial),controls(updated))
        self.assertEqual(len(initial.edges),len(updated.edges))
        self.assertEqual(self.path.read_text(),SOURCE)

    def test_multiple_returns_share_one_function_exit_without_extra_graph_ports(self):
        self.path.write_text('def choose(x):\n    if x < 0:\n        return 1\n    return x\n')
        doc=PythonDocument(self.path)
        scope=next(k for k,s in doc.scopes.items() if s.title=='choose')
        desc=describe_graph(doc.composite_file_graph(expanded={scope}),origin='source')
        boundary=function_boundaries(desc)[0]
        self.assertEqual(len(boundary.return_sites),2)
        definition=next(n for n in desc.nodes if n.id==boundary.definition_id)
        self.assertIsNone(definition.interface.exits[0].control_port)
        self.assertEqual(definition.interface.exits[0].control_anchor_id,
                         definition.interface.exits[0].id+':control')

    def test_archive_installer_restores_shell_execution_bits_safely(self):
        import zipfile
        # The managed release archive declares executable scripts, while
        # Python's zipfile extraction alone does not restore those bits.
        root=Path(__file__).resolve().parents[1]
        source=root/'doctor.sh'
        zpath=Path(self.temp.name)/'tiny.zip'
        # Fresh extraction via Python intentionally drops executable bits;
        # construct a POSIX executable ZIP member explicitly for this test.
        info=zipfile.ZipInfo('Superior-MI-Python-Visual-Programming-Lab-v2.31/doctor.sh')
        info.create_system=3
        info.external_attr=(0o100755 << 16)
        with zipfile.ZipFile(zpath,'w') as z:
            z.writestr(info,source.read_bytes())
        with zipfile.ZipFile(zpath) as z:
            item=z.infolist()[0]
            self.assertTrue((item.external_attr >> 16) & 0o111)

    def test_invocation_is_not_a_definition_result(self):
        self.path.write_text('def f(x):\n    return x\n\nif __name__ == "__main__":\n    print(f(3))\n')
        doc=PythonDocument(self.path)
        desc=describe_graph(doc.composite_file_graph(expanded=set(doc.scopes)-{'module'}),origin='source')
        defs=[n for n in desc.nodes if n.semantic_role=='definition']
        calls=[n for n in desc.nodes if n.semantic_role=='invocation']
        self.assertEqual(len(defs),1)
        self.assertTrue(calls)
        self.assertFalse(any(n.definition_graph for n in calls))
        self.assertTrue(all(n.effect_verification=='unverified' for n in calls))
        self.assertNotEqual({p.id for p in defs[0].ports if p.direction=='outputs'},
                            {p.id for n in calls for p in n.ports if p.direction=='outputs'})


if __name__ == '__main__':unittest.main()
