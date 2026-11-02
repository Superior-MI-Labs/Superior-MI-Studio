"""Definition-time bindings and bounded independent-region diagnostics."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio_native import python_lowering
from studio_native.program_graph import ProgramGraph, ProgramGraphError
from studio_native.python_lowering import preview_python, review_independent_source_functions
from studio_native.source_editor import SourceDocumentSession

EXAMPLE = Path(__file__).resolve().parents[1] / 'examples/qualified-integer-program.smi-graph'


class DefinitionTimeBindingGuards(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / 'independent.py'
        self.graph = ProgramGraph.open(EXAMPLE)
        self.base = preview_python(self.graph.state).source
        self.assertIsNotNone(self.base)

    def source(self, suffix, *, mutate=True):
        text = self.base.replace('_smi_value_0 = 1', '_smi_value_0 = 12') if mutate else self.base
        self.path.write_text(text + '\n' + suffix + '\n', encoding='utf-8')
        return SourceDocumentSession.open(self.path)

    def review(self, session, names=('increment',)):
        return review_independent_source_functions(self.graph, session, names,
            expected_graph_revision=self.graph.revision)

    def test_definition_time_rebinding_refused_without_execution(self):
        cases = (
            'def helper(value=(increment := 9)): return value',
            'def helper(*, value=(increment := 9)): return value',
            'def helper(value: (increment := int)): return value',
            'def helper() -> (increment := int): return 1',
            '@(increment := lambda fn: fn)\ndef helper(): pass',
            'async def helper(value=(increment := 9)): return value',
            'class Helper((increment := object)): pass',
            'class Helper(metaclass=(increment := type)): pass',
            'other = lambda value=(increment := 8): value',
            'class Box:\n    global increment\n    increment = 9',
            'class Box:\n    global increment\n    if 1: del increment',
            'def helper(value=(lambda v=(increment := 9): v)()): return value',
        )
        for suffix in cases:
            with self.subTest(suffix=suffix):
                session = self.source(suffix)
                before = self.graph.state
                with self.assertRaisesRegex(ProgramGraphError,
                        'module-scope binding shadows selected'):
                    self.review(session)
                self.assertEqual(self.graph.state, before)
                self.assertEqual(session.text, self.path.read_text(encoding='utf-8'))

    def test_nested_local_and_deferred_lambda_body_are_not_module_bindings(self):
        session = self.source('''
def helper():
    increment = 33
    return increment

class Box:
    increment = 7
    global_unrelated = 8

callback = lambda: (increment := 4)
''')
        review = self.review(session)
        self.assertEqual([(change.function, change.node_id)
                          for change in review.changes], [('increment', 'one')])

    def test_bad_batch_skips_recompiling_unchanged_functions_for_diagnostics(self):
        session = self.source('', mutate=False)
        session.update(session.text.replace('_smi_value_0 = 1',
                                            '_smi_value_0 = unknown_external_value'))
        with patch.object(python_lowering, '_qualified_source_edit_plan',
                          wraps=python_lowering._qualified_source_edit_plan) as qualify:
            with self.assertRaisesRegex(ProgramGraphError,
                    "Function 'increment' \\(source lines"):
                self.review(session, ('compose', 'increment'))
        self.assertEqual(qualify.call_count, 2,
                         'one full batch proof and one changed-region diagnostic')

    def test_successful_multi_function_contract_unchanged(self):
        session = self.source('def extra(): return 1')
        review = self.review(session, ('compose', 'increment'))
        self.assertEqual([change.node_id for change in review.changes], ['one'])
        self.assertEqual(session.text, self.path.read_text(encoding='utf-8'))
        self.assertFalse(self.graph.dirty)


if __name__ == '__main__':
    unittest.main()
