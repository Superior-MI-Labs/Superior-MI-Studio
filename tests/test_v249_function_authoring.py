"""Integrated function call/renaming milestone, using one source authority."""
import ast
from pathlib import Path
import tempfile
import unittest

from studio_native.authoring_contract import CallComposition,OperandReference
from studio_native.authoring_actions import available_actions, search_actions
from studio_native.python_authoring import (
    eligible_composed_call_targets, compatible_composed_call_pin,
    propose_composed_call, eligible_rename_functions, propose_rename_function,
    eligible_parameter_renames, propose_rename_parameter,
    propose_assign_source_value,
)
from studio_native.authoring_contract import ValueAssignment
from studio_native.python_graph import PythonDocument, SourceError
from studio_native.python_edit import apply_proposal
from studio_native.semantic_contract import describe_graph


def ref(name):return OperandReference('name',name)
def lit(value):return OperandReference('literal',value)


class FunctionWorkflow(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.path=Path(temporary.name)/'sample.py'

    def doc(self,text):
        self.path.write_bytes(text if isinstance(text,bytes) else text.encode('utf-8'))
        return PythonDocument(self.path)

    def candidate(self,doc):
        targets=eligible_composed_call_targets(doc)
        self.assertTrue(targets)
        return next(x for x in targets if doc.scopes[x[0]].title=='caller')

    def apply(self,proposal):
        self.assertEqual(self.path.read_bytes(),proposal.original)
        apply_proposal(proposal)
        doc=PythonDocument(self.path)
        for key in doc.scopes:
            describe_graph(doc.scope_graph(key),origin='source')
        self.assertEqual(ast.dump(doc.tree,include_attributes=False),
                         ast.dump(ast.parse(self.path.read_text()),include_attributes=False))
        return doc

    def test_store_call_with_existing_local_and_second_literal(self):
        doc=self.doc('def helper(x, offset):\n    return x + offset\n\ndef caller(value):\n    seed = value + 2\n    return value\n')
        scope,names,anchor,callees=self.candidate(doc)
        self.assertIn('seed',names)
        self.assertEqual(dict(callees)['helper'],('x','offset'))
        proposal=propose_composed_call(doc,scope,CallComposition('helper',
            (ref('seed'),lit('3')),'result',True),anchor)
        self.assertIn(b'    result = helper(seed, 3)\n    return result',proposal.candidate)
        after=self.apply(proposal)
        self.assertEqual(self.path.read_text().count('seed = value + 2'),1)
        graph=after.scope_graph(next(key for key,value in after.scopes.items() if value.title=='caller'))
        self.assertTrue(any(n.get('source_kind')=='call' for n in graph['nodes']))

    def test_call_two_bound_values_preserves_old_return(self):
        doc=self.doc('def helper(x, y):\n    return x + y\n\ndef caller(value):\n    second = value * 2\n    return value\n')
        scope,names,anchor,_=self.candidate(doc)
        self.apply(propose_composed_call(doc,scope,CallComposition('helper',
            (ref('value'),ref('second')),'total',False),anchor))
        self.assertIn('    total = helper(value, second)\n    return value',self.path.read_text())

    def test_call_result_is_reusable_without_reexecuting_the_call(self):
        doc=self.doc('def helper(x):\n    return x + 1\n\ndef caller(value):\n    return value\n')
        scope,_,anchor,_=self.candidate(doc)
        second=self.apply(propose_composed_call(doc,scope,CallComposition('helper',
                          (ref('value'),),'fetched',False),anchor))
        from studio_native.authoring_contract import BinaryComposition
        from studio_native.python_authoring import propose_compose_binary_local,eligible_composition_targets
        matched=next((scope,names,anchor) for scope,names,anchor in eligible_composition_targets(second)
                     if second.scopes[scope].title=='caller')
        self.assertIn('fetched',matched[1])
        self.apply(propose_compose_binary_local(second,matched[0],BinaryComposition(
              ref('fetched'),'*',lit('3'),'answer',True),matched[2]))
        text=self.path.read_text()
        self.assertEqual(text.count('helper(value)'),1)
        self.assertIn('fetched = helper(value)\n    answer = fetched * 3\n    return answer',text)

    def test_existing_unqualified_effectful_call_not_exposed_as_dataflow(self):
        doc=self.doc('def helper(x):\n    return x\n\ndef caller(value):\n    result = mystery(value)\n    return value\n')
        self.assertFalse(any(doc.scopes[scope].title=='caller' for scope,_,_,_ in eligible_composed_call_targets(doc)))

    def test_parameterless_caller_uses_literals(self):
        doc=self.doc('def helper(x):\n    return x\n\ndef caller():\n    return None\n')
        scope,_,anchor,_=self.candidate(doc)
        self.apply(propose_composed_call(doc,scope,CallComposition('helper',(lit('7'),),'out'),anchor))
        self.assertIn('out = helper(7)\n    return out',self.path.read_text())

    def test_pindrop_only_exact_producers(self):
        doc=self.doc('def helper(x):\n    return x\n\ndef caller(value):\n    return value\n')
        scope,_,anchor,_=self.candidate(doc)
        identifier=f'py:{scope}|param|value'
        actions=available_actions(doc,pin=(identifier,identifier+':outputs:value'))
        # Some graphs use :outputs:<name> on param pins; source proof decides.
        graph=doc.scope_graph(scope)
        source=next(n for n in graph['nodes'] if n['source_kind']=='param')
        for port in source['draft_ports']['outputs']:
            exact=available_actions(doc,pin=(source['id'],port['id']))
            if exact:
                self.assertIn('python.call-with-values.v1',{a.id for a in exact})
                break
        else:self.fail('No eligible producer pin found')
        self.assertEqual(compatible_composed_call_pin(doc,'forged','forged'),())

    def test_refuse_invalid_call_arguments_and_unsafe_returns(self):
        doc=self.doc('def helper(x, y):\n    return x\n\ndef caller(v):\n    return v\n')
        scope,_,anchor,_=self.candidate(doc)
        for req in (CallComposition('helper',(ref('foreign'),lit('2')),'r'),
                    CallComposition('helper',(ref('v'),),'r'),
                    CallComposition('not_here',(ref('v'),lit('1')),'r'),
                    CallComposition('helper',(ref('v'),lit('__import__("os")')),'r')):
            with self.subTest(req=req),self.assertRaises(SourceError):
                propose_composed_call(doc,scope,req,anchor)
        with self.assertRaises(ValueError):CallComposition('helper',(), 'r')
        doc=self.doc('def helper(x):\n    return x\n\ndef caller(v):\n    return print(v)\n')
        scope,_,anchor,_=self.candidate(doc)
        with self.assertRaisesRegex(SourceError,'effectful|compound'):
            propose_composed_call(doc,scope,CallComposition('helper',(ref('v'),),'r'),anchor)

    def test_refuse_ambiguous_scope_effects_rebindings(self):
        for source in (
            'def helper(x):\n    return x\n\ndef caller(x):\n    if x: x=2\n    return x\n',
            'def helper(x):\n    return x\n\ndef caller(x):\n    y=print(x)\n    return x\n',
            'def helper(x):\n    return x\n\ndef caller(x):\n    x=3\n    return x\n',
            '@decorator\ndef caller(x):\n    return x\n\ndef helper(x):\n    return x\n',
        ):
            with self.subTest(source=source):
                doc=self.doc(source)
                self.assertFalse(any(doc.scopes[scope].title=='caller'
                                     for scope,_,_,_ in eligible_composed_call_targets(doc)))

    def test_rename_updates_all_direct_calls_and_recursive_body(self):
        doc=self.doc('def helper(x):\n    return helper(x-1) if x else 0\n\ndef caller(value):\n    return helper(value)\n\nhelper(2)\n')
        self.assertIn('helper',eligible_rename_functions(doc))
        proposal=propose_rename_function(doc,'helper','calculate')
        self.assertEqual(self.path.read_bytes(),doc.raw)
        self.apply(proposal)
        self.assertEqual(self.path.read_text().count('calculate'),4)
        self.assertNotIn('helper',self.path.read_text())

    def test_rename_module_unicode_crlf_comments_preserved(self):
        doc=self.doc('def éclair(δ):\r\n    return δ  # never touch\r\n\r\ndef caller(z):\r\n    return éclair(z)\r\n'.encode('utf-8'))
        self.apply(propose_rename_function(doc,'éclair','café'))
        self.assertIn('def café(δ):\r\n'.encode(),self.path.read_bytes())
        self.assertIn('return δ  # never touch'.encode(),self.path.read_bytes())
        self.assertNotIn(b'\n',self.path.read_bytes().replace(b'\r\n',b''))

    def test_rename_rejects_ambiguous_alias_or_shadowing(self):
        cases=(
            'def helper(x):\n    return x\nf = helper\n',
            'def helper(x):\n    return x\ndef caller(helper):\n    return helper(1)\n',
            'def helper(x):\n    return x\ndef helper(y):\n    return y\n',
            '@decorator\ndef helper(x):\n    return x\n',
            'def helper(x):\n    return x\ndef caller():\n    return getattr(obj,"helper")\n',
            '__all__=["helper"]\ndef helper(x):\n    return x\n',
        )
        for case in cases:
            with self.subTest(case=case):
                doc=self.doc(case)
                self.assertNotIn('helper',eligible_rename_functions(doc))
                with self.assertRaises(SourceError):propose_rename_function(doc,'helper','renamed')

    def test_rename_rejects_builtins_collisions_and_nonidentifier(self):
        doc=self.doc('def helper(x):\n    return x\n\ndef caller(z):\n    return helper(z)\n')
        for name in ('helper','print','caller','for','__private','x', 'a-b'):
            with self.subTest(name=name),self.assertRaises(SourceError):
                propose_rename_function(doc,'helper',name)

    def test_stale_function_edits_are_rejected_at_save(self):
        doc=self.doc('def helper(x):\n    return x\n\ndef caller(y):\n    return helper(y)\n')
        rename=propose_rename_function(doc,'helper','compute')
        self.path.write_bytes(doc.raw+b'# parallel writer\n')
        with self.assertRaisesRegex(ValueError,'externally'):apply_proposal(rename)


    def test_rename_parameter_updates_body_positional_and_keywords(self):
        doc=self.doc('def helper(number, shift=2):\n    result = number + shift\n    return result\n\ndef caller(a):\n    return helper(a, shift=4)\n\nhelper(number=3)\n')
        self.assertIn(('helper',('number','shift')),eligible_parameter_renames(doc))
        proposal=propose_rename_parameter(doc,'helper','number','input_value')
        self.apply(proposal)
        self.assertIn('def helper(input_value, shift=2)',self.path.read_text())
        self.assertIn('result = input_value + shift',self.path.read_text())
        self.assertIn('helper(input_value=3)',self.path.read_text())
        self.assertIn('helper(a, shift=4)',self.path.read_text())
        next_doc=PythonDocument(self.path)
        self.apply(propose_rename_parameter(next_doc,'helper','shift','offset'))
        self.assertIn('def helper(input_value, offset=2)',self.path.read_text())
        self.assertIn('helper(a, offset=4)',self.path.read_text())

    def test_parameter_rename_works_with_unicode_and_crlf(self):
        doc=self.doc('def café(énergie):\r\n    return énergie\r\n\r\nprint(café(énergie=4))\r\n'.encode())
        self.apply(propose_rename_parameter(doc,'café','énergie','valeur'))
        contents=self.path.read_bytes()
        self.assertIn('def café(valeur):\r\n'.encode(),contents)
        self.assertIn('return valeur\r\n'.encode(),contents)
        self.assertIn('café(valeur=4)'.encode(),contents)
        self.assertNotIn(b'\n',contents.replace(b'\r\n',b''))

    def test_parameter_rename_rejects_unsafe_bindings_and_dynamic_calls(self):
        cases=(
            'def helper(x):\n    x = 3\n    return x\n',
            'def helper(x):\n    return lambda: x\n',
            'def helper(x):\n    return [x for _ in range(1)]\n',
            'def helper(x):\n    return x\nhelper(**{ "x": 3 })\n',
            'def helper(x):\n    return x\nhelper(*[3])\n',
            '@decorator\ndef helper(x):\n    return x\n',
        )
        for case in cases:
            with self.subTest(case=case):
                doc=self.doc(case)
                self.assertFalse(any(fn=='helper' and 'x' in names
                            for fn,names in eligible_parameter_renames(doc)))
                with self.assertRaises(SourceError):propose_rename_parameter(doc,'helper','x','new_x')

    def test_parameter_rename_refuses_collision_and_stale_save(self):
        doc=self.doc('def helper(x, y):\n    temp = x + y\n    return temp\n')
        for name in ('y','temp','helper','print','for','x','__x'):
            with self.subTest(name=name),self.assertRaises(SourceError):
                propose_rename_parameter(doc,'helper','x',name)
        proposal=propose_rename_parameter(doc,'helper','x','new_x')
        self.path.write_bytes(doc.raw+b'# changed\n')
        with self.assertRaises(ValueError):apply_proposal(proposal)

    def test_actions_are_single_catalog_and_qualified(self):
        doc=self.doc('def helper(x):\n    return x\n\ndef caller(v):\n    return v\n')
        actions=available_actions(doc)
        names={x.id for x in actions}
        self.assertIn('python.call-with-values.v1',names)
        self.assertIn('python.rename-function.v1',names)
        self.assertIn('python.rename-parameter.v1',names)
        self.assertEqual({a.id for a in search_actions(actions,'function rename')},
                         {'python.rename-function.v1','python.rename-parameter.v1'})
        # A declaration without any caller is still legitimately renameable.
        doc=self.doc('def helper(x):\n    return x\n')
        self.assertIn('python.rename-function.v1',{a.id for a in available_actions(doc)})
        self.assertNotIn('python.call-with-values.v1',{a.id for a in available_actions(doc)})


if __name__=='__main__':unittest.main()
