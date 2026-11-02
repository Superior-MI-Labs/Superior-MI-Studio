"""Source-backed Branch creation and catalog qualification regressions."""
import ast
import tempfile
import unittest
from pathlib import Path

from studio_native.python_authoring import definitions, eligible_targets, propose_branch_early_return
from studio_native.operation_catalog import qualified_operations
from studio_native.python_graph import PythonDocument, SourceError
from studio_native.python_edit import apply_proposal
from studio_native.semantic_contract import describe_graph


class QualifiedBranchAuthoring(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'sample.py'
        self.source='def check(value):\n    result = value\n    return result\n'
        self.path.write_text(self.source)
        self.doc=PythonDocument(self.path)
        self.key,parameters,returns=eligible_targets(self.doc)[0]
        self.target=returns[0]

    def create(self,parameter='value',literal='None'):
        return propose_branch_early_return(self.doc,self.key,parameter,literal,self.target)

    def test_definition_is_explicit_qualified_adapter_capability(self):
        self.assertEqual(definitions(),qualified_operations('python'))
        self.assertEqual(definitions()[0].control_outputs,('true','false'))
        self.assertEqual(definitions()[0].capability,'guarded-source-proposal')
        self.assertEqual(qualified_operations('unknown'),())

    def test_creation_is_only_proposal_until_user_applies(self):
        proposal=self.create()
        self.assertIn('+    if value is None:',proposal.diff)
        self.assertIn('+        return None',proposal.diff)
        self.assertEqual(self.path.read_text(),self.source)
        self.assertEqual(self.doc.raw,proposal.original)

    def test_apply_reparse_and_canonical_control_ports(self):
        proposal=self.create()
        backup=apply_proposal(proposal)
        self.assertEqual(backup.read_text(),self.source)
        updated=PythonDocument(self.path)
        graph=updated.presentation_graph(self.key)
        valid=describe_graph(graph,origin='source')
        branches=[n for n in valid.nodes if n.operation_kind=='branch']
        self.assertEqual(len(branches),1)
        node=branches[0]
        self.assertEqual({p.label for p in node.ports if p.direction=='outputs' and p.type_id=='execution'}, {'true','false'})
        self.assertEqual(len([n for n in valid.nodes if n.construct=='return']),2)
        self.assertTrue(any(e.relation=='control' for e in valid.edges))
        self.assertEqual(ast.dump(ast.parse(self.path.read_text()).body[0].body[-1],include_attributes=False),
                         ast.dump(ast.parse(self.source).body[0].body[-1],include_attributes=False))

    def test_branch_false_path_continues_to_original_return_and_true_terminates(self):
        proposal=self.create()
        apply_proposal(proposal)
        graph=PythonDocument(self.path).presentation_graph(self.key)
        branch=next(n for n in graph['nodes'] if n['source_kind']=='branch')
        returns=sorted((n for n in graph['nodes'] if n['source_kind']=='return'),
                       key=lambda n:n['source_span']['line'])
        def route(name):
            out=next(p for p in branch['draft_ports']['outputs'] if p['label']==name)
            edges=[e for e in graph['edges'] if e['relation']=='control' and
                   e['source']==branch['id'] and e['sourcePort']==out['id']]
            self.assertEqual(len(edges),1)
            return edges[0]['target']
        self.assertEqual(route('true'),returns[0]['id'])
        self.assertEqual(route('false'),returns[1]['id'])

    def test_function_outer_ports_and_input_binding_stay_unchanged(self):
        from studio_native.operation_catalog import function_boundaries
        before=next(n for n in describe_graph(
            self.doc.composite_file_graph(expanded={self.key}),origin='source').nodes
            if n.semantic_role=='definition' and n.interface and n.interface.category=='function')
        apply_proposal(self.create())
        updated=PythonDocument(self.path)
        after=describe_graph(updated.composite_file_graph(expanded={self.key}),origin='source')
        definition=next(n for n in after.nodes if n.id==before.id)
        self.assertEqual(before.interface.inputs,definition.interface.inputs)
        self.assertEqual(before.interface.outputs,definition.interface.outputs)
        boundary=next(b for b in function_boundaries(after) if b.definition_id==before.id)
        self.assertEqual(len(boundary.return_sites),2)
        self.assertEqual(len(boundary.entry_bindings),1)
        self.assertEqual(boundary.result_port,before.interface.exits[0].value_port)

    def test_rejects_unqualified_expression_and_stale_anchor(self):
        for value in ('value + 1','__import__("os")','(1,2)','-1','a if b else c'):
            with self.subTest(value=value), self.assertRaises(SourceError):self.create(literal=value)
        with self.assertRaises(SourceError):self.create(parameter='__globals__')
        with self.assertRaises(SourceError):propose_branch_early_return(self.doc,self.key,'value','0',{'line':999,'col':0,'end_line':999,'end_col':9})

    def test_rejects_semicolon_suite_or_nested_return(self):
        self.path.write_text('def check(value): return value\n')
        self.assertEqual(eligible_targets(PythonDocument(self.path)),())
        self.path.write_text('def check(value):\n    if value:\n        return 1\n')
        self.assertEqual(eligible_targets(PythonDocument(self.path)),())
        self.path.write_text('def check(value):\n    return value; pass\n')
        self.assertEqual(eligible_targets(PythonDocument(self.path)),())

    def test_crlf_preserves_existing_bytes(self):
        source=b'def check(value):\r\n    return value\r\n'
        self.path.write_bytes(source)
        doc=PythonDocument(self.path)
        key,_,targets=eligible_targets(doc)[0]
        proposal=propose_branch_early_return(doc,key,'value','"x"',targets[0])
        self.assertIn(b'    if value is None:\r\n        return \'x\'\r\n    return value\r\n',proposal.candidate)
        self.assertEqual(proposal.original,source)

    def test_secondary_nested_function_target_preserves_outer_ast(self):
        self.path.write_text('def outer(x):\n    def inner(y):\n        return y\n    return inner(x)\n')
        doc=PythonDocument(self.path)
        nested=next(t for t in eligible_targets(doc) if t[0].endswith('function:inner:2:4'))
        proposal=propose_branch_early_return(doc,nested[0],'y','0',nested[2][0])
        modified=ast.parse(proposal.candidate.decode()).body[0]
        self.assertEqual(len(modified.body),2)
        self.assertIsInstance(modified.body[0].body[0],ast.If)

    def test_rejects_external_change_at_atomic_apply(self):
        proposal=self.create()
        self.path.write_text(self.source+'# external change\n')
        with self.assertRaisesRegex(SourceError,'changed externally'):
            apply_proposal(proposal)


if __name__=='__main__':unittest.main()
