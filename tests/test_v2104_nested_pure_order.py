"""Pure source-order equivalence is scoped to one execution suite at a time.

These are proof-layer tests, not a second importer. The full import still
requires a matching graph-owned lowering and an explicit source transaction.
"""
import ast
import unittest

from studio_native.python_lowering import _equivalent_pure_assignment_order


def equivalent(first, second):
    return _equivalent_pure_assignment_order(ast.parse(first), ast.parse(second))


class NestedPureSuiteTests(unittest.TestCase):
    def test_reordered_pure_if_arm(self):
        original = '''def f(x, flag):
    if flag:
        _smi_value_2 = x + 1
        _smi_value_3 = x * 2
        return _smi_value_2
    return x
'''
        reordered = original.replace(
            '        _smi_value_2 = x + 1\n        _smi_value_3 = x * 2',
            '        _smi_value_3 = x * 2\n        _smi_value_2 = x + 1')
        self.assertTrue(equivalent(original, reordered))

    def test_reordered_else_arm_and_nested_branch(self):
        original = '''def f(x, a, b):
    if a:
        if b:
            _smi_value_2 = x + 1
            _smi_value_3 = x * 2
        else:
            _smi_value_2 = x - 1
            _smi_value_3 = x * 2
    else:
        _smi_value_2 = x + 4
        _smi_value_3 = x * 5
    return x
'''
        revised = (original.replace(
            '            _smi_value_2 = x + 1\n            _smi_value_3 = x * 2',
            '            _smi_value_3 = x * 2\n            _smi_value_2 = x + 1')
            .replace('        _smi_value_2 = x + 4\n        _smi_value_3 = x * 5',
                     '        _smi_value_3 = x * 5\n        _smi_value_2 = x + 4'))
        self.assertTrue(equivalent(original, revised))

    def test_reordered_pure_loop_body_not_loop_header(self):
        first = '''def f(values, x):
    for item in values:
        _smi_value_2 = item + x
        _smi_value_3 = item * x
    return x
'''
        second = first.replace(
            '        _smi_value_2 = item + x\n        _smi_value_3 = item * x',
            '        _smi_value_3 = item * x\n        _smi_value_2 = item + x')
        self.assertTrue(equivalent(first, second))

    def test_reordered_pure_while_body(self):
        first = '''def f(x):
    while x:
        _smi_value_2 = x + 1
        _smi_value_3 = x * 2
        x -= 1
    return x
'''
        second = first.replace(
            '        _smi_value_2 = x + 1\n        _smi_value_3 = x * 2',
            '        _smi_value_3 = x * 2\n        _smi_value_2 = x + 1')
        self.assertTrue(equivalent(first, second))

    def test_never_move_across_branches(self):
        before = '''def f(x, yes):
    if yes:
        _smi_value_2 = x + 1
    else:
        _smi_value_3 = x + 2
    return x
'''
        after = before.replace('        _smi_value_2 = x + 1',
                               '        _smi_value_3 = x + 2').replace(
                               '        _smi_value_3 = x + 2\n    return',
                               '        _smi_value_2 = x + 1\n    return')
        self.assertFalse(equivalent(before, after))

    def test_no_reordering_across_effect_or_return(self):
        before = '''def f(x, flag):
    if flag:
        _smi_value_2 = x + 1
        print(x)
        _smi_value_3 = x * 2
    return x
'''
        after = before.replace(
            '        _smi_value_2 = x + 1\n        print(x)\n        _smi_value_3 = x * 2',
            '        _smi_value_3 = x * 2\n        print(x)\n        _smi_value_2 = x + 1')
        self.assertFalse(equivalent(before, after))

    def test_no_reordered_division_or_function_call(self):
        before = '''def f(x, y, flag):
    if flag:
        _smi_value_2 = x // y
        _smi_value_3 = x + y
    return x
'''
        after = before.replace(
            '        _smi_value_2 = x // y\n        _smi_value_3 = x + y',
            '        _smi_value_3 = x + y\n        _smi_value_2 = x // y')
        self.assertFalse(equivalent(before, after))
        self.assertFalse(equivalent(before.replace('x // y', 'f(x)'),
                                    after.replace('x // y', 'f(x)')))

    def test_forward_reference_in_branch_never_accepted(self):
        before = '''def f(x, flag):
    if flag:
        _smi_value_2 = x + 1
        _smi_value_3 = _smi_value_2 * 2
    return x
'''
        after = before.replace(
            '        _smi_value_2 = x + 1\n        _smi_value_3 = _smi_value_2 * 2',
            '        _smi_value_3 = _smi_value_2 * 2\n        _smi_value_2 = x + 1')
        self.assertFalse(equivalent(before, after))

    def test_duplicate_target_inside_branch_never_accepted(self):
        before = '''def f(x, flag):
    if flag:
        _smi_value_2 = x + 1
        _smi_value_2 = x + 2
    return x
'''
        self.assertFalse(equivalent(before, before))

    def test_unchanged_nested_statement_structure_is_still_equal(self):
        first = '''def f(x, flag):
    if flag:
        return x
    return x
'''
        self.assertTrue(equivalent(first, first))

if __name__ == '__main__':
    unittest.main()
