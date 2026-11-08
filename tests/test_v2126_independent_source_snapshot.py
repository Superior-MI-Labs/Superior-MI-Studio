"""Compiler receipts bind one live source revision and an unchanged disk preimage."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from studio_native import python_lowering as adapter
from studio_native.program_graph import GraphConflict, ProgramGraph, ProgramGraphError
from studio_native.source_editor import SourceDocumentSession

EXAMPLE=Path(__file__).resolve().parents[1]/'examples/qualified-integer-program.smi-graph'


class IndependentSourceSnapshotTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path=Path(tmp.name)/'user.py'
        self.graph=ProgramGraph.open(EXAMPLE)
        self.source=adapter.preview_python(self.graph.state).source
        self.assertIsNotNone(self.source)
        self.edit=self.source.replace('_smi_value_0 = 1','_smi_value_0 = 7',1)
        self.assertNotEqual(self.edit,self.source)
        self.path.write_text(self.edit,encoding='utf-8')
        self.session=SourceDocumentSession.open(self.path)
        self.graph_before=self.graph.state
        self.revision=self.graph.revision

    def review(self):
        return adapter.review_independent_source_functions(
            self.graph,self.session,('increment',),expected_graph_revision=self.revision)

    def import_review(self,review):
        return adapter.import_independent_source_functions(
            self.graph,self.session,review.functions,
            expected_graph_revision=review.graph_revision,
            expected_source_revision=review.source_revision,
            expected_source_sha256=review.source_sha256)

    def test_clean_source_snapshot_still_imports_one_atomic_change(self):
        review=self.review()
        self.assertEqual(review.source_sha256,__import__('hashlib').sha256(
            self.session.text.encode('utf-8')).hexdigest())
        self.assertEqual(review.source_revision,self.session.revision)
        self.assertEqual(self.graph.state,self.graph_before)
        self.assertTrue(self.import_review(review))
        self.assertEqual(self.session.text,self.edit)
        self.assertEqual(self.path.read_text(encoding='utf-8'),self.edit)

    def test_external_write_during_compiler_review_refuses_stale_receipt(self):
        real=adapter._qualified_source_edit_plan
        def external_write(*args,**kwargs):
            answer=real(*args,**kwargs)
            self.path.write_text('# external writer\n',encoding='utf-8')
            return answer
        with patch.object(adapter,'_qualified_source_edit_plan',side_effect=external_write):
            with self.assertRaisesRegex(GraphConflict,'Source changed on disk during'):
                self.review()
        self.assertEqual(self.graph.state,self.graph_before)
        self.assertEqual(self.session.text,self.edit)

    def test_reentrant_source_revision_during_review_refuses_stale_receipt(self):
        real=adapter._qualified_source_edit_plan
        def source_edit(*args,**kwargs):
            answer=real(*args,**kwargs)
            self.session.update(self.session.text+'\n# late draft\n')
            return answer
        with patch.object(adapter,'_qualified_source_edit_plan',side_effect=source_edit):
            with self.assertRaisesRegex(GraphConflict,'Source revision changed during'):
                self.review()
        self.assertEqual(self.graph.state,self.graph_before)
        self.assertIn('late draft',self.session.text)

    def test_external_write_after_plan_before_graph_commit_refuses(self):
        reviewed=self.review()
        real=adapter._independent_functions_plan
        def late_write(*args,**kwargs):
            answer=real(*args,**kwargs)
            self.path.write_text('some other program\n',encoding='utf-8')
            return answer
        with patch.object(adapter,'_independent_functions_plan',side_effect=late_write):
            with self.assertRaisesRegex(GraphConflict,'Source changed on disk before graph import'):
                self.import_review(reviewed)
        self.assertEqual(self.graph.state,self.graph_before)
        self.assertEqual(self.session.text,self.edit)

    def test_failure_diagnostic_does_not_mask_source_change(self):
        self.path.write_text(self.edit.replace('_smi_value_0 = 7',
                                             '_smi_value_0 = unknown_value'),encoding='utf-8')
        self.session=SourceDocumentSession.open(self.path)
        real=adapter._qualified_source_edit_plan
        def changed_while_failing(*args,**kwargs):
            self.path.write_text('# modified while qualifying\n',encoding='utf-8')
            return real(*args,**kwargs)
        with patch.object(adapter,'_qualified_source_edit_plan',side_effect=changed_while_failing):
            with self.assertRaisesRegex(GraphConflict,'Source changed on disk during'):
                self.review()
        self.assertEqual(self.graph.state,self.graph_before)

    def test_unencodable_live_draft_is_refused_without_graph_mutation(self):
        self.session.update(self.edit+'# lone surrogate: \ud800\n')
        with self.assertRaisesRegex(ProgramGraphError,'cannot be encoded as UTF-8'):
            self.review()
        self.assertEqual(self.graph.state,self.graph_before)
        self.assertEqual(self.path.read_text(encoding='utf-8'),self.edit)


if __name__=='__main__':
    unittest.main()
