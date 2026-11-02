"""End-to-end qualified variable creation through the existing Python adapter.

These tests check source identity, lexical dominance, round-trip graph parity,
exact UI-action qualification and negative safety boundaries. No code execution.
"""
import ast
from pathlib import Path
import tempfile
import unittest

from studio_native.authoring_contract import OperandReference, ValueAssignment, BinaryComposition
from studio_native.authoring_actions import available_actions, search_actions
from studio_native.python_authoring import (
    eligible_value_assignment_targets, compatible_value_assignment_pin,
    propose_assign_source_value, eligible_composition_targets, propose_compose_binary_local,
)
from studio_native.python_edit import apply_proposal
from studio_native.python_graph import PythonDocument, SourceError
from studio_native.semantic_contract import describe_graph


def reference(name): return OperandReference('name',name)
def literal(text): return OperandReference('literal',text)


class VariableAuthoringTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.file=Path(tmp.name)/'source.py'

    def doc(self,source='def calculate(number):\n    return number\n'):
        self.file.write_bytes(source if isinstance(source,bytes) else source.encode('utf-8'))
        return PythonDocument(self.file)

    def target(self,doc):
        candidates=eligible_value_assignment_targets(doc)
        self.assertTrue(candidates,'Expected at least one eligible final Return')
        return candidates[0]

    def save(self,doc,recipe):
        scope,_,anchor=self.target(doc)
        original=self.file.read_bytes()
        proposed=propose_assign_source_value(doc,scope,recipe,anchor)
        self.assertEqual(self.file.read_bytes(),original,'Preview must never mutate source')
        apply_proposal(proposed)
        after=PythonDocument(self.file)
        for key in after.scopes:
            describe_graph(after.scope_graph(key),origin='source')
        self.assertEqual(ast.dump(after.tree,include_attributes=False),
                         ast.dump(ast.parse(self.file.read_text()),include_attributes=False))
        return after

    def test_fresh_local_from_parameter_then_composition_and_return(self):
        first=self.save(self.doc(),ValueAssignment(reference('number'),'saved',False))
        self.assertEqual(self.file.read_text(),
            'def calculate(number):\n    saved = number\n    return number\n')
        scope,names,anchor=eligible_composition_targets(first)[0]
        self.assertIn('saved',names)
        composed=propose_compose_binary_local(first,scope,
            BinaryComposition(reference('saved'),'*',literal('2'),'doubled',True),anchor)
        apply_proposal(composed)
        self.assertEqual(self.file.read_text(),
            'def calculate(number):\n    saved = number\n    doubled = saved * 2\n    return doubled\n')
        self.assertEqual(self.file.read_text().count('saved = number'),1)
        parsed=PythonDocument(self.file)
        scope=next(k for k,v in parsed.scopes.items() if v.title=='calculate')
        graph=parsed.scope_graph(scope)
        self.assertGreaterEqual(sum(n['source_kind']=='assignment' for n in graph['nodes']),2)
        self.assertTrue(any(e['relation']=='data' for e in graph['edges']))

    def test_literal_value_even_without_function_parameters(self):
        doc=self.doc('def f():\n    return None\n')
        self.assertEqual(self.target(doc)[1],())
        self.save(doc,ValueAssignment(literal('42'),'answer',True))
        self.assertEqual(self.file.read_text(),'def f():\n    answer = 42\n    return answer\n')

    def test_constant_signed_literal_crlf_and_unicode_name(self):
        doc=self.doc('def café(δ):\r\n    return δ\r\n'.encode('utf-8'))
        self.save(doc,ValueAssignment(literal('-3.5'),'résultat',True))
        content=self.file.read_bytes()
        self.assertIn('    résultat = -3.5\r\n'.encode(),content)
        self.assertIn('    return résultat\r\n'.encode(),content)
        self.assertNotIn(b'\n',content.replace(b'\r\n',b''))

    def test_docstrings_and_preserved_returns(self):
        doc=self.doc('def f(x):\n    "doc"\n    return compute(x)\n')
        self.save(doc,ValueAssignment(literal('"hi"'),'text',False))
        self.assertIn('    "doc"\n    text = \'hi\'\n    return compute(x)',self.file.read_text())

    def test_effectful_return_must_not_be_replaced(self):
        doc=self.doc('def f(x):\n    return compute(x)\n')
        scope,_,anchor=self.target(doc)
        with self.assertRaisesRegex(SourceError,'effectful|compound'):
            propose_assign_source_value(doc,scope,ValueAssignment(reference('x'),'v',True),anchor)
        self.assertNotIn(b'v = ',self.file.read_bytes())

    def test_rebinding_and_invalid_identifier_are_rejected(self):
        doc=self.doc('def f(value):\n    return value\n')
        scope,_,anchor=self.target(doc)
        for name in ('value','bad-name','__secret','return',''):
            with self.subTest(name=name),self.assertRaises(SourceError):
                propose_assign_source_value(doc,scope,ValueAssignment(reference('value'),name),anchor)

    def test_cannot_reference_future_or_foreign_scope_names(self):
        doc=self.doc('def f(x):\n    return x\n\ndef g(y):\n    return y\n')
        scope,_,anchor=next(x for x in eligible_value_assignment_targets(doc)
                            if doc.scopes[x[0]].title=='f')
        for name in ('y','future','builtins','g'):
            with self.subTest(name=name),self.assertRaisesRegex(SourceError,'dominating'):
                propose_assign_source_value(doc,scope,ValueAssignment(reference(name),'v'),anchor)

    def test_refuse_ambiguous_flow_and_rebound_local(self):
        for source in ('def f(x):\n    if x: x=2\n    return x\n',
                       'def f(x):\n    for i in range(x): pass\n    return x\n',
                       'def f(x):\n    v=2\n    v=3\n    return v\n',
                       'def f(x):\n    try:\n        v=2\n    except: pass\n    return x\n',
                       '@wrapper\ndef f(x):\n    return x\n',
                       'async def f(x):\n    return x\n'):
            with self.subTest(source=source):
                doc=self.doc(source)
                self.assertEqual(eligible_value_assignment_targets(doc),())
                self.assertNotIn('python.assign-source-local.v1',
                                 {a.id for a in available_actions(doc)})

    def test_call_result_local_is_not_advertised_as_qualified_stored_value(self):
        doc=self.doc('def f(x):\n    v = external(x)\n    return v\n')
        self.assertFalse(eligible_value_assignment_targets(doc))

    def test_exact_port_id_is_required_for_pin_drop(self):
        doc=self.doc('def f(x):\n    stage = x + 1\n    return stage\n')
        scope,names,anchor=self.target(doc)
        graph=doc.scope_graph(scope)
        variable=next(n for n in graph['nodes'] if n['source_kind']=='assignment')
        port=next(p['id'] for p in variable['draft_ports']['outputs']
                  if p['id'].endswith(':outputs:value'))
        choices=[a for a in available_actions(doc,pin=(variable['id'],port))
                 if a.id=='python.assign-source-local.v1']
        self.assertEqual([(x.source_scope,x.parameter,x.anchor) for x in choices],
                         [(scope,'stage',anchor)])
        self.assertEqual(compatible_value_assignment_pin(doc,variable['id'],'not-a-port'),())
        self.assertNotIn('python.assign-source-local.v1',
                         {a.id for a in available_actions(doc,pin=(variable['id'],'not-a-port'))})

    def test_no_source_mutation_without_review_and_reject_stale_save(self):
        doc=self.doc()
        scope,_,anchor=self.target(doc)
        before=self.file.read_bytes()
        proposal=propose_assign_source_value(doc,scope,ValueAssignment(reference('number'),'saved'),anchor)
        self.assertEqual(self.file.read_bytes(),before)
        self.file.write_bytes(before+b'# external change\n')
        with self.assertRaises(SourceError):
            apply_proposal(proposal)
        self.assertNotIn(b'saved = ',self.file.read_bytes())

    def test_search_capabilities_and_neutral_contract(self):
        doc=self.doc()
        actions=available_actions(doc)
        self.assertIn('python.assign-source-local.v1',{x.id for x in actions})
        self.assertTrue(search_actions(actions,'variable'))
        with self.assertRaises(ValueError):ValueAssignment(reference('x'),'v','yes')
        self.assertEqual(ValueAssignment.__module__,'studio_native.authoring_contract')

    def test_gui_uses_canonical_source_action_and_single_forms(self):
        gui=(Path(__file__).parents[1]/'studio_native/gui.py').read_text()
        self.assertIn('self._selected_qualified_symbol()',gui)
        self.assertIn("'python.assign-source-local.v1'",gui)
        self.assertIn('propose_assign_source_value(self.python_doc',gui)
        self.assertIn("dialog.setObjectName('QualifiedVariableAssignmentDialog')",gui)
        self.assertIn("dialog.setObjectName('QualifiedBinaryCompositionDialog')",gui)
        self.assertIn("self.review_source_proposal(proposal)",gui)


if __name__=='__main__':unittest.main()
