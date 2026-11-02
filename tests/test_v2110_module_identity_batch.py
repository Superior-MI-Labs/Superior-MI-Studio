"""One authoritative source-AST identity guard for multi-function reconciliation."""
import ast
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio_native import python_lowering
from studio_native.program_graph import ProgramGraph, ProgramGraphError
from studio_native.python_lowering import (preview_python,
    review_independent_source_functions, import_independent_source_functions)
from studio_native.source_editor import SourceDocumentSession

EXAMPLE = Path(__file__).resolve().parents[1] / 'examples/qualified-integer-program.smi-graph'


class ModuleIdentityBatchTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / 'independent.py'
        self.graph = ProgramGraph.open(EXAMPLE)
        self.base = preview_python(self.graph.state).source
        self.assertIsNotNone(self.base)

    def source(self, body):
        self.path.write_text(body, encoding='utf-8')
        return SourceDocumentSession.open(self.path)

    def review(self, session, selected=('increment', 'compose')):
        return review_independent_source_functions(self.graph, session, selected,
            expected_graph_revision=self.graph.revision)

    def test_one_module_identity_scan_for_multiple_functions(self):
        session = self.source(self.base.replace('_smi_value_0 = 1', '_smi_value_0 = 19'))
        original = python_lowering._module_function_binding_conflicts
        with patch.object(python_lowering, '_module_function_binding_conflicts', wraps=original) as spy:
            review = self.review(session)
        self.assertEqual(spy.call_count, 1)
        self.assertEqual([change.node_id for change in review.changes], ['one'])
        self.assertEqual(set(spy.call_args.args[1]), {'increment', 'compose'})
        before = self.graph.state
        self.assertTrue(import_independent_source_functions(self.graph, session, ('increment', 'compose'),
            expected_graph_revision=review.graph_revision,
            expected_source_revision=review.source_revision,
            expected_source_sha256=review.source_sha256))
        self.assertNotEqual(self.graph.state, before)
        self.assertEqual(session.text, self.path.read_text(encoding='utf-8'))
        self.graph.undo(self.graph.revision)
        self.assertEqual({k:v for k,v in self.graph.state.items() if k!='revision'},
                         {k:v for k,v in before.items() if k!='revision'})

    def test_concurrent_shadows_are_attributed_to_each_selected_function(self):
        module = ast.parse('''
@((compose := 42), (increment := 43))[0]
def other(): pass
from elsewhere import increment as compose
class C:
    global increment
    increment = 8
''')
        selected = {'increment': ast.parse('def increment(): pass').body[0],
                    'compose': ast.parse('def compose(): pass').body[0]}
        found = python_lowering._module_function_binding_conflicts(module, selected)
        self.assertEqual(found['compose'], (2, 4))
        self.assertEqual(found['increment'], (2, 7))

    def test_bare_module_annotation_does_not_bind_value(self):
        # CPython does not put `increment` into globals for a declaration-only
        # annotation. A real initializer *does* bind it, and must be refused.
        session = self.source(self.base.replace('_smi_value_0 = 1', '_smi_value_0 = 24')
                              + '\nincrement: int\ncompose: int\n')
        receipt = self.review(session)
        self.assertEqual([change.node_id for change in receipt.changes], ['one'])
        session.update(session.text + '\nincrement: int = 17\n')
        before = self.graph.state
        with self.assertRaisesRegex(ProgramGraphError, 'module-scope binding shadows'):
            self.review(session)
        self.assertEqual({k:v for k,v in self.graph.state.items() if k!='revision'},
                         {k:v for k,v in before.items() if k!='revision'})

    def test_annotation_expression_is_still_checked(self):
        module = ast.parse('''
def increment(): return 1
other: (increment := int)
''')
        owner = module.body[0]
        self.assertEqual(python_lowering._module_function_binding_conflicts(
            module, {'increment': owner})['increment'], (3,))

    def test_local_and_class_bindings_do_not_shadow_both_functions(self):
        session = self.source(self.base.replace('_smi_value_0 = 1', '_smi_value_0 = 16') + '''
class Separate:
    increment = 4
    compose = 5

def helper():
    increment = 6
    compose = 7
    return increment + compose
''')
        self.assertEqual([change.node_id for change in self.review(session).changes], ['one'])

    def test_wildcard_import_fails_closed_for_both_selected_functions(self):
        session = self.source(self.base.replace('_smi_value_0 = 1', '_smi_value_0 = 16')
                              + '\nfrom unsafe_unknown import *\n')
        with self.assertRaisesRegex(ProgramGraphError, "Function 'increment'.*module-scope binding"):
            self.review(session)

    def test_single_function_uses_same_shared_guard(self):
        session = self.source(self.base.replace('_smi_value_0 = 1', '_smi_value_0 = 16')
                              + '\ncompose = None\n')
        # A rebinding of a non-selected function must not prevent a separately
        # selected and independent function's review. The compiler still checks
        # only its own modelled source changes.
        receipt = self.review(session, ('increment',))
        self.assertEqual([change.node_id for change in receipt.changes], ['one'])
        with self.assertRaisesRegex(ProgramGraphError, 'module-scope binding shadows'):
            self.review(session, ('compose',))


if __name__ == '__main__':
    unittest.main()
