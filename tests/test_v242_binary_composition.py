"""v2.42: composable dataflow authoring, without introducing a Python-specific core IR."""
import ast
from pathlib import Path
import tempfile
import unittest
from studio_native.authoring_contract import OperandReference, BinaryComposition
from studio_native.authoring_actions import available_actions, search_actions
from studio_native.python_authoring import (eligible_composition_targets,
                                             propose_compose_binary_local,
                                             propose_create_function,propose_return_parameter_from_pass,
                                             eligible_parameter_returns)
from studio_native.python_edit import apply_proposal
from studio_native.python_graph import PythonDocument,SourceError
from studio_native.semantic_contract import describe_graph


def ref(name):return OperandReference('name',name)
def lit(text):return OperandReference('literal',text)


class BinaryCompositionTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.p=Path(temp.name)/'candidate.py'

    def doc(self,body='def f(x):\n    return x\n'):
        self.p.write_bytes(body if isinstance(body,bytes) else body.encode('utf-8'))
        return PythonDocument(self.p)

    def qualified(self,doc):
        candidates=eligible_composition_targets(doc)
        self.assertTrue(candidates)
        return candidates[0]

    def make(self,doc,recipe):
        scope,_,anchor=self.qualified(doc)
        proposal=propose_compose_binary_local(doc,scope,recipe,anchor)
        self.assertEqual(self.p.read_bytes(),doc.raw,'preview cannot save')
        apply_proposal(proposal)
        rebuilt=PythonDocument(self.p)
        for key in rebuilt.scopes:describe_graph(rebuilt.scope_graph(key),origin='source')
        return rebuilt

    def test_chain_two_operations_as_real_local_dependencies(self):
        d=self.doc()
        a=self.make(d,BinaryComposition(ref('x'),'+',lit('2'),'stage',False))
        scope,names,_=self.qualified(a)
        self.assertIn('stage',names)
        b=self.make(a,BinaryComposition(ref('stage'),'*',lit('3'),'total',True))
        self.assertEqual(self.p.read_text(),'def f(x):\n    stage = x + 2\n    total = stage * 3\n    return total\n')
        scope=next(k for k,v in b.scopes.items() if v.title=='f')
        graph=b.scope_graph(scope)
        self.assertGreaterEqual(sum(n['source_kind']=='assignment' for n in graph['nodes']),2)
        self.assertTrue(any(e['relation']=='data' for e in graph['edges']))
        self.assertEqual(ast.dump(b.tree,include_attributes=False),
                         ast.dump(ast.parse(self.p.read_text()),include_attributes=False))

    def test_comparison_two_existing_sources(self):
        doc=self.doc('def f(x, y):\n    return x\n')
        self.make(doc,BinaryComposition(ref('x'),'>=',ref('y'),'is_bigger',True))
        self.assertIn('is_bigger = x >= y\n    return is_bigger',self.p.read_text())
        self.assertTrue(any(n['source_kind']=='compare' for scope in PythonDocument(self.p).scopes
                            for n in PythonDocument(self.p).scope_graph(scope)['nodes']))

    def test_literal_comparison_signed_negative_and_crlf_unicode(self):
        doc=self.doc('def f(δ):\r\n    return δ\r\n'.encode())
        self.make(doc,BinaryComposition(ref('δ'),'<',lit('-2.5'),'result',True))
        self.assertIn(b'\r\n    result = ',self.p.read_bytes())
        self.assertNotIn(b'\n    return result\n',self.p.read_bytes().replace(b'\r\n',b''))

    def test_no_repeated_expression_or_call(self):
        doc=self.doc('def f(x):\n    tmp = expensive(x)\n    return tmp\n')
        self.assertFalse(eligible_composition_targets(doc))
        self.assertNotIn('python.compose-binary-local.v1',{a.id for a in available_actions(doc)})

    def test_reject_branch_loop_try_and_rebinding(self):
        cases=('def f(x):\n    if x: x=2\n    return x\n',
               'def f(x):\n    for i in range(x):\n        pass\n    return x\n',
               'def f(x):\n    a = 3\n    a = 4\n    return a\n',
               'def f(x):\n    try:\n        pass\n    finally:\n        pass\n    return x\n',
               'async def f(x):\n    return x\n',
               '@decorator\ndef f(x):\n    return x\n')
        for source in cases:
            with self.subTest(source=source):
                self.assertEqual(eligible_composition_targets(self.doc(source)),())

    def test_no_connection_to_unavailable_or_future_local(self):
        doc=self.doc('def f(x):\n    result = x + 1\n    return result\n')
        scope,_,anchor=self.qualified(doc)
        for operand in ('missing','later'):
            with self.assertRaises(SourceError):
                propose_compose_binary_local(doc,scope,BinaryComposition(ref(operand),'+',lit('1'),'new_value'),anchor)

    def test_reject_discarding_effectful_return(self):
        doc=self.doc('def f(x):\n    return side_effect(x)\n')
        scope,_,anchor=self.qualified(doc)
        with self.assertRaises(SourceError):
            propose_compose_binary_local(doc,scope,BinaryComposition(ref('x'),'+',lit('1'),'result',True),anchor)
        p=propose_compose_binary_local(doc,scope,BinaryComposition(ref('x'),'+',lit('1'),'result',False),anchor)
        self.assertIn(b'return side_effect(x)',p.candidate)
        self.assertEqual(doc.raw,self.p.read_bytes())

    def test_reject_invalid_new_local(self):
        doc=self.doc();scope,_,anchor=self.qualified(doc)
        for name in ('x','for','__mystery','invalid name',''):
            with self.subTest(name=name),self.assertRaises(SourceError):
                propose_compose_binary_local(doc,scope,BinaryComposition(ref('x'),'+',lit('2'),name),anchor)

    def test_reject_eval_and_unsafe_literal_expression(self):
        doc=self.doc();scope,_,anchor=self.qualified(doc)
        for text in ('hello()','2 + 2','[2, 3]','__import__("os")','1e999'):
            with self.subTest(text=text),self.assertRaises(SourceError):
                propose_compose_binary_local(doc,scope,BinaryComposition(ref('x'),'+',lit(text),'value'),anchor)

    def test_reject_unsupported_operator(self):
        doc=self.doc();scope,_,anchor=self.qualified(doc)
        with self.assertRaises(SourceError):
            propose_compose_binary_local(doc,scope,BinaryComposition(ref('x'),'/',lit('2'),'value'),anchor)

    def test_stale_anchor_and_external_changes(self):
        doc=self.doc();scope,_,anchor=self.qualified(doc)
        with self.assertRaises(SourceError):
            propose_compose_binary_local(doc,scope,BinaryComposition(ref('x'),'+',lit('2'),'value'),dict(line=99,col=2))
        proposal=propose_compose_binary_local(doc,scope,BinaryComposition(ref('x'),'+',lit('2'),'value'),anchor)
        self.p.write_text('def f(x):\n    return x + 100\n')
        with self.assertRaises(SourceError):apply_proposal(proposal)

    def test_catalog_and_pin_context_use_same_definition(self):
        doc=self.doc();scope,names,anchor=self.qualified(doc)
        actions=available_actions(doc)
        self.assertEqual([a.id for a in search_actions(actions,'compose')],['python.compose-binary-local.v1'])
        node=f'py:{scope}|param|x';out=node+':outputs:value'
        pin_actions=available_actions(doc,pin=(node,out))
        matching=[a for a in pin_actions if a.id=='python.compose-binary-local.v1']
        self.assertEqual(len(matching),1)
        self.assertEqual((matching[0].source_scope,matching[0].parameter,matching[0].anchor),(scope,'x',anchor))
        self.assertNotIn('python.compose-binary-local.v1',
                         {a.id for a in available_actions(doc,pin=('wrong',out))})

    def test_local_assignment_pin_offers_composer_without_duplicate_evaluation(self):
        doc=self.doc('def f(x):\n    stage = x + 2\n    return stage\n')
        scope,_,anchor=self.qualified(doc)
        graph=doc.scope_graph(scope)
        local=next(n for n in graph['nodes'] if n['source_kind']=='assignment')
        value_port=next(p['id'] for p in local['draft_ports']['outputs']
                        if p['id'].endswith(':outputs:value'))
        matches=[a for a in available_actions(doc,pin=(local['id'],value_port))
                 if a.id=='python.compose-binary-local.v1']
        self.assertEqual([(a.source_scope,a.parameter,a.anchor) for a in matches],
                         [(scope,'stage',anchor)])
        self.assertFalse(available_actions(doc,pin=(local['id'],local['id']+':outputs:out')))
        new=self.make(doc,BinaryComposition(ref('stage'),'*',lit('3'),'result',True))
        self.assertEqual(self.p.read_text().count('stage = x + 2'),1)
        self.assertIn('result = stage * 3\n    return result',self.p.read_text())

    def test_pin_of_call_assignment_is_not_advertised(self):
        doc=self.doc('def f(x):\n    stage = run(x)\n    return stage\n')
        self.assertEqual(eligible_composition_targets(doc),())

    def test_neutral_recipe_has_no_python_ast_authority(self):
        self.assertEqual(BinaryComposition.__module__,'studio_native.authoring_contract')
        self.assertEqual(OperandReference.__module__,'studio_native.authoring_contract')
        for args in (('call','x'),('name','')):
            with self.assertRaises(ValueError):OperandReference(*args)
        with self.assertRaises(ValueError):BinaryComposition(ref('x'),'+',lit('1'),'output','yes')


if __name__=='__main__':unittest.main()
