"""Linked source attachment must bind one exact graph/source/disk preimage."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio_native import python_lowering as adapter
from studio_native.program_graph import GraphConflict, ProgramGraph
from studio_native.source_editor import SourceDocumentSession

EXAMPLE=Path(__file__).resolve().parents[1]/'examples/qualified-integer-program.smi-graph'


class LinkedSourceAdmissionTests(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path=Path(directory.name)/'linked.py'
        self.graph=ProgramGraph.open(EXAMPLE)
        self.source=adapter.preview_python(self.graph.state).source
        self.assertIsNotNone(self.source)
        self.path.write_text(self.source,encoding='utf-8')
        self.session=SourceDocumentSession.open(self.path)
        self.graph_before=self.graph.state

    def attach(self):
        return adapter.LinkedPythonSource.attach(self.graph,self.session)

    def move_graph(self):
        self.assertTrue(self.graph.edit(self.graph.revision,'move_node',
                                        node='one',x=283,y=71))

    def test_clean_exact_link_retains_proven_graph_and_source_receipt(self):
        with patch.object(adapter,'preview_python',wraps=adapter.preview_python) as preview:
            link=self.attach()
        self.assertEqual(preview.call_count,1)
        self.assertEqual(link.graph_revision,self.graph.revision)
        self.assertEqual(link.source_revision,self.session.revision)
        self.assertEqual(link.source_text,self.session.text)
        self.assertEqual(link.base_source,self.source)
        self.assertFalse(link.import_edits())
        self.assertEqual(self.graph.state,self.graph_before)

    def test_reentrant_graph_edit_after_preview_refuses_attachment(self):
        preview=adapter.preview_python
        def late_graph(state):
            result=preview(state)
            self.move_graph()
            return result
        with patch.object(adapter,'preview_python',side_effect=late_graph):
            with self.assertRaisesRegex(GraphConflict,'Graph changed during Python link admission'):
                self.attach()
        self.assertEqual(self.session.text,self.source)
        self.assertEqual(self.path.read_text(encoding='utf-8'),self.source)

    def test_reentrant_editor_edit_after_preview_refuses_attachment(self):
        preview=adapter.preview_python
        def late_source(state):
            result=preview(state)
            self.session.update(self.session.text+'\n# unsaved after preview\n')
            return result
        with patch.object(adapter,'preview_python',side_effect=late_source):
            with self.assertRaisesRegex(GraphConflict,'Source changed during Python link admission'):
                self.attach()
        self.assertEqual(self.graph.state,self.graph_before)
        self.assertTrue(self.session.dirty)

    def test_external_disk_replacement_after_preview_refuses_attachment(self):
        preview=adapter.preview_python
        def external(state):
            result=preview(state)
            self.path.write_text('# external source replacement\n',encoding='utf-8')
            return result
        with patch.object(adapter,'preview_python',side_effect=external):
            with self.assertRaisesRegex(GraphConflict,'Source changed on disk during Python link admission'):
                self.attach()
        self.assertEqual(self.session.text,self.source)
        self.assertEqual(self.graph.state,self.graph_before)

    def test_saved_bytes_change_even_with_same_editor_revision_refuses(self):
        preview=adapter.preview_python
        def saved_preimage_advance(state):
            result=preview(state)
            # Model a source-owner baseline update with newline conversion:
            # normalized text/revision unchanged, exact saved bytes different.
            new_raw=self.session.saved_raw.replace(b'\n',b'\r\n')
            self.assertNotEqual(new_raw,self.session.saved_raw)
            self.path.write_bytes(new_raw)
            self.session.saved_raw=new_raw
            return result
        revision,text=self.session.revision,self.session.text
        with patch.object(adapter,'preview_python',side_effect=saved_preimage_advance):
            with self.assertRaisesRegex(GraphConflict,'Source changed during Python link admission'):
                self.attach()
        self.assertEqual((self.session.revision,self.session.text),(revision,text))
        self.assertEqual(self.graph.state,self.graph_before)

    def test_inspection_callback_editor_change_refuses_before_preview(self):
        inspect=self.session.inspect_external
        def change_during_inspection():
            result=inspect()
            self.session.update(self.session.text+'\n# late inspect edit\n')
            return result
        with patch.object(self.session,'inspect_external',side_effect=change_during_inspection), \
                patch.object(adapter,'preview_python',wraps=adapter.preview_python) as preview:
            with self.assertRaisesRegex(GraphConflict,'Source changed during Python link admission'):
                self.attach()
            preview.assert_not_called()
        self.assertEqual(self.graph.state,self.graph_before)

    def test_graph_change_during_fingerprint_refuses_before_preview(self):
        fingerprint=adapter.LinkedPythonSource._graph_fingerprint
        def late_fingerprint(graph):
            result=fingerprint(graph)
            self.move_graph()
            return result
        with patch.object(adapter.LinkedPythonSource,'_graph_fingerprint',
                          side_effect=late_fingerprint), \
                patch.object(adapter,'preview_python',wraps=adapter.preview_python) as preview:
            with self.assertRaisesRegex(GraphConflict,'Graph changed during Python link admission'):
                self.attach()
            preview.assert_not_called()

    def test_concurrent_graph_change_supersedes_stale_preview_refusal(self):
        def invalid_preview(state):
            self.move_graph()
            return adapter.PythonPreview(None,('fixture: unqualified',))
        with patch.object(adapter,'preview_python',side_effect=invalid_preview):
            with self.assertRaisesRegex(GraphConflict,'Graph changed during Python link admission'):
                self.attach()


if __name__=='__main__':unittest.main()
