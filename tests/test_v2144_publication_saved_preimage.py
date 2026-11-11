"""Python publication refuses stale saved ProgramGraph preimages before source writes."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio_native import python_lowering as adapter
from studio_native.program_graph import ProgramGraph, GraphConflict, ProgramGraphError
from studio_native.python_edit import create_source_exclusive, apply_proposal

EXAMPLE=Path(__file__).resolve().parents[1]/'examples/qualified-integer-program.smi-graph'


class SavedPublicationPreimageTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.directory=Path(temp.name)
        self.graph_path=self.directory/'program.smi-graph'
        self.graph_path.write_bytes(EXAMPLE.read_bytes())
        self.graph=ProgramGraph.open(self.graph_path)
        self.before=self.graph_path.read_bytes()
        self.revision=self.graph.revision
        self.output=self.directory/'published.py'
        self.original=adapter.preview_python(self.graph.state).source
        self.assertIsNotNone(self.original)

    def publish(self, **kwargs):
        return adapter.publish_python(self.graph,self.output,
                                      expected_revision=self.revision,**kwargs)

    def move(self):
        self.assertTrue(self.graph.edit(self.graph.revision,'move_node',
                                        node='one',x=271,y=93))

    def test_unchanged_saved_graph_publishes_exact_source_and_receipt(self):
        result=self.publish()
        self.assertEqual(self.output.read_text(),self.original)
        self.assertEqual(result.graph_sha256,hashlib.sha256(self.before).hexdigest())
        self.assertEqual(result.graph_revision,self.revision)
        self.assertEqual(result.source_sha256,
                         hashlib.sha256(self.output.read_bytes()).hexdigest())
        self.assertEqual(self.graph_path.read_bytes(),self.before)

    def test_reentrant_graph_edit_during_preview_refuses_exclusive_write(self):
        preview=adapter.preview_python
        def graph_advanced(state):
            result=preview(state)
            self.move()
            return result
        with patch.object(adapter,'preview_python',side_effect=graph_advanced), \
                patch('studio_native.python_edit.create_source_exclusive',
                      wraps=create_source_exclusive) as writer:
            with self.assertRaisesRegex(GraphConflict,'Graph changed during Python publication'):
                self.publish()
            writer.assert_not_called()
        self.assertFalse(self.output.exists())
        self.assertEqual(self.graph_path.read_bytes(),self.before)

    def test_graph_saved_at_new_revision_during_preview_cannot_publish_old_code(self):
        preview=adapter.preview_python
        def advanced_and_saved(state):
            result=preview(state)
            self.move()
            self.graph.save(self.graph_path)
            return result
        with patch.object(adapter,'preview_python',side_effect=advanced_and_saved):
            with self.assertRaisesRegex(GraphConflict,'Graph changed during Python publication'):
                self.publish()
        self.assertFalse(self.output.exists())
        self.assertNotEqual(self.graph_path.read_bytes(),self.before)

    def test_external_change_to_saved_graph_during_preview_refuses(self):
        preview=adapter.preview_python
        def external_writer(state):
            result=preview(state)
            self.graph_path.write_bytes(self.before+b' ')
            return result
        with patch.object(adapter,'preview_python',side_effect=external_writer):
            with self.assertRaisesRegex(GraphConflict,'Saved graph changed externally'):
                self.publish()
        self.assertFalse(self.output.exists())

    def test_failed_preview_with_changed_graph_prioritizes_owner_conflict(self):
        def invalid_preview(_state):
            self.move()
            return adapter.PythonPreview(None,('fixture stale compiler issue',))
        with patch.object(adapter,'preview_python',side_effect=invalid_preview):
            with self.assertRaisesRegex(GraphConflict,'Graph changed during Python publication'):
                self.publish()
        self.assertFalse(self.output.exists())

    def test_thrown_preview_error_with_changed_graph_prioritizes_owner_conflict(self):
        def failing_preview(_state):
            self.move()
            raise ProgramGraphError('fixture obsolete compiler error')
        with patch.object(adapter,'preview_python',side_effect=failing_preview):
            with self.assertRaisesRegex(GraphConflict,'Graph changed during Python publication'):
                self.publish()
        self.assertFalse(self.output.exists())

    def test_existing_target_stays_intact_when_graph_changes_during_preview(self):
        old=b'# user authored source\n'
        self.output.write_bytes(old)
        preview=adapter.preview_python
        def late_edit(state):
            result=preview(state)
            self.move()
            return result
        with patch.object(adapter,'preview_python',side_effect=late_edit), \
                patch('studio_native.python_edit.apply_proposal',
                      wraps=apply_proposal) as writer:
            with self.assertRaisesRegex(GraphConflict,'Graph changed during Python publication'):
                self.publish(expected_target_sha256=hashlib.sha256(old).hexdigest())
            writer.assert_not_called()
        self.assertEqual(self.output.read_bytes(),old)
        self.assertFalse((self.directory/'published.py.smi-backup').exists())

    def test_target_preimage_callback_advances_graph_before_replace_and_refuses(self):
        old=b'# author edits\n'
        self.output.write_bytes(old)
        read=Path.read_bytes
        advanced=[False]
        def concurrent_read(path):
            result=read(path)
            if path==self.output and not advanced[0]:
                advanced[0]=True
                self.move()
            return result
        with patch.object(Path,'read_bytes',concurrent_read), \
                patch('studio_native.python_edit.apply_proposal',
                      wraps=apply_proposal) as writer:
            with self.assertRaisesRegex(GraphConflict,'Graph changed during Python publication'):
                self.publish(expected_target_sha256=hashlib.sha256(old).hexdigest())
            writer.assert_not_called()
        self.assertTrue(advanced[0])
        self.assertEqual(self.output.read_bytes(),old)
        self.assertFalse((self.directory/'published.py.smi-backup').exists())

    def test_valid_target_replacement_preserves_existing_source_writer_backup(self):
        old=b'# author original\n'
        self.output.write_bytes(old)
        result=self.publish(expected_target_sha256=hashlib.sha256(old).hexdigest())
        self.assertEqual(self.output.read_text(),self.original)
        self.assertEqual((self.directory/'published.py.smi-backup').read_bytes(),old)
        self.assertEqual(result.graph_sha256,hashlib.sha256(self.before).hexdigest())


if __name__=='__main__':
    unittest.main()
