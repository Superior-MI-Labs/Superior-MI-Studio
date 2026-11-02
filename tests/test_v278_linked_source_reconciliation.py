"""Source-owned .py → graph-owned ProgramGraph, without a second document store."""
import tempfile
import unittest
from pathlib import Path

from studio_native.program_graph import ProgramGraph, GraphConflict, ProgramGraphError
from studio_native.python_lowering import LinkedPythonSource, preview_python
from studio_native.source_editor import SourceDocumentSession

EXAMPLES = Path(__file__).resolve().parents[1] / 'examples'


class LinkedSourceReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.graph_path = self.folder / 'working.smi-graph'
        self.graph_path.write_bytes((EXAMPLES / 'qualified-integer-program.smi-graph').read_bytes())
        self.graph = ProgramGraph.open(self.graph_path)
        self.base = preview_python(self.graph.state).source
        self.source_path = self.folder / 'working.py'
        self.source_path.write_text(self.base, encoding='utf-8')
        self.session = SourceDocumentSession.open(self.source_path)

    def link(self):
        return LinkedPythonSource.attach(self.graph, self.session)

    def candidate(self, source):
        return source.replace('_smi_value_0 = 1', '_smi_value_0 = 17').replace(
            '_smi_value_1 + _smi_value_0', '_smi_value_1 * _smi_value_0')

    def test_clean_exact_baseline_and_noop(self):
        link = self.link()
        self.assertFalse(link.import_edits())
        self.assertEqual(self.graph.revision, link.graph_revision)
        self.assertFalse(self.graph.dirty)
        self.assertFalse(self.session.dirty)

    def test_source_owned_draft_to_graph_is_one_undoable_transaction(self):
        previous = self.graph.state
        link = self.link()
        revised = self.candidate(self.base)
        self.assertTrue(self.session.update(revised))
        self.assertTrue(self.session.dirty)
        self.assertTrue(link.import_edits())
        self.assertEqual(preview_python(self.graph.state).source, revised)
        self.assertEqual(self.graph.revision, previous['revision'] + 1)
        self.assertEqual(self.graph.state['edges'], previous['edges'])
        self.assertEqual(self.graph.state['layout'], previous['layout'])
        self.assertEqual(self.source_path.read_text(), self.base)
        self.assertEqual(self.graph_path.read_bytes(),
                         (EXAMPLES / 'qualified-integer-program.smi-graph').read_bytes())
        self.assertTrue(self.session.dirty, 'Import must never auto-save source')
        self.assertTrue(self.graph.dirty, 'Import must never auto-save graph')
        self.assertFalse(link.import_edits())
        self.assertTrue(self.graph.undo(self.graph.revision))
        self.assertEqual(preview_python(self.graph.state).source, self.base)

    def test_sequential_source_revisions_reconcile_without_new_link(self):
        link = self.link()
        self.session.update(self.base.replace('_smi_value_0 = 1', '_smi_value_0 = 4'))
        self.assertTrue(link.import_edits())
        second = self.session.text.replace('_smi_value_0 = 4', '_smi_value_0 = 9')
        self.session.update(second)
        self.assertTrue(link.import_edits())
        self.assertEqual(preview_python(self.graph.state).source, second)

    def test_unknown_source_program_cannot_be_linked(self):
        self.source_path.write_text(self.base + '# untouched comment\n', encoding='utf-8')
        self.session = SourceDocumentSession.open(self.source_path)
        with self.assertRaisesRegex(GraphConflict, 'exact generated-Python baseline'):
            self.link()

    def test_existing_unsaved_source_cannot_claim_common_ancestor(self):
        self.session.update(self.candidate(self.base))
        with self.assertRaisesRegex(GraphConflict, 'clean'):
            self.link()

    def test_unsupported_source_edits_are_retained_without_graph_mutation(self):
        link = self.link()
        original = self.graph.state
        unexpected = self.candidate(self.base) + '\nprint("unsupported")\n'
        self.session.update(unexpected)
        with self.assertRaisesRegex(ProgramGraphError, 'differs beyond qualified'):
            link.import_edits()
        self.assertEqual(self.session.text, unexpected)
        self.assertEqual(self.graph.state, original)
        self.assertEqual(self.source_path.read_text(), self.base)

    def test_invalid_syntax_is_retained_and_refused(self):
        link = self.link()
        self.session.update('def bad(:\n')
        with self.assertRaises(ProgramGraphError):
            link.import_edits()
        self.assertEqual(self.session.text, 'def bad(:\n')
        self.assertFalse(self.graph.dirty)

    def test_graph_changed_since_link_refuses_rebase(self):
        link = self.link()
        self.session.update(self.candidate(self.base))
        self.graph.edit(self.graph.revision, 'move_node', node='one', x=321, y=42)
        before = self.graph.state
        with self.assertRaisesRegex(GraphConflict, 'Graph changed'):
            link.import_edits()
        self.assertEqual(self.graph.state, before)
        self.assertTrue(self.session.dirty)

    def test_external_source_change_blocks_import_preserving_draft(self):
        link = self.link()
        self.session.update(self.candidate(self.base))
        self.source_path.write_text('unexpected external edit\n', encoding='utf-8')
        with self.assertRaisesRegex(GraphConflict, 'on disk'):
            link.import_edits()
        self.assertFalse(self.graph.dirty)
        self.assertEqual(self.session.text, self.candidate(self.base))

    def test_saved_source_revision_imports_from_existing_exact_link(self):
        link = self.link()
        self.session.update(self.candidate(self.base))
        self.session.commit()
        self.assertTrue(link.import_edits(), 'Source save must not strand graph reconciliation')
        self.assertEqual(preview_python(self.graph.state).source, self.session.text)
        self.assertFalse(self.session.dirty)
        self.assertTrue(self.graph.dirty)

    def test_saved_source_then_another_unsaved_edit_keeps_existing_baseline_safe(self):
        link = self.link()
        self.session.update(self.candidate(self.base))
        self.session.commit()
        self.session.update(self.session.text.replace('_smi_value_0 = 17', '_smi_value_0 = 23'))
        with self.assertRaisesRegex(GraphConflict, 'unproven draft'):
            link.import_edits()
        self.assertFalse(self.graph.dirty)

    def test_save_after_graph_import_allows_more_source_edits(self):
        link = self.link()
        self.session.update(self.candidate(self.base))
        self.assertTrue(link.import_edits())
        self.session.commit()
        self.session.update(self.session.text.replace('_smi_value_0 = 17', '_smi_value_0 = 23'))
        self.assertTrue(link.import_edits())
        self.assertIn('_smi_value_0 = 23', preview_python(self.graph.state).source)

    def test_link_can_be_reestablished_after_both_owners_advance_and_save(self):
        link = self.link()
        self.session.update(self.candidate(self.base))
        self.assertTrue(link.import_edits())
        self.graph.save(self.graph_path)
        self.session.commit()
        again = self.link()
        self.assertFalse(again.import_edits())


if __name__ == '__main__':
    unittest.main()
