"""Reuse authoritative source and graph witnesses within one bounded preflight."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio_native import python_lowering
from studio_native.python_lowering import (preview_python,
    review_independent_source_functions, import_independent_source_functions,
    review_generated_source_edit)
from studio_native.program_graph import ProgramGraph, ProgramGraphError
from studio_native.source_editor import SourceDocumentSession

EXAMPLE = Path(__file__).resolve().parents[1] / 'examples/qualified-integer-program.smi-graph'


class SharedPreflightTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'independent.py'
        self.graph = ProgramGraph.open(EXAMPLE)
        self.baseline = preview_python(self.graph.state).source
        self.assertIsNotNone(self.baseline)

    def source(self, text):
        self.path.write_text(text, encoding='utf-8')
        return SourceDocumentSession.open(self.path)

    def test_independent_review_reuses_existing_baseline_compilation(self):
        session = self.source(self.baseline.replace('_smi_value_0 = 1', '_smi_value_0 = 29')
                              + '\n# source-only comment\n')
        with patch.object(python_lowering, 'preview_python', wraps=preview_python) as preview:
            receipt = review_independent_source_functions(self.graph, session,
                ('increment', 'compose'), expected_graph_revision=self.graph.revision)
        # One authoritative original preview and one trial compilation. The
        # nested compiler must not re-preview the unchanged original graph.
        self.assertEqual(preview.call_count, 2)
        self.assertEqual([item.node_id for item in receipt.changes], ['one'])
        before = self.graph.state
        self.assertTrue(import_independent_source_functions(self.graph, session,
            ('increment', 'compose'), expected_graph_revision=receipt.graph_revision,
            expected_source_revision=receipt.source_revision,
            expected_source_sha256=receipt.source_sha256))
        self.assertNotEqual(self.graph.state, before)
        self.assertEqual(session.text, self.path.read_text(encoding='utf-8'))
        self.graph.undo(self.graph.revision)
        self.assertEqual({k:v for k,v in before.items() if k!='revision'},
                         {k:v for k,v in self.graph.state.items() if k!='revision'})

    def test_one_graph_state_snapshot_inside_compiler_plan(self):
        session = self.source(self.baseline.replace('_smi_value_0 = 1', '_smi_value_0 = 29'))
        original = ProgramGraph.state
        reads = []
        def tracked_state(instance):
            if instance is self.graph:
                reads.append(instance.revision)
            return original.fget(instance)
        with patch.object(ProgramGraph, 'state', property(tracked_state)):
            receipt = review_independent_source_functions(self.graph, session,
                ('increment', 'compose'), expected_graph_revision=self.graph.revision)
        # Independent ownership preview + one compiler-plan defensive copy.
        # The trial graph has its own state and is independently qualified.
        self.assertEqual(len(reads), 2)
        self.assertEqual(reads[0], reads[1])
        self.assertEqual([item.node_id for item in receipt.changes], ['one'])

    def test_generated_source_still_requires_its_own_fresh_preview(self):
        edited = self.baseline.replace('_smi_value_0 = 1', '_smi_value_0 = 34')
        with patch.object(python_lowering, 'preview_python', wraps=preview_python) as preview:
            receipt = review_generated_source_edit(self.graph, self.baseline, edited,
                                                   expected_revision=self.graph.revision)
        self.assertEqual(preview.call_count, 2)
        self.assertEqual([item.node_id for item in receipt.changes], ['one'])

    def test_bad_independent_expression_still_refuses_without_mutation(self):
        session = self.source(self.baseline.replace('_smi_value_0 = 1',
                                                    '_smi_value_0 = object()'))
        state = self.graph.state
        with self.assertRaises(ProgramGraphError):
            review_independent_source_functions(self.graph, session, ('increment',),
                                                expected_graph_revision=self.graph.revision)
        self.assertEqual(self.graph.state, state)

    def test_source_only_formatting_is_no_graph_edit(self):
        session = self.source(self.baseline + '\n# outside graph document\n')
        receipt = review_independent_source_functions(self.graph, session,
            ('increment',), expected_graph_revision=self.graph.revision)
        self.assertEqual(receipt.changes, ())

if __name__ == '__main__':
    unittest.main()
