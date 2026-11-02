"""Source-to-graph review uses the same proof as commit, without another owner."""
import tempfile
import unittest
from pathlib import Path
from studio_native.program_graph import ProgramGraph, GraphConflict, ProgramGraphError
from studio_native.python_lowering import (LinkedPythonSource, preview_python,
    review_generated_source_edit, import_generated_source_edit)
from studio_native.source_editor import SourceDocumentSession

EXAMPLE=Path(__file__).resolve().parents[1]/'examples/qualified-integer-program.smi-graph'

class ReconciliationReviewContract(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.graph=ProgramGraph.open(EXAMPLE)
        self.base=preview_python(self.graph.state).source
        self.source=self.root/'linked.py';self.source.write_text(self.base,encoding='utf-8')
        self.session=SourceDocumentSession.open(self.source)
        self.link=LinkedPythonSource.attach(self.graph,self.session)

    def test_exact_baseline_has_no_commands(self):
        result=self.link.review_edits()
        self.assertEqual(result.graph_revision,self.graph.revision)
        self.assertEqual(result.changes,())
        self.assertEqual(self.link.source_revision,0)

    def test_two_operation_preflight_grouped_by_original_function_and_node_id(self):
        revised=self.base.replace('_smi_value_0 = 1','_smi_value_0 = 29').replace(
            '_smi_value_1 + _smi_value_0','_smi_value_1 * _smi_value_0')
        self.session.update(revised)
        before=self.graph.state
        undo=len(self.graph._undo)
        report=self.link.review_edits()
        self.assertEqual([(e.node_id,e.action,e.before,e.after) for e in report.changes],
            [('one','set_property',1,29),('add','replace_node_operation','python.add','python.multiply')])
        self.assertEqual({e.function for e in report.changes},{'increment'})
        self.assertEqual(self.graph.state,before)
        self.assertEqual(len(self.graph._undo),undo)
        self.assertEqual(self.link.source_revision,0)
        self.assertTrue(self.link.import_edits())
        self.assertEqual(preview_python(self.graph.state).source,revised)
        self.assertEqual(self.graph.revision,before['revision']+1)
        self.assertEqual(self.source.read_text(),self.base)

    def test_comment_only_review_is_noop_and_preserved_by_owner(self):
        self.session.update('# author comment\n'+self.base)
        self.assertFalse(self.link.review_edits().changes)
        self.assertFalse(self.link.import_edits())
        self.assertEqual(self.graph.state,ProgramGraph.open(EXAMPLE).state)
        self.assertTrue(self.session.text.startswith('# author comment'))

    def test_source_trivia_and_expression_change_still_proven(self):
        self.session.update('# note\n'+self.base.replace('_smi_value_0 = 1',
            '# inside function\n    _smi_value_0 = 8'))
        report=self.link.review_edits()
        self.assertEqual(len(report.changes),1)
        self.assertEqual((report.changes[0].node_id,report.changes[0].after),('one',8))
        self.assertTrue(self.link.import_edits())
        self.assertIn('# note',self.session.text)

    def test_preview_does_not_grant_permission_when_graph_changes(self):
        self.session.update(self.base.replace('_smi_value_0 = 1','_smi_value_0 = 7'))
        self.assertEqual(len(self.link.review_edits().changes),1)
        self.graph.edit(self.graph.revision,'move_node',node='one',x=400,y=20)
        before=self.graph.state
        with self.assertRaisesRegex(GraphConflict,'Graph changed'):
            self.link.import_edits()
        self.assertEqual(self.graph.state,before)
        self.assertTrue(self.session.dirty)

    def test_preview_does_not_grant_permission_when_source_changes(self):
        self.session.update(self.base.replace('_smi_value_0 = 1','_smi_value_0 = 8'))
        self.link.review_edits()
        self.session.update('def impossible(:\n')
        before=self.graph.state
        with self.assertRaises(ProgramGraphError):self.link.import_edits()
        self.assertEqual(before,self.graph.state)

    def test_unsupported_extra_statement_fails_preflight_without_graph_edit(self):
        self.session.update(self.base+'\nprint("unknown")\n')
        before=self.graph.state
        with self.assertRaisesRegex(ProgramGraphError,'differs beyond'):
            self.link.review_edits()
        self.assertEqual(self.graph.state,before)
        with self.assertRaises(ProgramGraphError):self.link.import_edits()

    def test_graph_revision_undo_redo_identity_restored_is_allowed(self):
        self.session.update(self.base.replace('_smi_value_0 = 1','_smi_value_0 = 9'))
        self.graph.edit(self.graph.revision,'move_node',node='one',x=200,y=30)
        self.graph.undo(self.graph.revision)
        self.assertEqual(len(self.link.review_edits().changes),1)
        self.assertTrue(self.link.import_edits())

    def test_external_change_fails_preview_and_commit(self):
        self.session.update(self.base.replace('_smi_value_0 = 1','_smi_value_0 = 11'))
        self.source.write_text('external change\n',encoding='utf-8')
        for action in (self.link.review_edits,self.link.import_edits):
            with self.subTest(action=action),self.assertRaisesRegex(GraphConflict,'on disk'):
                action()
        self.assertFalse(self.graph.dirty)

    def test_full_compiler_proof_rejects_unknown_return_mutation(self):
        bad=self.base.replace('return _smi_value_2','return 999')
        with self.assertRaises(ProgramGraphError):
            review_generated_source_edit(self.graph,self.base,bad,
                expected_revision=self.graph.revision)

    def test_byte_exact_generated_editor_still_refuses_formatting(self):
        with self.assertRaises(ProgramGraphError):
            review_generated_source_edit(self.graph,self.base,'# note\n'+self.base,
                expected_revision=self.graph.revision)

    def test_stale_expected_revision_refused(self):
        with self.assertRaises(GraphConflict):
            review_generated_source_edit(self.graph,self.base,self.base,
                expected_revision=self.graph.revision+1)

if __name__=='__main__':unittest.main()
