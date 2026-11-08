"""Independent batch diagnostics use normalized proof, never source-only trivia."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio_native import python_lowering
from studio_native.program_graph import ProgramGraph, ProgramGraphError
from studio_native.python_lowering import preview_python, review_independent_source_functions
from studio_native.source_editor import SourceDocumentSession


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / 'examples/qualified-integer-program.smi-graph'


class IndependentDiagnosticEfficiency(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'authored.py'
        self.graph = ProgramGraph.open(EXAMPLE)
        self.base = preview_python(self.graph.state).source
        self.assertIsNotNone(self.base)

    def source(self, text):
        self.path.write_text(text, encoding='utf-8')
        return SourceDocumentSession.open(self.path)

    def rejected(self, original, *, expected_calls, message="Function 'increment' \\(source lines"):
        session = self.source(original)
        before = self.graph.state
        source_revision = session.revision
        with patch.object(python_lowering, '_qualified_source_edit_plan',
                          wraps=python_lowering._qualified_source_edit_plan) as qualify:
            with self.assertRaisesRegex(ProgramGraphError, message) as failure:
                review_independent_source_functions(self.graph, session,
                    ('compose', 'increment'), expected_graph_revision=self.graph.revision)
        self.assertEqual(qualify.call_count, expected_calls)
        self.assertEqual(self.graph.state, before)
        self.assertEqual(session.text, original)
        self.assertEqual(session.revision, source_revision)
        return str(failure.exception)

    def test_source_only_docstring_and_pass_are_not_retried(self):
        authored = self.base.replace('def compose(y):\n',
            'def compose(y):\n    """source-owned documentation"""\n    pass\n', 1)
        authored = authored.replace('_smi_value_0 = 1',
                                    '_smi_value_0 = unknown_external', 1)
        error = self.rejected(authored, expected_calls=2)
        self.assertIn('Constant vs Name', error)

    def test_normalized_keywords_and_bare_annotations_do_not_trigger_retry(self):
        authored = self.base.replace('_smi_value_1 = increment(_smi_value_0)',
                                     '_smi_value_1: int\n    _smi_value_1 = increment(x=_smi_value_0)', 1)
        authored = authored.replace('_smi_value_0 = 1',
                                    '_smi_value_0 = unknown_external', 1)
        self.rejected(authored, expected_calls=2)

    def test_changed_valid_region_is_proved_before_bad_region(self):
        authored = self.base.replace('_smi_value_2 = _smi_value_1 * _smi_value_1',
                                     '_smi_value_2 = _smi_value_1 + _smi_value_1', 1)
        authored = authored.replace('_smi_value_0 = 1',
                                    '_smi_value_0 = unknown_external', 1)
        self.rejected(authored, expected_calls=3)


if __name__ == '__main__':
    unittest.main()
