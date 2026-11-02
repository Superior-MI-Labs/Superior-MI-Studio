"""Independent-source local identifiers survive proven pure dependency reorderings."""
import tempfile
import unittest
from pathlib import Path

from studio_native.program_graph import ProgramGraphError
from studio_native.python_lowering import (
    review_independent_source_functions, import_independent_source_functions,
    review_generated_source_edit,
)
from studio_native.source_editor import SourceDocumentSession
from tests import test_v2103_pure_order_reconciliation as order_fixtures
from tests import test_v2104_nested_roundtrip as branch_fixtures


class StructuralLocalIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'author.py'

    def review(self, graph, text, function):
        self.path.write_text(text,encoding='utf8')
        session=SourceDocumentSession.open(self.path)
        receipt=review_independent_source_functions(graph,session,(function,),
            expected_graph_revision=graph.revision)
        return session,receipt

    def test_reordered_pure_dependent_calculation_with_readable_local_name(self):
        harness=order_fixtures.PureDependencyOrderTests('runTest')
        harness.setUp()
        self.addCleanup(harness.doCleanups)
        # First assignment is moved and its output renamed, while graph values
        # and the source's second expression now depend upon that assignment.
        text=harness.edited.replace('_smi_value_3','partial_total')
        self.assertNotEqual(text,harness.edited)
        before=harness.h.graph.state
        session,receipt=self.review(harness.h.graph,'# extra source\n'+text,'compose')
        self.assertEqual([(c.node_id,c.input_port) for c in receipt.changes],[('a','left')])
        self.assertEqual(harness.h.graph.state,before)
        self.assertTrue(import_independent_source_functions(harness.h.graph,session,('compose',),
            expected_graph_revision=receipt.graph_revision,
            expected_source_revision=receipt.source_revision,
            expected_source_sha256=receipt.source_sha256))
        self.assertEqual(session.text,'# extra source\n'+text)
        self.assertTrue(harness.h.graph.undo(harness.h.graph.revision))
        self.assertEqual(harness.h.graph.state['edges'],before['edges'])
        with self.assertRaises(ProgramGraphError):
            review_generated_source_edit(harness.h.graph,harness.base,text,
                expected_revision=harness.h.graph.revision)

    def test_branch_local_reordering_and_alias_are_bounded_by_the_branch(self):
        harness=branch_fixtures.BranchLocalReconciliationTests('runTest')
        harness.setUp()
        self.addCleanup(harness.doCleanups)
        text=harness.edited.replace('_smi_value_4','branch_total')
        session,receipt=self.review(harness.h.graph,text,'choose')
        self.assertEqual([(c.node_id,c.input_port) for c in receipt.changes],[('a','left')])
        self.assertEqual(session.text,text)

    def test_reordered_annotated_alias_and_branch_pass_share_existing_proof(self):
        harness=branch_fixtures.BranchLocalReconciliationTests('runTest')
        harness.setUp()
        self.addCleanup(harness.doCleanups)
        text=harness.edited.replace('_smi_value_4', 'readable_total').replace(
            '        readable_total =', '        readable_total: int =')
        text=text.replace('    if _smi_value_2:', '    if _smi_value_2:\n        pass')
        original=harness.h.graph.state
        session,receipt=self.review(harness.h.graph,text,'choose')
        self.assertEqual([(c.node_id,c.input_port) for c in receipt.changes],[('a','left')])
        self.assertTrue(import_independent_source_functions(harness.h.graph,session,('choose',),
            expected_graph_revision=receipt.graph_revision,
            expected_source_revision=receipt.source_revision,
            expected_source_sha256=receipt.source_sha256))
        self.assertEqual(session.text,text)
        self.assertTrue(harness.h.graph.undo(harness.h.graph.revision))
        self.assertEqual(harness.h.graph.state['edges'],original['edges'])

    def test_stale_source_refuses_reordered_alias_import(self):
        harness=order_fixtures.PureDependencyOrderTests('runTest')
        harness.setUp()
        self.addCleanup(harness.doCleanups)
        text=harness.edited.replace('_smi_value_3','partial_total')
        session,receipt=self.review(harness.h.graph,text,'compose')
        original=harness.h.graph.state
        self.path.write_text(text+'\n# external update\n',encoding='utf8')
        with self.assertRaises(Exception):
            import_independent_source_functions(harness.h.graph,session,('compose',),
                expected_graph_revision=receipt.graph_revision,
                expected_source_revision=receipt.source_revision,
                expected_source_sha256=receipt.source_sha256)
        self.assertEqual(harness.h.graph.state,original)

    def test_ambiguous_alias_collision_and_renamed_parameter_are_refused(self):
        harness=order_fixtures.PureDependencyOrderTests('runTest')
        harness.setUp()
        self.addCleanup(harness.doCleanups)
        base=harness.edited
        original=harness.h.graph.state
        scenarios=[base.replace('_smi_value_3','x'),
                   base.replace('_smi_value_3','_smi_value_2'),
                   base.replace('_smi_value_3','partial_total').replace('_smi_value_2','partial_total'),
                   base.replace('_smi_value_3','partial_total').replace('return _smi_value_4','return new_value')]
        for candidate in scenarios:
            with self.subTest(case=candidate[-100:]):
                with self.assertRaises(ProgramGraphError):
                    self.review(harness.h.graph,candidate,'compose')
                self.assertEqual(harness.h.graph.state,original)

    def test_no_alias_identity_guessing_if_unrelated_assignment_added(self):
        harness=order_fixtures.PureDependencyOrderTests('runTest')
        harness.setUp()
        self.addCleanup(harness.doCleanups)
        candidate=harness.edited.replace('    return _smi_value_4',
            '    unexpected = 5\n    return _smi_value_4')
        with self.assertRaises(ProgramGraphError):
            self.review(harness.h.graph,candidate,'compose')


if __name__=='__main__':
    unittest.main()
