"""Linked-source review/import must not use a stale text or disk receipt."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio_native import python_lowering as adapter
from studio_native.program_graph import GraphConflict, ProgramGraph, ProgramGraphError
from studio_native.source_editor import SourceDocumentSession

EXAMPLE = Path(__file__).resolve().parents[1] / 'examples/qualified-integer-program.smi-graph'


class LinkedSourceSnapshotTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / 'linked.py'
        self.graph = ProgramGraph.open(EXAMPLE)
        self.original = adapter.preview_python(self.graph.state).source
        self.path.write_text(self.original, encoding='utf-8')
        self.session = SourceDocumentSession.open(self.path)
        self.link = adapter.LinkedPythonSource.attach(self.graph, self.session)
        self.graph_before = self.graph.state
        self.edited = self.original.replace('_smi_value_0 = 1', '_smi_value_0 = 7', 1)
        self.assertNotEqual(self.edited, self.original)
        self.session.update(self.edited)

    def test_unmodified_snapshot_review_and_atomic_import_still_work(self):
        report = self.link.review_edits()
        self.assertEqual(len(report.changes), 1)
        self.assertEqual(self.graph.state, self.graph_before)
        self.assertTrue(self.link.import_edits())
        self.assertEqual(self.session.text, self.edited)
        self.assertEqual(self.path.read_text(encoding='utf-8'), self.original)
        self.assertIn('_smi_value_0 = 7', adapter.preview_python(self.graph.state).source)

    def test_review_refuses_external_write_during_compiler_proof(self):
        real = adapter._qualified_source_edit_plan

        def external(*args, **kwargs):
            result = real(*args, **kwargs)
            self.path.write_text('# changed elsewhere\n', encoding='utf-8')
            return result

        with patch.object(adapter, '_qualified_source_edit_plan', side_effect=external):
            with self.assertRaisesRegex(GraphConflict, 'on disk'):
                self.link.review_edits()
        self.assertEqual(self.graph.state, self.graph_before)
        self.assertEqual(self.link.source_revision, 0)

    def test_review_refuses_reentrant_source_revision(self):
        real = adapter._qualified_source_edit_plan

        def reentrant(*args, **kwargs):
            result = real(*args, **kwargs)
            self.session.update(self.session.text + '\n# changed in editor\n')
            return result

        with patch.object(adapter, '_qualified_source_edit_plan', side_effect=reentrant):
            with self.assertRaisesRegex(GraphConflict, 'Source changed during linked'):
                self.link.review_edits()
        self.assertEqual(self.graph.state, self.graph_before)

    def test_import_refuses_external_write_before_graph_transaction(self):
        real = adapter._qualified_source_edit_plan

        def external(*args, **kwargs):
            result = real(*args, **kwargs)
            self.path.write_text('external = True\n', encoding='utf-8')
            return result

        with patch.object(adapter, '_qualified_source_edit_plan', side_effect=external), \
                patch.object(self.graph, 'edit_many', wraps=self.graph.edit_many) as edit:
            with self.assertRaisesRegex(GraphConflict, 'on disk'):
                self.link.import_edits()
            edit.assert_not_called()
        self.assertEqual(self.graph.state, self.graph_before)
        self.assertEqual(self.link.source_revision, 0)

    def test_import_refuses_reentrant_editor_change_before_graph_transaction(self):
        real = adapter._qualified_source_edit_plan

        def reentrant(*args, **kwargs):
            result = real(*args, **kwargs)
            self.session.update(self.session.text + '\n# late draft\n')
            return result

        with patch.object(adapter, '_qualified_source_edit_plan', side_effect=reentrant), \
                patch.object(self.graph, 'edit_many', wraps=self.graph.edit_many) as edit:
            with self.assertRaisesRegex(GraphConflict, 'Source changed during linked'):
                self.link.import_edits()
            edit.assert_not_called()
        self.assertEqual(self.graph.state, self.graph_before)
        self.assertIn('late draft', self.session.text)

    def test_failed_compiler_proof_prefers_source_conflict_diagnostic(self):
        real = adapter._qualified_source_edit_plan
        self.session.update(self.original + '\nprint("unsupported top-level")\n')

        def failing(*args, **kwargs):
            self.path.write_text('# changed during failure\n', encoding='utf-8')
            return real(*args, **kwargs)

        with patch.object(adapter, '_qualified_source_edit_plan', side_effect=failing):
            with self.assertRaisesRegex(GraphConflict, 'on disk'):
                self.link.import_edits()
        self.assertEqual(self.graph.state, self.graph_before)

    def test_unencodable_draft_refuses_without_raw_unicode_exception(self):
        self.session.update(self.edited + '\n# malformed \ud800\n')
        with self.assertRaisesRegex(ProgramGraphError, 'cannot be encoded as UTF-8'):
            self.link.review_edits()
        with self.assertRaisesRegex(ProgramGraphError, 'cannot be encoded as UTF-8'):
            self.link.import_edits()
        self.assertEqual(self.graph.state, self.graph_before)

    def test_source_save_during_proof_invalidates_captured_disk_preimage(self):
        real = adapter._qualified_source_edit_plan

        def commit_source(*args, **kwargs):
            result = real(*args, **kwargs)
            self.session.commit()
            return result

        with patch.object(adapter, '_qualified_source_edit_plan', side_effect=commit_source), \
                patch.object(self.graph, 'edit_many', wraps=self.graph.edit_many) as edit:
            with self.assertRaisesRegex(GraphConflict, 'Source changed during linked'):
                self.link.import_edits()
            edit.assert_not_called()
        self.assertEqual(self.graph.state, self.graph_before)
        self.assertEqual(self.path.read_text(encoding='utf-8'), self.edited)
        self.assertEqual(self.link.source_revision, 0)

    def test_noop_receipt_does_not_advance_after_reentrant_source_update(self):
        # Start from an unchanged, freshly linked baseline; no compiler work.
        self.session = SourceDocumentSession.open(self.path)
        self.link = adapter.LinkedPythonSource.attach(self.graph, self.session)
        real = self.link._qualify_receipt
        count = 0

        def source_change_during_receipt():
            nonlocal count
            count += 1
            if count == 2:
                self.session.update(self.original + '\n# late note\n')
            return real()

        with patch.object(self.link, '_qualify_receipt', side_effect=source_change_during_receipt):
            with self.assertRaisesRegex(GraphConflict, 'Source changed during linked'):
                self.link.import_edits()
        self.assertEqual(self.graph.state, self.graph_before)
        self.assertEqual(self.link.source_revision, 0)
        self.assertEqual(self.link.source_text, self.original)

    def test_graph_identity_changed_during_compiler_proof_refuses(self):
        real = adapter._qualified_source_edit_plan

        def change_graph(*args, **kwargs):
            result = real(*args, **kwargs)
            self.graph.edit(self.graph.revision, 'move_node', node='one', x=213, y=29)
            return result

        with patch.object(adapter, '_qualified_source_edit_plan', side_effect=change_graph), \
                patch.object(self.graph, 'edit_many', wraps=self.graph.edit_many) as edit:
            with self.assertRaisesRegex(GraphConflict, 'Graph changed since source link'):
                self.link.import_edits()
            edit.assert_not_called()
        self.assertEqual(self.link.source_revision, 0)


if __name__ == '__main__':
    unittest.main()
