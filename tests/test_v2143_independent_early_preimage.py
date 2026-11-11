"""Early independent-source admission must not report stale compiler diagnostics."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio_native import python_lowering as adapter
from studio_native.program_graph import GraphConflict, ProgramGraph, ProgramGraphError
from studio_native.source_editor import SourceDocumentSession

EXAMPLE=Path(__file__).resolve().parents[1]/'examples/qualified-integer-program.smi-graph'


class IndependentEarlyPreimageTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path=Path(temp.name)/'independent.py'
        self.graph=ProgramGraph.open(EXAMPLE)
        self.graph_before=self.graph.state
        self.revision=self.graph.revision
        generated=adapter.preview_python(self.graph.state).source
        self.assertIsNotNone(generated)
        self.source=generated.replace('_smi_value_0 = 1',
                                      '_smi_value_0 = 13',1)
        self.assertNotEqual(self.source,generated)
        self.path.write_text(self.source,encoding='utf-8')
        self.session=SourceDocumentSession.open(self.path)

    def review(self,functions=('increment',)):
        return adapter.review_independent_source_functions(
            self.graph,self.session,functions,
            expected_graph_revision=self.revision)

    def move_graph(self):
        self.assertTrue(self.graph.edit(self.graph.revision,'move_node',
                                        node='one',x=248,y=68))

    def test_normal_review_and_import_still_use_original_proof_pipeline(self):
        review=self.review()
        self.assertEqual(review.graph_revision,self.revision)
        self.assertTrue(review.changes)
        self.assertEqual(self.graph.state,self.graph_before)
        self.assertTrue(adapter.import_independent_source_functions(
            self.graph,self.session,review.functions,
            expected_graph_revision=review.graph_revision,
            expected_source_revision=review.source_revision,
            expected_source_sha256=review.source_sha256))
        self.assertEqual(self.path.read_text(encoding='utf-8'),self.source)

    def test_live_editor_edit_during_generated_preview_refuses_preflight(self):
        original=adapter.preview_python
        def concurrent(state):
            result=original(state)
            self.session.update(self.session.text+'\n# later source revision\n')
            return result
        with patch.object(adapter,'preview_python',side_effect=concurrent):
            with self.assertRaisesRegex(GraphConflict,'Source revision changed during'):
                self.review()
        self.assertEqual(self.graph.state,self.graph_before)

    def test_external_write_during_preview_refuses_preflight(self):
        original=adapter.preview_python
        def concurrent(state):
            result=original(state)
            self.path.write_text('# external replacement\n',encoding='utf-8')
            return result
        with patch.object(adapter,'preview_python',side_effect=concurrent):
            with self.assertRaisesRegex(GraphConflict,'Source changed on disk during'):
                self.review()
        self.assertEqual(self.graph.state,self.graph_before)
        self.assertEqual(self.session.text,self.source)

    def test_graph_edit_during_invalid_preview_prefers_graph_conflict(self):
        def concurrent(_state):
            self.move_graph()
            return adapter.PythonPreview(None,('fixture stale compiler error',))
        with patch.object(adapter,'preview_python',side_effect=concurrent):
            with self.assertRaisesRegex(GraphConflict,'Graph revision changed during'):
                self.review()
        self.assertNotEqual(self.graph.revision,self.revision)

    def test_keyword_admission_error_with_reentrant_source_update_refuses(self):
        def rejected(*args,**kwargs):
            self.session.update(self.session.text+'\n# changed during keyword proof\n')
            raise ProgramGraphError('fixture: obsolete keyword diagnostic')
        with patch.object(adapter,'_independent_keyword_parameter_contract',
                          side_effect=rejected):
            with self.assertRaisesRegex(GraphConflict,'Source revision changed during'):
                self.review()
        self.assertEqual(self.graph.state,self.graph_before)

    def test_transient_function_proof_error_with_saved_byte_change_refuses(self):
        initial_revision=self.session.revision
        initial_text=self.session.text
        def rejected(*args,**kwargs):
            altered=self.session.saved_raw.replace(b'\n',b'\r\n')
            self.assertNotEqual(altered,self.session.saved_raw)
            self.path.write_bytes(altered)
            self.session.saved_raw=altered
            raise ProgramGraphError('fixture: obsolete local syntax diagnostic')
        with patch.object(adapter,'_independent_proof_function',side_effect=rejected):
            with self.assertRaisesRegex(GraphConflict,'Source saved baseline changed during'):
                self.review()
        self.assertEqual((self.session.revision,self.session.text),
                         (initial_revision,initial_text))
        self.assertEqual(self.graph.state,self.graph_before)

    def test_transient_proof_success_with_graph_update_still_refuses(self):
        original=adapter._independent_proof_function
        def concurrent(*args,**kwargs):
            proved=original(*args,**kwargs)
            self.move_graph()
            return proved
        with patch.object(adapter,'_independent_proof_function',side_effect=concurrent):
            with self.assertRaisesRegex(GraphConflict,'Graph revision changed during'):
                self.review()
        self.assertNotEqual(self.graph.revision,self.revision)
        self.assertEqual(self.session.text,self.source)

    def test_stable_missing_function_retains_precise_source_diagnostic(self):
        with self.assertRaisesRegex(ProgramGraphError,
                                    "Function 'missing' must occur exactly once"):
            self.review(('missing',))
        self.assertEqual(self.graph.state,self.graph_before)
        self.assertEqual(self.path.read_text(encoding='utf-8'),self.source)


if __name__=='__main__':unittest.main()
