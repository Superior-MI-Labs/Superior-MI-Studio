"""Reproduce v2.78 native failure; qualify source-owned trivia preservation."""
import ast
import tempfile
import unittest
from pathlib import Path

from studio_native.program_graph import ProgramGraph, GraphConflict, ProgramGraphError
from studio_native.python_lowering import LinkedPythonSource, preview_python, import_generated_source_edit
from studio_native.source_editor import SourceDocumentSession

EXAMPLE = Path(__file__).resolve().parents[1] / 'examples' / 'qualified-integer-program.smi-graph'


class LinkedSourceRevisionAndTriviaTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        folder = Path(tmp.name)
        self.graph_path = folder / 'reconciliation.smi-graph'
        self.graph_path.write_bytes(EXAMPLE.read_bytes())
        self.graph = ProgramGraph.open(self.graph_path)
        self.graph.edit(self.graph.revision, 'set_property', node='one', key='value', value=17)
        self.graph.edit(self.graph.revision, 'replace_node_operation', node='add', operation='python.multiply')
        self.graph.save(self.graph_path)
        self.original = preview_python(self.graph.state).source
        self.source_path = folder / 'reconciliation.py'
        self.source_path.write_text(self.original, encoding='utf-8')
        self.session = SourceDocumentSession.open(self.source_path)
        self.link = LinkedPythonSource.attach(self.graph, self.session)

    def edit_value(self, old, new):
        candidate = self.session.text.replace(f'_smi_value_0 = {old}', f'_smi_value_0 = {new}')
        self.assertNotEqual(candidate, self.session.text)
        self.session.update(candidate)
        return candidate

    def test_exact_v278_native_failed_path_undo_redo_save_then_second_import(self):
        self.edit_value(17, 23)
        self.assertTrue(self.link.import_edits())
        self.graph.undo(self.graph.revision)
        self.graph.redo(self.graph.revision)
        self.graph.save(self.graph_path)
        self.session.qualify()
        self.session.commit()
        self.edit_value(23, 24)
        self.assertTrue(self.link.import_edits())
        self.assertIn('_smi_value_0 = 24', preview_python(self.graph.state).source)
        self.graph.save(self.graph_path)
        self.session.qualify()
        self.session.commit()
        self.assertFalse(self.session.dirty)
        self.assertFalse(self.graph.dirty)

    def test_restored_same_graph_state_can_revalidate_after_undo_redo(self):
        self.graph.edit(self.graph.revision, 'move_node', node='one', x=500, y=40)
        self.graph.undo(self.graph.revision)
        self.edit_value(17, 23)
        self.assertTrue(self.link.import_edits())

    def test_same_python_different_graph_layout_still_refused(self):
        self.graph.edit(self.graph.revision, 'move_node', node='one', x=500, y=40)
        self.edit_value(17, 23)
        with self.assertRaisesRegex(GraphConflict, 'Graph changed'):
            self.link.import_edits()

    def test_same_python_different_graph_identity_still_refused(self):
        self.graph.edit(self.graph.revision, 'annotate', function=self.graph.state['functions'][0]['id'], text='review')
        self.edit_value(17, 23)
        with self.assertRaisesRegex(GraphConflict, 'Graph changed'):
            self.link.import_edits()

    def test_source_comment_above_function_and_inside_body_survives_literal_import(self):
        source = self.original.replace('def compose(y):', '# author note\ndef compose(y):')
        source = source.replace('    _smi_value_0 = 17', '    # compiler preserves this in source session only\n    _smi_value_0 = 23')
        self.session.update(source)
        self.assertTrue(self.link.import_edits())
        self.assertEqual(self.session.text, source)
        self.assertEqual(self.source_path.read_text(), self.original)
        self.assertNotIn('author note', preview_python(self.graph.state).source)
        self.assertIn('_smi_value_0 = 23', preview_python(self.graph.state).source)
        self.session.commit()
        self.assertEqual(self.source_path.read_text(), source)
        self.graph.save(self.graph_path)
        self.assertFalse(self.graph.dirty)

    def test_source_trivia_only_is_safe_no_graph_transaction_then_edit(self):
        before = self.graph.state
        commented = '# source-owned header\n' + self.original + '\n# source-owned footer\n'
        self.session.update(commented)
        self.assertFalse(self.link.import_edits())
        self.assertEqual(self.graph.state, before)
        self.edit_value(17, 24)
        self.assertTrue(self.link.import_edits())
        self.assertTrue(self.session.text.startswith('# source-owned header'))
        self.assertIn('_smi_value_0 = 24', preview_python(self.graph.state).source)

    def test_source_trivia_plus_operator_import(self):
        self.session.update(self.original.replace(
            '    _smi_value_2 = _smi_value_1 * _smi_value_0',
            '    # keep formatting\n    _smi_value_2 = (_smi_value_1 + _smi_value_0)  # deliberate edit'))
        self.assertTrue(self.link.import_edits())
        self.assertEqual(next(n['operation'] for n in self.graph.state['nodes'] if n['id'] == 'add'), 'python.add')
        self.assertIn('# deliberate edit', self.session.text)

    def test_source_trivia_plus_unsupported_code_refused_with_no_mutation(self):
        before = self.graph.state
        self.session.update('# comment\n' + self.original + '\nprint("extra")\n')
        with self.assertRaisesRegex(ProgramGraphError, 'differs beyond'):
            self.link.import_edits()
        self.assertEqual(self.graph.state, before)
        self.assertTrue(self.session.text.startswith('# comment'))

    def test_import_refuses_reordered_code_even_if_values_same(self):
        before = self.graph.state
        candidate = self.original.replace('    _smi_value_0 = 17\n    _smi_value_1 = x',
                                         '    _smi_value_1 = x\n    _smi_value_0 = 23')
        self.session.update(candidate)
        with self.assertRaisesRegex(ProgramGraphError, 'structure'):
            self.link.import_edits()
        self.assertEqual(self.graph.state, before)

    def test_generated_python_dialog_remains_byte_exact(self):
        with self.assertRaisesRegex(ProgramGraphError, '1 to 32'):
            import_generated_source_edit(self.graph, self.original,
                                         '# comment\n' + self.original,
                                         expected_revision=self.graph.revision)

    def test_saved_source_with_trivia_then_more_edits(self):
        self.session.update('# authored\n' + self.original.replace('_smi_value_0 = 17', '_smi_value_0 = 23'))
        self.assertTrue(self.link.import_edits())
        self.session.commit()
        self.graph.save(self.graph_path)
        self.edit_value(23, 24)
        self.assertTrue(self.link.import_edits())
        self.assertEqual(self.session.text.count('# authored'), 1)
        self.session.commit()
        self.assertIn('# authored', self.source_path.read_text())


if __name__ == '__main__':
    unittest.main()
