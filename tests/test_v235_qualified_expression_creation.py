"""Actual Python AST -> qualified visual creation -> AST and graph invariance."""
import ast
import tempfile
import unittest
from pathlib import Path

from studio_native.python_graph import PythonDocument, SourceError
from studio_native.python_authoring import (
    definitions, eligible_targets, eligible_pass_targets,
    propose_arithmetic_return_from_pass, propose_comparison_branch_return,
    propose_branch_early_return, compatible_parameter_return_pin)
from studio_native.authoring_actions import available_actions, search_actions
from studio_native.python_edit import apply_proposal
from studio_native.semantic_contract import describe_graph


class QualifiedExpressions(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path=Path(self.folder.name)/'source.py'

    def document(self, text):
        self.path.write_bytes(text if isinstance(text,bytes) else text.encode('utf-8'))
        return PythonDocument(self.path)

    @staticmethod
    def pin(scope,name='number'):
        node=f'py:{scope}|param|{name}'
        return node,node+f':outputs:{name}'

    def test_catalog_is_one_adapter_registry_and_only_qualified_operations_are_listed(self):
        names={definition.id for definition in definitions()}
        self.assertEqual(len(names),len(definitions()))
        doc=self.document('def f(number):\n    pass\n')
        actions=available_actions(doc)
        self.assertTrue({
            'python.return-from-pass.v1','python.return-parameter-from-pass.v1',
            'python.arithmetic-return-from-pass.v1','python.create-function.v1',
            'python.add-optional-keyword-parameter.v1'}.issubset({a.id for a in actions}))
        self.assertEqual([a.id for a in search_actions(actions,'arithmetic')],
                         ['python.arithmetic-return-from-pass.v1'])
        self.assertTrue({a.id for a in actions}.issubset(names))

    def test_exact_parameter_pin_filters_by_source_anchor_type(self):
        doc=self.document('def f(number):\n    pass\n\ndef g(number):\n    return number\n')
        first_scope,_=eligible_pass_targets(doc)[0]
        next_scope,_,anchors=eligible_targets(doc)[0]
        pass_actions=available_actions(doc,pin=self.pin(first_scope))
        self.assertEqual({a.id for a in pass_actions}, {
            'python.return-parameter-from-pass.v1','python.arithmetic-return-from-pass.v1',
            'python.call-return-from-pass.v1',
            'python.conditional-return-from-pass.v1',
            'python.for-range-accumulate.v1',
            'python.while-countdown.v1'})
        self.assertTrue(all(a.source_scope==first_scope for a in pass_actions))
        compare_actions=available_actions(doc,pin=self.pin(next_scope))
        self.assertEqual({a.id for a in compare_actions}, {'python.comparison-branch-return.v1',
                                                           'python.call-before-return.v1'})
        self.assertEqual(compare_actions[0].anchor,anchors[0])
        self.assertEqual(compatible_parameter_return_pin(doc,*self.pin(next_scope)),
                         ((next_scope,'number',anchors[0]),))
        self.assertEqual(available_actions(doc,pin=('fake',self.pin(next_scope)[1])),())
        self.assertEqual(available_actions(doc,pin=(self.pin(next_scope)[0],'execution-output')),())

    def test_arithmetic_reparses_as_real_three_part_data_graph(self):
        doc=self.document('def f(number):\n    pass\n')
        scope,anchor=eligible_pass_targets(doc)[0]
        proposal=propose_arithmetic_return_from_pass(doc,scope,'number','+','12',anchor)
        self.assertEqual(self.path.read_bytes(),proposal.original)
        self.assertEqual(proposal.candidate,b'def f(number):\n    return number + 12\n')
        apply_proposal(proposal)
        actual=PythonDocument(self.path)
        graph=actual.scope_graph(scope)
        contract=describe_graph(graph,origin='source')
        parameter=next(n for n in graph['nodes'] if n['source_kind']=='param')
        arithmetic=next(n for n in graph['nodes'] if n['source_kind']=='operation')
        returned=next(n for n in graph['nodes'] if n['source_kind']=='return')
        self.assertEqual(arithmetic['title'],'ADD')
        self.assertTrue(any(e['source']==parameter['id'] and e['target']==arithmetic['id'] and
                            e['relation']=='data' for e in graph['edges']))
        self.assertTrue(any(e['source']==arithmetic['id'] and e['target']==returned['id'] and
                            e['relation']=='data' for e in graph['edges']))
        self.assertEqual(len(contract.edges),len(graph['edges']))

    def test_comparison_reparses_branch_operand_and_true_false_return_paths(self):
        doc=self.document('def f(number):\n    return number\n')
        scope,_,anchors=eligible_targets(doc)[0]
        proposal=propose_comparison_branch_return(doc,scope,'number','<=','0','None',anchors[0])
        self.assertEqual(self.path.read_bytes(),doc.raw)
        apply_proposal(proposal)
        graph=PythonDocument(self.path).scope_graph(scope)
        describe_graph(graph,origin='source')
        param=next(n for n in graph['nodes'] if n['source_kind']=='param')
        comparison=next(n for n in graph['nodes'] if n['source_kind']=='compare')
        branch=next(n for n in graph['nodes'] if n['source_kind']=='branch')
        returns=[n for n in graph['nodes'] if n['source_kind']=='return']
        self.assertEqual(comparison['title'],'LTE')
        self.assertEqual(len(returns),2)
        edges=graph['edges']
        self.assertTrue(any(e['source']==param['id'] and e['target']==comparison['id'] and
                            e['relation']=='data' for e in edges))
        self.assertTrue(any(e['source']==comparison['id'] and e['target']==branch['id'] and
                            e['relation']=='data' for e in edges))
        exits={e['sourcePort'].rsplit(':',1)[-1] for e in edges
               if e['source']==branch['id'] and e['target'] in {r['id'] for r in returns}
               and e['relation']=='control'}
        self.assertEqual(exits,{'true','false'})
        self.assertIn(b'return number\n',self.path.read_bytes())

    def test_all_supported_arithmetic_operators_preserve_exact_AST(self):
        for operator,cls in (('+',ast.Add),('-',ast.Sub),('*',ast.Mult)):
            with self.subTest(operator=operator):
                doc=self.document('def f(number):\n    pass\n')
                scope,anchor=eligible_pass_targets(doc)[0]
                proposal=propose_arithmetic_return_from_pass(doc,scope,'number',operator,'2',anchor)
                body=ast.parse(proposal.candidate).body[0].body[0]
                self.assertIsInstance(body.value.op,cls)
                self.assertEqual(body.value.right.value,2)
                self.assertEqual(self.path.read_bytes(),doc.raw)

    def test_all_supported_comparisons_keep_unchanged_old_return(self):
        for op,cls in (('==',ast.Eq),('!=',ast.NotEq),('<',ast.Lt),('<=',ast.LtE),('>',ast.Gt),('>=',ast.GtE)):
            with self.subTest(op=op):
                doc=self.document('def f(number):\n    return number\n')
                scope,_,anchors=eligible_targets(doc)[0]
                proposal=propose_comparison_branch_return(doc,scope,'number',op,'3','0',anchors[0])
                fn=ast.parse(proposal.candidate).body[0]
                self.assertIsInstance(fn.body[0].test.ops[0],cls)
                self.assertIsInstance(fn.body[1],ast.Return)
                self.assertEqual(ast.unparse(fn.body[1]),'return number')

    def test_refusal_invalid_ops_dynamic_expressions_and_foreign_parameter(self):
        doc=self.document('def f(number):\n    pass\n')
        scope,anchor=eligible_pass_targets(doc)[0]
        for op in ('/','//','**','eval',''):
            with self.subTest(arithmetic=op),self.assertRaises(SourceError):
                propose_arithmetic_return_from_pass(doc,scope,'number',op,'1',anchor)
        for value in ('True','None','"hello"','float("inf")','[2]','2+3','nan','1e400'):
            with self.subTest(numeric=value),self.assertRaises(SourceError):
                propose_arithmetic_return_from_pass(doc,scope,'number','+',value,anchor)
        with self.assertRaises(SourceError):
            propose_arithmetic_return_from_pass(doc,scope,'other','+', '1',anchor)
        with self.assertRaises(SourceError):
            propose_arithmetic_return_from_pass(doc,scope,'number','+','1',dict(anchor,line=99))
        doc=self.document('def f(number):\n    return number\n')
        scope,_,anchors=eligible_targets(doc)[0]
        for op in ('is','in','and','exec'):
            with self.subTest(comparison=op),self.assertRaises(SourceError):
                propose_comparison_branch_return(doc,scope,'number',op,'1','0',anchors[0])
        for bad in ('calculate()','number','2 + 3','x if y else z'):
            with self.subTest(value=bad),self.assertRaises(SourceError):
                propose_comparison_branch_return(doc,scope,'number','<',bad,'0',anchors[0])
        with self.assertRaises(SourceError):
            propose_comparison_branch_return(doc,scope,'other','<','0','0',anchors[0])
        with self.assertRaises(SourceError):
            propose_comparison_branch_return(doc,scope,'number','<','0','0',dict(anchors[0],line=900))

    def test_source_refusal_inline_comment_or_multi_statement(self):
        for source in ('def f(number): return number\n',
                       'def f(number):\n    return number  # keep\n',
                       'def f(number):\n    return number; x = 3\n'):
            with self.subTest(source=source):
                doc=self.document(source)
                for scope,params,anchors in eligible_targets(doc):
                    with self.assertRaises(SourceError):
                        propose_comparison_branch_return(doc,scope,'number','==','0','0',anchors[0])
                self.assertEqual(self.path.read_bytes(),doc.raw)
        doc=self.document('def f(number):\n    pass  # keep\n')
        self.assertEqual(eligible_pass_targets(doc),())

    def test_crlf_unicode_and_nested_function_keep_surrounding_source_bytes(self):
        doc=self.document('def outer(é):\r\n    def inner(π):\r\n        pass\r\n    return é\r\n')
        scope,anchor=next(x for x in eligible_pass_targets(doc) if 'inner' in x[0])
        proposal=propose_arithmetic_return_from_pass(doc,scope,'π','*','3',anchor)
        self.assertIn('        return π * 3\r\n'.encode(),proposal.candidate)
        self.assertIn('    return é\r\n'.encode(),proposal.candidate)
        apply_proposal(proposal)
        fresh=PythonDocument(self.path)
        self.assertTrue(any(n['source_kind']=='operation' for n in fresh.scope_graph(scope)['nodes']))

    def test_source_external_modification_blocks_apply(self):
        doc=self.document('def f(number):\n    return number\n')
        scope,_,anchors=eligible_targets(doc)[0]
        proposal=propose_comparison_branch_return(doc,scope,'number','>=','1','None',anchors[0])
        self.path.write_bytes(doc.raw+b'\n# edited by other program\n')
        with self.assertRaisesRegex(SourceError,'changed externally'):
            apply_proposal(proposal)

    def test_old_branch_builder_uses_the_same_standalone_validation(self):
        doc=self.document('def f(number):\n    return number\n')
        scope,_,anchors=eligible_targets(doc)[0]
        proposal=propose_branch_early_return(doc,scope,'number','None',anchors[0])
        self.assertIn(b'if number is None:',proposal.candidate)
        self.assertIn(b'    return number\n',proposal.candidate)
        self.assertEqual(self.path.read_bytes(),doc.raw)


if __name__=='__main__':unittest.main()
