"""Characterize ephemeral independent-source proof stages, not a new importer."""
import ast
import unittest

from studio_native.program_graph import ProgramGraphError
from studio_native.python_lowering import (
    _independent_proof_function, _independent_keyword_calls,
    _independent_local_correspondence,
)


def function(text):
    return ast.parse(text).body[0]


def syntax(node):
    return ast.dump(node, include_attributes=False)


class IndependentCandidateBoundaries(unittest.TestCase):
    def test_candidate_is_transient_and_source_only_syntax_does_not_escape(self):
        original = function('''def work(value):
    """original author documentation"""
    local: int = value + 3
    local: int
    if True:
        pass
    return local
''')
        reference = function('''def work(value):
    _smi_value_0 = value + 3
    return _smi_value_0
''')
        before = syntax(original)
        candidate = _independent_proof_function(
            original, reference, {}, {'work': [original]}, 'work')
        self.assertEqual(syntax(original), before)
        self.assertIn('_smi_value_0 = value + 3', ast.unparse(candidate))
        self.assertNotIn('original author documentation', ast.unparse(candidate))
        self.assertNotIn('if True:', ast.unparse(candidate))
        self.assertNotIn('local: int', ast.unparse(candidate))

    def test_keyword_calls_only_canonicalize_exact_local_arguments(self):
        original = function('''def caller(a, b):
    return difference(b=b, a=a)
''')
        before = syntax(original)
        normalized = _independent_keyword_calls(original, {'difference': ('a', 'b')})
        self.assertEqual(ast.unparse(normalized).splitlines()[-1],
                         '    return difference(a, b)')
        self.assertNotEqual(syntax(normalized), before)
        for text in ('difference(b=effect(), a=a)',
                     'difference(b=b, a=a, unexpected=b)',
                     'unknown(b=b, a=a)',
                     'difference(a=a, b=b, **more)'):
            with self.subTest(text=text):
                function_node = function('def caller(a, b):\n    return '+text+'\n')
                original_syntax = syntax(function_node)
                self.assertEqual(syntax(_independent_keyword_calls(
                    function_node, {'difference': ('a', 'b')})), original_syntax)

    def test_local_alias_must_not_be_inferred_from_ambiguous_witnesses(self):
        reference = function('''def work(x):
    _smi_value_0 = x + 1
    _smi_value_1 = x + 1
    return _smi_value_0
''')
        authored = function('''def work(x):
    first = x + 1
    second = x + 1
    return first
''')
        before = syntax(authored)
        normalized = _independent_local_correspondence(
            authored, reference, {'x'}, {'work': [authored]})
        self.assertEqual(syntax(normalized), before)

    def test_renamed_local_must_not_be_inferred_across_nested_scope(self):
        reference = function('''def work(x):
    _smi_value_0 = x + 1
    return _smi_value_0
''')
        authored = function('''def work(x):
    renamed = x + 1
    def nested():
        return renamed
    return renamed
''')
        before = syntax(authored)
        normalized = _independent_local_correspondence(
            authored, reference, {'x'}, {'work': [authored]})
        self.assertEqual(syntax(normalized), before)

    def test_candidate_ast_bound_refuses_without_touching_author_source(self):
        body = ''.join('    pass\n' for _ in range(4400))
        original = function('def work():\n'+body+'    return 1\n')
        reference = function('def work():\n    return 1\n')
        before = syntax(original)
        with self.assertRaisesRegex(ProgramGraphError, '4096 nodes'):
            _independent_proof_function(original, reference, {}, {'work': [original]}, 'work')
        self.assertEqual(syntax(original), before)


if __name__ == '__main__':
    unittest.main()
