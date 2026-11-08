"""Proof helper consolidation must not broaden independent Python import."""
import ast
import copy
import unittest

from studio_native.python_lowering import (
    _function_parameter_names, _IndependentCandidateSyntax,
    _pure_expression_witness,
)


class IndependentProofConsolidation(unittest.TestCase):
    def test_parameter_contract_names_include_keyword_variants(self):
        fn=ast.parse('def f(a, /, b: int, *other, c: bool, **extras): pass').body[0]
        self.assertEqual(_function_parameter_names(fn.args),
                         {'a','b','other','c','extras'})

    def test_candidate_normalization_leaves_original_ast_untouched(self):
        source=('def f(arg: int):\n'
                '    value: int = 1 + 2\n'
                '    value: int\n'
                '    if True:\n'
                '        pass\n'
                '    else:\n'
                '        pass\n'
                '    return value\n')
        original=ast.parse(source).body[0]
        baseline=ast.dump(original,include_attributes=False)
        owned=copy.deepcopy(original)
        normalizer=_IndependentCandidateSyntax({'arg','value'})
        owned.body=normalizer.strip_noops(owned.body)
        self.assertEqual(ast.dump(original,include_attributes=False),baseline)
        self.assertEqual([type(x).__name__ for x in owned.body],
                         ['Assign','Return'])
        self.assertEqual(owned.body[0].value.value,3)

    def test_unknown_annotation_and_effectful_guard_are_not_erased(self):
        source=('def f():\n'
                '    unknown: int\n'
                '    if run():\n'
                '        pass\n'
                '    return 1\n')
        owned=copy.deepcopy(ast.parse(source).body[0])
        owned.body=_IndependentCandidateSyntax(set()).strip_noops(owned.body)
        self.assertIsInstance(owned.body[0],ast.AnnAssign)
        self.assertIsInstance(owned.body[1],ast.If)
        self.assertIsInstance(owned.body[1].test,ast.Call)
        self.assertEqual(len(owned.body[1].body),1)
        self.assertIsInstance(owned.body[1].body[0],ast.Pass)

    def test_pure_witness_proves_only_fully_resolved_expression(self):
        expression=ast.parse('local + 4',mode='eval').body
        original=ast.dump(expression,include_attributes=False)
        expected=ast.dump(ast.parse('_smi_value_3 + 4',mode='eval').body,
                          include_attributes=False)
        self.assertEqual(_pure_expression_witness(
            expression,{'local':'_smi_value_3'},set()),expected)
        self.assertEqual(ast.dump(expression,include_attributes=False),original)
        self.assertIsNone(_pure_expression_witness(expression,{}, {'local'}))
        self.assertIsNone(_pure_expression_witness(
            ast.parse('dangerous()',mode='eval').body,{},set()))


if __name__=='__main__':
    unittest.main()
