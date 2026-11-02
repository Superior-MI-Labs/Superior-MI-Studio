"""Static module identity must respect real Python class-scope binding rules."""
import ast
import tempfile
import unittest
from pathlib import Path

from studio_native.python_lowering import (
    _module_function_binding_conflicts, preview_python,
    review_independent_source_functions, import_independent_source_functions)
from studio_native.program_graph import ProgramGraph, ProgramGraphError
from studio_native.source_editor import SourceDocumentSession

EXAMPLE = Path(__file__).resolve().parents[1] / 'examples/qualified-integer-program.smi-graph'


class FunctionScopeIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'authored.py'
        self.graph = ProgramGraph.open(EXAMPLE)
        self.base = preview_python(self.graph.state).source
        self.assertIsNotNone(self.base)

    def source(self, append):
        self.path.write_text(self.base.replace('_smi_value_0 = 1', '_smi_value_0 = 33')
                             + '\n' + append + '\n', encoding='utf-8')
        return SourceDocumentSession.open(self.path)

    def review(self, session, functions=('increment', 'compose')):
        return review_independent_source_functions(self.graph, session, functions,
                                                  expected_graph_revision=self.graph.revision)

    def test_class_global_all_binding_forms_refuse_atomic_review(self):
        candidates = (
            'import random as increment',
            'from collections import deque as increment',
            'def increment(): pass',
            'async def increment(): pass',
            'class increment: pass',
            'try:\n    1 / 0\nexcept Exception as increment:\n    pass',
            'match 1:\n        case increment:\n            pass',
            'def helper(v=(increment := 4)): pass',
        )
        for item in candidates:
            with self.subTest(binding=item):
                session = self.source('class Owner:\n    global increment\n    ' + item.replace('\n', '\n    '))
                state = self.graph.state
                with self.assertRaisesRegex(ProgramGraphError,
                                             'module-scope binding shadows selected'):
                    self.review(session)
                self.assertEqual(state, self.graph.state)

    def test_nested_class_explicit_global_writes_are_not_missed(self):
        session = self.source('''class Outer:
    class Middle:
        class Inner:
            global increment
            from collections import deque as increment''')
        with self.assertRaisesRegex(ProgramGraphError, 'module-scope binding shadows'):
            self.review(session)

    def test_nested_class_local_shadow_is_not_false_module_conflict(self):
        session = self.source('''class Outer:
    class increment:
        pass
    class Inner:
        def increment(self): pass
        other = [k for increment in [1] for k in [2]]''')
        review = self.review(session)
        self.assertEqual([change.node_id for change in review.changes], ['one'])
        self.assertTrue(import_independent_source_functions(
            self.graph, session, ('increment', 'compose'),
            expected_graph_revision=review.graph_revision,
            expected_source_revision=review.source_revision,
            expected_source_sha256=review.source_sha256))
        self.assertEqual(session.text, self.path.read_text(encoding='utf-8'))

    def test_class_global_does_not_extend_into_comprehension_target(self):
        # The comprehension's iteration binding belongs to its own scope.
        session = self.source('''class Owner:
    global increment
    temporary = [value for increment in (1, 2) for value in (3,)]''')
        self.assertEqual([c.node_id for c in self.review(session).changes], ['one'])

    def test_duplicate_source_names_keep_exact_identity_refusal(self):
        session = self.source('''def increment(value): return value
async def increment(value): return value''')
        with self.assertRaisesRegex(ProgramGraphError, 'duplicate source definitions'):
            self.review(session)

    def test_module_index_preserves_distinct_missing_name_diagnostics(self):
        session = self.source('def increments(value): return value')
        # The original increment still exists, so make the missing source owner
        # explicit without changing the saved ProgramGraph document.
        session.update(session.text.replace('def compose(', 'def composed('))
        with self.assertRaisesRegex(ProgramGraphError,
                                    "Function 'compose'.*top-level functions"):
            self.review(session)

    def test_nested_class_definition_expressions_follow_enclosing_scope(self):
        session = self.source('''class Outer:
    class Inner((increment := object)):
        pass''')
        self.assertEqual([c.node_id for c in self.review(session).changes], ['one'])
        session = self.source('''class Outer:
    global increment
    class Inner((increment := object)):
        pass''')
        with self.assertRaisesRegex(ProgramGraphError, 'module-scope binding shadows'):
            self.review(session)

    def test_class_method_signature_evaluation_respects_global(self):
        session = self.source('''class Outer:
    global increment
    def unrelated(value=(increment := 1)):
        return value''')
        with self.assertRaisesRegex(ProgramGraphError, 'module-scope binding shadows'):
            self.review(session)

    def test_class_import_without_global_is_not_module_conflict(self):
        session = self.source('class Owner:\n    import random as increment')
        self.assertEqual([c.node_id for c in self.review(session).changes], ['one'])


if __name__ == '__main__':
    unittest.main()
