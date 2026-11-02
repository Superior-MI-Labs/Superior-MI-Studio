"""v2.41: AST-backed Branch/Loop assembly without language leakage or execution."""
import ast
from pathlib import Path
import tempfile
import unittest

from studio_native.python_graph import PythonDocument, SourceError
from studio_native.python_edit import apply_proposal
from studio_native.python_authoring import (
    eligible_flow_pass_targets, eligible_pass_targets, propose_create_function,
    propose_conditional_returns_from_pass, propose_for_range_accumulate,
    propose_while_countdown)
from studio_native.authoring_actions import available_actions, search_actions
from studio_native.authoring_contract import QualifiedOperation, validate_catalog
from studio_native.operation_catalog import qualified_operations
from studio_native.semantic_contract import describe_graph


class ControlFlowAuthoringTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.p=Path(self.tmp.name)/'program.py'

    def doc(self,source='def build(n):\n    pass\n'):
        self.p.write_bytes(source.encode() if isinstance(source,str) else source)
        return PythonDocument(self.p)

    def flow(self,doc):
        return eligible_flow_pass_targets(doc)[0]

    def verify(self,proposal,doc,expected,kinds,expected_control=None):
        self.assertEqual(self.p.read_bytes(),doc.raw,'preview must never write')
        self.assertEqual(ast.dump(ast.parse(proposal.candidate)),ast.dump(ast.parse(expected)))
        apply_proposal(proposal)
        new=PythonDocument(self.p)
        scope=next(key for key,s in new.scopes.items() if s.title=='build')
        graph=new.scope_graph(scope)
        found=[node['source_kind'] for node in graph['nodes']]
        for kind in kinds:self.assertIn(kind,found)
        describe_graph(new.presentation_graph(scope),origin='source')
        if expected_control is not None:
            self.assertGreaterEqual(len([e for e in graph['edges'] if e['relation']=='control']),expected_control)
        return new,graph

    def test_branch_two_return_paths_after_reparse(self):
        doc=self.doc();key,_,anchor=self.flow(doc)
        p=propose_conditional_returns_from_pass(doc,key,'n','<','0','-1','1',anchor)
        self.verify(p,doc,'def build(n):\n    if n < 0:\n        return -1\n    return 1\n',
                    ('branch','compare','return'),expected_control=2)

    def test_for_range_accumulator_and_real_loop_ports(self):
        doc=self.doc();key,_,anchor=self.flow(doc)
        p=propose_for_range_accumulate(doc,key,'n','index','total',anchor)
        _,graph=self.verify(p,doc,'def build(n):\n    total = 0\n    for index in range(n):\n        total += index\n    return total\n',
                            ('loop','assignment','return'),expected_control=2)
        self.assertTrue(any(e['targetPort'].endswith(':repeat') for e in graph['edges']))

    def test_while_countdown_preserves_argument_binding(self):
        doc=self.doc();key,_,anchor=self.flow(doc)
        p=propose_while_countdown(doc,key,'n','counter','steps',anchor)
        self.verify(p,doc,'def build(n):\n    counter = n\n    steps = 0\n    while counter > 0:\n        counter -= 1\n        steps += 1\n    return steps\n',
                    ('loop','assignment','return'),expected_control=2)

    def test_catalog_and_search_unified_with_python_adapter(self):
        doc=self.doc();ids={action.id for action in available_actions(doc)}
        self.assertTrue({'python.conditional-return-from-pass.v1',
                         'python.for-range-accumulate.v1',
                         'python.while-countdown.v1'} <= ids)
        self.assertEqual([a.id for a in search_actions(available_actions(doc),'countdown')],
                         ['python.while-countdown.v1'])
        self.assertTrue({'python.assign-source-local.v1',
                         'python.compose-binary-local.v1'} <=
                        {capability.id for capability in qualified_operations('python')})
        self.assertEqual(qualified_operations('go'),())
        self.assertEqual(validate_catalog(qualified_operations('python')),qualified_operations('python'))
        with self.assertRaises(ValueError):validate_catalog((qualified_operations('python')[0],)*2)
        self.assertEqual(QualifiedOperation.__module__,'studio_native.authoring_contract')

    def test_exact_parameter_pin_offers_flow_without_exposing_foreign_pins(self):
        doc=self.doc();scope,_,anchor=self.flow(doc)
        node=f'py:{scope}|param|n';pin=node+':outputs:n'
        actions=available_actions(doc,pin=(node,pin))
        ids={a.id for a in actions}
        self.assertTrue({'python.conditional-return-from-pass.v1',
                         'python.for-range-accumulate.v1',
                         'python.while-countdown.v1'} <= ids)
        for action in actions:
            self.assertEqual(action.source_scope,scope)
            self.assertEqual(action.parameter,'n')
            self.assertEqual(action.anchor,anchor)
        self.assertEqual(available_actions(doc,pin=('foreign',pin)),())
        self.assertEqual(available_actions(doc,pin=(node,pin+':wrong')),())

    def test_no_parameter_or_nested_async_or_decorated_function(self):
        for source in ('def build():\n    pass\n','async def build(n):\n    pass\n',
                       '@custom\ndef build(n):\n    pass\n'):
            with self.subTest(source=source):
                doc=self.doc(source)
                self.assertEqual(eligible_flow_pass_targets(doc),())

    def test_reject_stale_anchor_and_wrong_parameter(self):
        doc=self.doc();scope,_,anchor=self.flow(doc)
        with self.assertRaises(SourceError):
            propose_for_range_accumulate(doc,scope,'not_a_parameter','index','total',anchor)
        with self.assertRaises(SourceError):
            propose_while_countdown(doc,scope,'n','counter','steps',{'line':42,'col':4})
        with self.assertRaises(SourceError):
            propose_conditional_returns_from_pass(doc,scope,'n','<','0','0','1',None)

    def test_reject_unsafe_names_collisions(self):
        doc=self.doc();scope,_,anchor=self.flow(doc)
        for names in (('n','total'),('for','total'),('a','a'),('__builtins__','total')):
            with self.subTest(names=names),self.assertRaises(SourceError):
                propose_for_range_accumulate(doc,scope,'n',*names,anchor)
        with self.assertRaises(SourceError):
            propose_while_countdown(doc,scope,'n','n','steps',anchor)

    def test_reject_effectful_literals_and_operators(self):
        doc=self.doc();scope,_,anchor=self.flow(doc)
        for bad in ('call()','1 + 2','[1, 2]','float("inf")'):
            with self.subTest(bad=bad),self.assertRaises(SourceError):
                propose_conditional_returns_from_pass(doc,scope,'n','<',bad,'0','1',anchor)
        with self.assertRaises(SourceError):
            propose_conditional_returns_from_pass(doc,scope,'n','is','None','1','2',anchor)

    def test_unsigned_and_signed_numeric_literals_share_one_gate(self):
        doc=self.doc();scope,_,anchor=self.flow(doc)
        prop=propose_conditional_returns_from_pass(doc,scope,'n','<=','-2.5','-10','+3',anchor)
        self.assertIn(b'if n <= -2.5:',prop.candidate)
        self.assertIn(b'return -10',prop.candidate)
        self.assertIn(b'return 3',prop.candidate)

    def test_comments_docstring_and_crlf_preserved(self):
        source=b'# header\r\ndef build(n):\r\n    """doc"""\r\n    pass\r\n'
        doc=self.doc(source);scope,_,anchor=self.flow(doc)
        p=propose_for_range_accumulate(doc,scope,'n','index','total',anchor)
        self.assertTrue(p.candidate.startswith(b'# header\r\ndef build(n):\r\n    """doc"""\r\n'))
        self.assertNotIn(b'\n',p.candidate.replace(b'\r\n',b''))
        self.assertEqual(self.p.read_bytes(),source)
        apply_proposal(p)
        self.assertIn('doc',self.p.read_text())

    def test_reject_existing_range_shadow(self):
        doc=self.doc('range = lambda x: []\ndef build(n):\n    pass\n')
        scope,_,anchor=self.flow(doc)
        with self.assertRaises(SourceError):
            propose_for_range_accumulate(doc,scope,'n','index','total',anchor)

    def test_stale_file_transaction_refused(self):
        doc=self.doc();scope,_,anchor=self.flow(doc)
        proposal=propose_while_countdown(doc,scope,'n','counter','steps',anchor)
        self.p.write_text('def build(n):\n    pass\n# intervening editor\n')
        with self.assertRaises(ValueError):apply_proposal(proposal)

    def test_source_is_not_executed_for_flow_proposals(self):
        doc=self.doc('raise RuntimeError("should never run")\ndef build(n):\n    pass\n')
        scope,_,anchor=self.flow(doc)
        p=propose_for_range_accumulate(doc,scope,'n','index','total',anchor)
        self.assertIn(b'raise RuntimeError',p.candidate)
        self.assertNotIn(b'total =',self.p.read_bytes())


if __name__=='__main__':unittest.main()
