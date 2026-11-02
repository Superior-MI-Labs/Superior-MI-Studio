"""Qualified source-owned invocation construction; no arbitrary graph compilation."""
import ast
import tempfile
import unittest
from pathlib import Path

from studio_native.python_authoring import (
    definitions, qualified_callees, eligible_call_pass_targets,
    eligible_call_return_targets, propose_call_return_from_pass,
    propose_call_before_return,
)
from studio_native.authoring_actions import available_actions
from studio_native.python_graph import PythonDocument, SourceError
from studio_native.python_edit import apply_proposal, rewire_source_operand
from studio_native.semantic_contract import describe_graph


class CallConstruction(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path=Path(tmp.name)/'call-builder.py'

    def doc(self,source):
        self.path.write_bytes(source if isinstance(source,bytes) else source.encode('utf-8'))
        return PythonDocument(self.path)

    @staticmethod
    def pin(scope,parameter='value'):
        ident=f'py:{scope}|param|{parameter}'
        return ident,ident+f':outputs:{parameter}'

    def test_two_actions_are_in_same_adapter_registry_and_pin_menu(self):
        doc=self.doc('def choose(x, y):\n    return x + y\n\ndef pending(value):\n    pass\n\ndef complete(value):\n    return value\n')
        ids={d.id for d in definitions()}
        self.assertEqual(len(ids),len(definitions()))
        self.assertIn('python.call-return-from-pass.v1',ids)
        self.assertIn('python.call-before-return.v1',ids)
        self.assertEqual({a.id for a in available_actions(doc)} & {
            'python.call-return-from-pass.v1','python.call-before-return.v1'},
            {'python.call-return-from-pass.v1','python.call-before-return.v1'})
        pass_scope,_,_=next(x for x in eligible_call_pass_targets(doc) if 'pending' in x[0])
        ret_scope,_,_=next(x for x in eligible_call_return_targets(doc) if 'complete' in x[0])
        self.assertIn('python.call-return-from-pass.v1',
                      {a.id for a in available_actions(doc,pin=self.pin(pass_scope))})
        self.assertIn('python.call-before-return.v1',
                      {a.id for a in available_actions(doc,pin=self.pin(ret_scope))})
        self.assertFalse(available_actions(doc,pin=('foreign','bogus')))

    def test_call_to_return_roundtrip_real_argument_and_result_data_edges(self):
        old='def combine(x, y):\n    return x + y\n\ndef dispatch(value):\n    pass\n'
        doc=self.doc(old)
        scope,anchor,options=eligible_call_pass_targets(doc)[0]
        self.assertIn(('combine',('x','y')),options)
        proposal=propose_call_return_from_pass(doc,scope,'value','combine',('3',),anchor)
        self.assertEqual(self.path.read_text(),old)
        self.assertIn('return combine(value, 3)',proposal.candidate.decode())
        backup=apply_proposal(proposal)
        self.assertEqual(backup.read_text(),old)
        new=PythonDocument(self.path)
        graph=new.scope_graph(scope)
        contract=describe_graph(graph,origin='source')
        self.assertTrue(contract.nodes)
        kinds={n['source_kind'] for n in graph['nodes']}
        self.assertTrue({'param','literal','call','return'}<=kinds)
        target=next(n for n in graph['nodes'] if n['source_kind']=='call')
        ret=next(n for n in graph['nodes'] if n['source_kind']=='return')
        src=next(n for n in graph['nodes'] if n['source_kind']=='param')
        lit=next(n for n in graph['nodes'] if n['source_kind']=='literal')
        self.assertTrue(any(e['source']==src['id'] and e['target']==target['id'] and
                            e['relation']=='data' for e in graph['edges']))
        self.assertTrue(any(e['source']==lit['id'] and e['target']==target['id'] and
                            e['relation']=='data' for e in graph['edges']))
        self.assertTrue(any(e['source']==target['id'] and e['target']==ret['id'] and
                            e['relation']=='data' for e in graph['edges']))
        self.assertEqual(len(contract.edges),len(graph['edges']))

    def test_call_statement_before_return_roundtrip_preserves_old_ast(self):
        doc=self.doc('def audit(item):\n    return item\n\ndef forward(value):\n    return value\n')
        scope,anchor,_=next(x for x in eligible_call_return_targets(doc) if 'forward' in x[0])
        old_return=ast.dump(doc.scopes[scope].ast_node.body[0],include_attributes=False)
        proposal=propose_call_before_return(doc,scope,'value','audit',(),anchor)
        self.assertIn(b'    audit(value)\n    return value\n',proposal.candidate)
        self.assertEqual(self.path.read_bytes(),doc.raw)
        apply_proposal(proposal)
        fresh=PythonDocument(self.path)
        body=fresh.scopes[scope].ast_node.body
        self.assertIsInstance(body[0],ast.Expr)
        self.assertIsInstance(body[0].value,ast.Call)
        self.assertEqual(ast.dump(body[1],include_attributes=False),old_return)
        graph=fresh.scope_graph(scope)
        describe_graph(graph,origin='source')
        self.assertEqual(sum(n['source_kind']=='call' for n in graph['nodes']),1)
        self.assertEqual(sum(n['source_kind']=='return' for n in graph['nodes']),1)
        self.assertTrue(any(e['relation']=='control' and e['target'] in {
            n['id'] for n in graph['nodes'] if n['source_kind']=='return'} for e in graph['edges']))

    def test_direct_return_call_has_one_control_and_one_data_identity(self):
        doc=self.doc('def combine(x, y):\n    return x + y\n\ndef dispatch(value):\n    return combine(value, 3)\n')
        scope=next(s for s in doc.scopes if 'dispatch' in s)
        graph=doc.scope_graph(scope)
        calls=[n for n in graph['nodes'] if n['source_kind']=='call']
        self.assertEqual(len(calls),1)
        call=calls[0]
        ret=next(n for n in graph['nodes'] if n['source_kind']=='return')
        entry=next(n for n in graph['nodes'] if n['source_kind']=='entry')
        self.assertEqual({p['type'] for p in call['draft_ports']['outputs']},
                         {'py:unknown','execution'})
        control=[e for e in graph['edges'] if e['relation']=='control']
        self.assertEqual([(e['source'],e['target']) for e in control],
                         [(entry['id'],call['id']),(call['id'],ret['id'])])
        self.assertTrue(any(e['source']==call['id'] and e['target']==ret['id'] and
                            e['relation']=='data' for e in graph['edges']))
        describe_graph(graph,origin='source')

    def test_nested_call_expression_does_not_get_invented_control_order(self):
        doc=self.doc('def choose(x):\n    return x\ndef f(value):\n    return choose(choose(value))\n')
        scope=next(s for s in doc.scopes if 'f:' in s)
        graph=doc.scope_graph(scope)
        calls=[n for n in graph['nodes'] if n['source_kind']=='call']
        self.assertEqual(len(calls),2)
        self.assertFalse(any(p['type']=='execution' for n in calls
                             for p in n['draft_ports']['inputs']+n['draft_ports']['outputs']))
        describe_graph(graph,origin='source')

    def test_unsupported_effectful_conditional_still_blocks_inferred_successor(self):
        doc=self.doc('def f(value):\n    if value:\n        print(value)\n    return value\n')
        scope=next(s for s in doc.scopes if 'f:' in s)
        graph=doc.scope_graph(scope)
        self.assertTrue(any('unresolved effects/control' in warning for warning in graph['warnings']))
        self.assertFalse(any(n['source_kind']=='control_join' for n in graph['nodes']))

    def test_arity_and_literals_are_checked_before_source_mutation(self):
        doc=self.doc('def combine(x, y):\n    return x + y\n\ndef caller(value):\n    pass\n')
        scope,anchor,_=eligible_call_pass_targets(doc)[0]
        for args in ((),('1','2'),('evil() ',),('[1]',),('1+2',),('1e400',)):
            with self.subTest(args=args),self.assertRaises(SourceError):
                propose_call_return_from_pass(doc,scope,'value','combine',args,anchor)
        for name in ('different','value.__class__','__import__'):
            with self.subTest(name=name),self.assertRaises(SourceError):
                propose_call_return_from_pass(doc,scope,'value',name,('1',),anchor)
        with self.assertRaises(SourceError):
            propose_call_return_from_pass(doc,scope,'wrong','combine',('2',),anchor)
        with self.assertRaises(SourceError):
            propose_call_return_from_pass(doc,scope,'value','combine',('2',),dict(anchor,line=500))
        self.assertEqual(self.path.read_bytes(),doc.raw)

    def test_shadowed_dynamic_or_nonpositional_callees_are_not_qualified(self):
        docs=[
            'def service(x):\n    return x\nservice = other\n',
            'def service(x):\n    return x\ndef service(y):\n    return y\n',
            '@wrapper\ndef service(x):\n    return x\n',
            'async def service(x):\n    return x\n',
            'def service(x=1):\n    return x\n',
            'def service(*x):\n    return x\n',
            'def service(x, *, y):\n    return x\n',
            'def service(x):\n    return x\nfrom helpers import service\n',
            'def service(x):\n    return x\nimport service\n',
            'def service(x):\n    return x\n',
        ]
        for source in docs:
            with self.subTest(source=source):
                doc=self.doc(source+'\ndef caller(value):\n    pass\n')
                scope=next(s for s in doc.scopes if 'caller' in s)
                if source=='def service(x):\n    return x\n':
                    self.assertEqual(qualified_callees(doc,scope),(('service',('x',)),))
                else:
                    self.assertFalse(qualified_callees(doc,scope))
        doc=self.doc('def service(x):\n    return x\ndef caller(service):\n    pass\n')
        scope=next(s for s in doc.scopes if 'caller' in s)
        self.assertEqual(qualified_callees(doc,scope),())

    def test_nested_caller_not_automatically_authorized_as_module_call(self):
        doc=self.doc('def service(x):\n    return x\ndef outer(value):\n    def inner(y):\n        pass\n    return value\n')
        nested=next(s for s in doc.scopes if 'inner' in s)
        self.assertEqual(qualified_callees(doc,nested),())
        self.assertFalse(any(s==nested for s,_,_ in eligible_call_pass_targets(doc)))

    def test_crlf_unicode_and_multi_arg_roundtrip(self):
        doc=self.doc('def 计算(左, 右, 标签):\r\n    return 左\r\n\r\ndef runner(值):\r\n    pass\r\n')
        scope,anchor,_=eligible_call_pass_targets(doc)[0]
        proposal=propose_call_return_from_pass(doc,scope,'值','计算',('4','"ok"'),anchor)
        self.assertIn('return 计算(值, 4, \'ok\')\r\n'.encode(),proposal.candidate)
        self.assertEqual(self.path.read_bytes(),doc.raw)
        apply_proposal(proposal)
        fresh=PythonDocument(self.path)
        describe_graph(fresh.scope_graph(scope),origin='source')

    def test_external_edit_refused_and_original_scope_unchanged(self):
        doc=self.doc('def run(x):\n    return x\n\ndef caller(value):\n    pass\n')
        scope,anchor,_=eligible_call_pass_targets(doc)[0]
        old_cal=ast.dump(doc.tree.body[0],include_attributes=False)
        proposal=propose_call_return_from_pass(doc,scope,'value','run',(),anchor)
        self.assertEqual(ast.dump(ast.parse(proposal.candidate).body[0],include_attributes=False),old_cal)
        self.path.write_bytes(doc.raw+b'\n# external change\n')
        with self.assertRaisesRegex(SourceError,'changed externally'):
            apply_proposal(proposal)

    def test_existing_call_argument_rewire_uses_same_source_authority(self):
        doc=self.doc('def choose(x, y):\n    return x + y\n\ndef caller(value):\n    return choose(99, 2)\n')
        scope=next(s for s in doc.scopes if 'caller' in s)
        graph=doc.scope_graph(scope)
        param=next(n for n in graph['nodes'] if n['source_kind']=='param')
        call=next(n for n in graph['nodes'] if n['source_kind']=='call')
        src=param['draft_ports']['outputs'][0]['id']
        dst=next(p['id'] for p in call['draft_ports']['inputs'] if p['id'].endswith(':arg0'))
        proposal=rewire_source_operand(doc,scope,param['id'],src,call['id'],dst)
        self.assertIn(b'choose(value, 2)',proposal.candidate)
        self.assertEqual(self.path.read_bytes(),doc.raw)
        apply_proposal(proposal)
        graph=PythonDocument(self.path).scope_graph(scope)
        param=next(n for n in graph['nodes'] if n['source_kind']=='param')
        call=next(n for n in graph['nodes'] if n['source_kind']=='call')
        self.assertTrue(any(e['source']==param['id'] and e['target']==call['id']
                            for e in graph['edges']))
