"""Consolidated admission is read-only, indexed once and still compiler-authorized."""
import ast
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio_native import python_lowering as adapter
from studio_native.program_graph import ProgramGraph, ProgramGraphError
from studio_native.source_editor import SourceDocumentSession


EXAMPLE = Path(__file__).resolve().parents[1] / 'examples/qualified-integer-program.smi-graph'


class SourceAdmissionContract(unittest.TestCase):
    def fixture(self, source=None, canonical=None, selected=('compose',)):
        canonical = ast.parse(canonical or (
            'def compose(y):\n    return increment(x=y)\n'
            'def increment(x):\n    return x + 1\n'))
        source = ast.parse(source or (
            'def compose(y):\n    return increment(x=y)\n'
            'def increment(x):\n    return x + 1\n'))
        found = adapter._top_level_function_index(source, include_async=True)
        owned = adapter._top_level_function_index(canonical, include_async=False)
        return source, found, owned, {name: found[name][0] for name in selected}

    def test_top_level_index_is_explicit_and_keeps_duplicate_and_async_definitions(self):
        module = ast.parse('def f(): pass\nasync def f(): pass\n'
                           'class Other:\n    def f(self): pass\n')
        source = adapter._top_level_function_index(module, include_async=True)
        generated = adapter._top_level_function_index(module, include_async=False)
        self.assertEqual(len(source['f']), 2)
        self.assertEqual(len(generated['f']), 1)
        self.assertNotIn('Other', source)
        self.assertEqual(list(source), ['f'])

    def test_exact_unselected_graph_callee_accepted_with_one_identity_scan(self):
        module, found, owned, selected = self.fixture()
        original = ast.dump(module, include_attributes=True)
        shadow = adapter._module_function_binding_conflicts
        with patch.object(adapter, '_module_function_binding_conflicts', wraps=shadow) as spy:
            names = adapter._independent_keyword_parameter_contract(
                module, selected, found, owned)
        self.assertEqual(names, {'increment': ('x',)})
        self.assertEqual(spy.call_count, 1)
        self.assertEqual(set(spy.call_args.args[1]), {'compose', 'increment'})
        self.assertEqual(ast.dump(module, include_attributes=True), original)

    def test_selected_module_shadow_refused_without_changing_ast(self):
        module, found, owned, selected = self.fixture(source=(
            'def compose(y):\n    return increment(x=y)\n'
            'def increment(x):\n    return x + 1\ncompose = 100\n'))
        initial = ast.dump(module, include_attributes=True)
        with self.assertRaisesRegex(ProgramGraphError,
                                    "Function 'compose'.*module-scope binding shadows"):
            adapter._independent_keyword_parameter_contract(module, selected, found, owned)
        self.assertEqual(ast.dump(module, include_attributes=True), initial)

    def test_shadowed_unselected_callee_is_not_a_keyword_proof_target(self):
        module, found, owned, selected = self.fixture(source=(
            'def compose(y):\n    return increment(x=y)\n'
            'def increment(x):\n    return x + 1\nincrement = 100\n'))
        self.assertEqual(adapter._independent_keyword_parameter_contract(
            module, selected, found, owned), {})

    def test_changed_and_duplicate_unselected_callees_have_no_qualification(self):
        for tail in ('def increment(x):\n    return x + 2\n',
                     'def increment(x):\n    return x + 1\n'
                     'def increment(x):\n    return x + 2\n'):
            with self.subTest(tail=tail):
                module, found, owned, selected = self.fixture(source=(
                    'def compose(y):\n    return increment(x=y)\n' + tail))
                self.assertEqual(adapter._independent_keyword_parameter_contract(
                    module, selected, found, owned), {})

    def test_existing_review_full_compiler_and_source_ownership_unchanged(self):
        graph = ProgramGraph.open(EXAMPLE)
        original_graph = graph.state
        text = adapter.preview_python(graph.state).source
        self.assertIsNotNone(text)
        text = text.replace('increment(_smi_value_0)', 'increment(x=_smi_value_0)', 1)
        text = text.replace('_smi_value_0 = 1', '_smi_value_0 = 23', 1)
        with tempfile.TemporaryDirectory() as dirname:
            path = Path(dirname) / 'developer.py'
            path.write_text(text, encoding='utf-8')
            session = SourceDocumentSession.open(path)
            revision = session.revision
            review = adapter.review_independent_source_functions(graph, session,
                ('compose', 'increment'), expected_graph_revision=graph.revision)
            self.assertEqual([change.node_id for change in review.changes], ['one'])
            self.assertEqual(graph.state, original_graph)
            self.assertEqual(session.revision, revision)
            self.assertEqual(session.text, text)
            self.assertTrue(adapter.import_independent_source_functions(graph, session,
                ('compose', 'increment'), expected_graph_revision=review.graph_revision,
                expected_source_revision=review.source_revision,
                expected_source_sha256=review.source_sha256))
            self.assertEqual(session.text, text)
            self.assertEqual(path.read_text(encoding='utf-8'), text)
            self.assertNotEqual(graph.state, original_graph)


if __name__ == '__main__':
    unittest.main()
