"""Adapter-approved data flow, placeholder Return and source transaction regressions."""
import ast
import tempfile
import unittest
from pathlib import Path

from studio_native.operation_catalog import qualified_operations, function_boundaries
from studio_native.python_authoring import (
    eligible_targets, eligible_return_targets, eligible_pass_targets,
    propose_local_literal_return, propose_return_from_pass,
)
from studio_native.python_graph import PythonDocument, SourceError
from studio_native.python_edit import apply_proposal
from studio_native.semantic_contract import describe_graph


class ReturnAndBindingAuthoring(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'candidate.py'

    def document(self,text,encoding='utf-8'):
        self.path.write_bytes(text if isinstance(text,bytes) else text.encode(encoding))
        return PythonDocument(self.path)

    def local(self,source='def f(value):\n    return value\n',name='result',literal='42'):
        doc=self.document(source)
        key,_,anchors=eligible_return_targets(doc)[0]
        return doc,key,propose_local_literal_return(doc,key,name,literal,anchors[0])

    def test_adapter_catalog_has_three_explicit_lowerings_not_observed_templates(self):
        capabilities=qualified_operations('python')
        self.assertGreaterEqual(len(capabilities),3)  # Catalog grows via adapter qualification, not a frozen UI count
        self.assertEqual(len({item.id for item in capabilities}),len(capabilities))
        self.assertTrue(all(item.capability=='guarded-source-proposal' and item.language=='python' for item in capabilities))
        self.assertIn('assignment',capabilities[1].operation_kinds)
        self.assertIn('return',capabilities[2].operation_kinds)
        self.assertEqual(qualified_operations('rust'),())

    def test_local_creation_is_reviewable_without_modifying_file(self):
        doc,key,proposal=self.local()
        self.assertIn('+    result = 42',proposal.diff)
        self.assertIn('+    return result',proposal.diff)
        self.assertIn('-    return value',proposal.diff)
        self.assertEqual(doc.raw,proposal.original)
        self.assertEqual(self.path.read_bytes(),doc.raw)

    def test_actual_graph_has_assignment_to_return_data_and_control_wires(self):
        doc,key,proposal=self.local()
        backup=apply_proposal(proposal)
        self.assertEqual(backup.read_bytes(),doc.raw)
        updated=PythonDocument(self.path)
        graph=updated.presentation_graph(key)
        descriptor=describe_graph(graph,origin='source')
        assignment=next(n for n in graph['nodes'] if n['source_kind']=='assignment')
        returned=next(n for n in graph['nodes'] if n['source_kind']=='return')
        self.assertEqual(len([n for n in graph['nodes'] if n['source_kind']=='assignment']),1)
        self.assertEqual({e['relation'] for e in graph['edges'] if e['source']==assignment['id'] and e['target']==returned['id']}, {'control','data'})
        self.assertTrue(any(n.operation_kind=='assignment' for n in descriptor.nodes))
        self.assertTrue(any(n.operation_kind=='return' for n in descriptor.nodes))
        self.assertEqual(len(function_boundaries(describe_graph(
            updated.composite_file_graph(expanded={key}),origin='source'))),1)

    def test_parameterless_function_can_create_local_without_branch_eligibility(self):
        doc=self.document('def f():\n    return None\n')
        self.assertEqual(eligible_targets(doc),())
        key,parameters,anchors=eligible_return_targets(doc)[0]
        self.assertEqual(parameters,())
        proposal=propose_local_literal_return(doc,key,'output','True',anchors[0])
        self.assertIn(b'    output = True\n    return output',proposal.candidate)

    def test_rejected_name_collisions_and_invalid_identifiers(self):
        for bad in ('value','for','1value','__class__','a-b','x'*65):
            with self.subTest(bad=bad),self.assertRaises(SourceError):
                self.local(name=bad)
        for source in ('def f(value):\n    import os as alias\n    return value\n',
                       'def f(value):\n    try:\n        raise ValueError()\n    except Exception as caught:\n        pass\n    return value\n'):
            doc=self.document(source)
            key,_,anchors=eligible_return_targets(doc)[0]
            with self.assertRaises(SourceError):
                propose_local_literal_return(doc,key,'alias' if 'alias' in source else 'caught','0',anchors[0])

    def test_rejects_effectful_original_return_and_comments(self):
        for source in ('def f(value):\n    return print(value)\n',
                       'def f(value):\n    return value + 1\n',
                       'def f(value):\n    return value  # keep this meaning\n'):
            doc=self.document(source)
            candidates=eligible_return_targets(doc)
            if '# keep this meaning' in source:
                self.assertEqual(candidates,(), 'Commented Return must not be advertised as creatable')
            else:
                key,_,anchors=candidates[0]
                with self.assertRaises(SourceError):
                    propose_local_literal_return(doc,key,'saved','0',anchors[0])

    def test_rejects_arbitrary_expression_and_stale_anchor(self):
        doc=self.document('def f(value):\n    return value\n')
        key,_,anchors=eligible_return_targets(doc)[0]
        for literal in ('open("/tmp/x")','(1,2)','value','-4','1e400','[2]',"'x'*2"):
            with self.subTest(literal=literal),self.assertRaises(SourceError):
                propose_local_literal_return(doc,key,'saved',literal,anchors[0])
        with self.assertRaises(SourceError):
            propose_local_literal_return(doc,key,'saved','1',{'line':300})

    def test_crlf_and_utf8_source_unchanged_except_inserted_statements(self):
        source='def f(value):\r\n    return value\r\n'
        doc,key,proposal=self.local(source,'résultat','"été"')
        self.assertIn('    résultat = \'été\'\r\n    return résultat\r\n'.encode(),proposal.candidate)
        self.assertEqual(proposal.original,source.encode())

    def test_nested_function_only_modifies_selected_body(self):
        text='def outer(x):\n    def inner(y):\n        return y\n    return inner(x)\n'
        doc=self.document(text)
        key,_,anchors=next(t for t in eligible_return_targets(doc) if 'function:inner:' in t[0])
        proposal=propose_local_literal_return(doc,key,'local','2',anchors[0])
        self.assertIn(b'        local = 2\n        return local',proposal.candidate)
        self.assertIn(b'    return inner(x)',proposal.candidate)

    def test_stale_external_file_blocks_atomic_apply(self):
        _,_,proposal=self.local()
        self.path.write_bytes(proposal.original+b'# modified externally\n')
        with self.assertRaisesRegex(SourceError,'changed externally'):
            apply_proposal(proposal)

    def test_pass_only_function_builds_return_and_reparses(self):
        doc=self.document('def f(value):\n    pass\n')
        key,anchor=eligible_pass_targets(doc)[0]
        proposal=propose_return_from_pass(doc,key,'"ready"',anchor)
        self.assertEqual(self.path.read_bytes(),doc.raw)
        apply_proposal(proposal)
        updated=PythonDocument(self.path)
        desc=describe_graph(updated.presentation_graph(key),origin='source')
        self.assertEqual(len([n for n in desc.nodes if n.construct=='return']),1)
        self.assertNotIn(b'pass',self.path.read_bytes())

    def test_pass_docstring_crlf_and_scope_identity(self):
        text=b'def placeholder():\r\n    """keep me"""\r\n    pass\r\n'
        doc=self.document(text)
        key,anchor=eligible_pass_targets(doc)[0]
        proposal=propose_return_from_pass(doc,key,'None',anchor)
        self.assertEqual(proposal.candidate,b'def placeholder():\r\n    """keep me"""\r\n    return None\r\n')
        self.assertIn(key,PythonDocument(self.path).scopes)

    def test_pass_rejects_inline_multiple_statements_and_comments(self):
        for text in ('def f(): pass\n','def f():\n    pass; pass\n',
                     'def f():\n    pass # note\n','def f():\n    x=1\n    pass\n'):
            with self.subTest(text=text):
                self.assertEqual(eligible_pass_targets(self.document(text)),())

    def test_pass_rejects_stale_anchor_and_nonliteral(self):
        doc=self.document('def f():\n    pass\n')
        key,anchor=eligible_pass_targets(doc)[0]
        for invalid in ('2 + 4','lambda: 3','-4'):
            with self.assertRaises(SourceError):
                propose_return_from_pass(doc,key,invalid,anchor)
        with self.assertRaises(SourceError):
            propose_return_from_pass(doc,key,'3',dict(line=120,col=1,end_line=120,end_col=5))

    def test_function_entry_and_result_interfaces_follow_generated_return(self):
        doc=self.document('def f(arg):\n    pass\n')
        key,anchor=eligible_pass_targets(doc)[0]
        apply_proposal(propose_return_from_pass(doc,key,'0',anchor))
        updated=PythonDocument(self.path)
        graph=describe_graph(updated.composite_file_graph(expanded={key}),origin='source')
        boundaries=function_boundaries(graph)
        self.assertEqual(len(boundaries),1)
        self.assertEqual(len(boundaries[0].entry_bindings),1)
        self.assertEqual(len(boundaries[0].return_sites),1)

    def test_bundled_python_authoring_example_offers_each_qualified_anchor(self):
        file=Path(__file__).parents[1]/'examples/python-v12-qualified-authoring.py'
        doc=PythonDocument(file)
        self.assertTrue(eligible_targets(doc))
        self.assertTrue(eligible_return_targets(doc))
        self.assertTrue(eligible_pass_targets(doc))

    def test_qualified_ui_builder_ids_stay_synchronized_with_adapter(self):
        from pathlib import Path
        ui=(Path(__file__).parents[1]/'studio_native/gui.py').read_text()
        for definition in qualified_operations('python'):
            self.assertIn(definition.id,ui)
        self.assertIn('review_source_proposal(proposal)',ui)
        self.assertIn('canvas.source_view',ui)


if __name__=='__main__':
    unittest.main()
