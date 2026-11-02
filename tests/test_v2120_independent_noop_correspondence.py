"""Source-only annotations and no-op guards share the existing graph compiler proof."""
import tempfile
import unittest
from pathlib import Path

from studio_native.program_graph import ProgramGraphError, GraphConflict
from studio_native.python_lowering import (
    review_independent_source_functions, import_independent_source_functions,
    review_generated_source_edit)
from studio_native.source_editor import SourceDocumentSession
from tests import test_v2114_independent_local_correspondence as local_fixtures
from tests import test_v2104_nested_roundtrip as branch_fixtures


class SourceOnlyNoops(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'authored.py'

    def session(self, source):
        self.path.write_text(source,encoding='utf-8')
        return SourceDocumentSession.open(self.path)

    def harness(self):
        fixture=local_fixtures.IndependentLocalCorrespondenceTests('runTest')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        return fixture

    def review(self, graph, source, functions):
        session=self.session(source)
        receipt=review_independent_source_functions(graph,session,functions,
            expected_graph_revision=graph.revision)
        return session,receipt

    def test_bare_annotation_existing_local_is_source_owned(self):
        h=self.harness()
        token='    _smi_value_2 = difference('
        self.assertEqual(h.base.count(token),1)
        authored=h.base.replace(token,'    _smi_value_2: int\n'+token)
        session,receipt=self.review(h.h.graph,authored,('caller',))
        self.assertEqual(receipt.changes,())
        self.assertEqual(session.text,authored)
        with self.assertRaises(ProgramGraphError):
            review_generated_source_edit(h.h.graph,h.base,authored,
                expected_revision=h.h.graph.revision)

    def test_annotations_existing_parameter_and_readable_local(self):
        h=self.harness()
        front,back=h.split()
        front=front.replace('_smi_value_2','computed')
        anchor='    computed = difference('
        self.assertEqual(front.count(anchor),1)
        source=front.replace(anchor,'    x: int\n    computed: int\n'+anchor)+back
        _,receipt=self.review(h.h.graph,source,('caller',))
        self.assertFalse(receipt.changes)

    def test_bare_annotation_with_keyword_rewire_is_undoable(self):
        h=self.harness()
        front,back=h.split()
        anchor='    _smi_value_2 = difference(_smi_value_0, _smi_value_1)'
        self.assertEqual(front.count(anchor),1)
        replacement=('    _smi_value_2: int\n'
                     '    _smi_value_2 = difference(b=_smi_value_0, a=_smi_value_1)')
        source=front.replace(anchor,replacement)+back
        session,receipt=self.review(h.h.graph,source,('caller',))
        self.assertEqual({(c.node_id,c.input_port) for c in receipt.changes},
                         {('z-call','a'),('z-call','b')})
        before=h.h.graph.state
        self.assertTrue(import_independent_source_functions(h.h.graph,session,receipt.functions,
            expected_graph_revision=receipt.graph_revision,
            expected_source_revision=receipt.source_revision,
            expected_source_sha256=receipt.source_sha256))
        self.assertEqual(session.text,source)
        self.assertTrue(h.h.graph.undo(h.h.graph.revision))
        self.assertEqual(h.h.graph.state['edges'],before['edges'])

    def test_noop_constant_conditions_with_siblings(self):
        h=self.harness()
        anchor='    _smi_value_2 = difference('
        source=h.base.replace(anchor,
            '    if True:\n        pass\n    if (2 + 3) == 5:\n'
            '        pass\n    else:\n        pass\n'+anchor)
        _,receipt=self.review(h.h.graph,source,('caller',))
        self.assertFalse(receipt.changes)

    def test_noop_inside_populated_branch_and_rewire(self):
        h=branch_fixtures.BranchLocalReconciliationTests('runTest')
        h.setUp()
        self.addCleanup(h.doCleanups)
        source=h.edited.replace('        _smi_value_4 =',
            '        if False:\n            pass\n        _smi_value_4 =')
        self.assertNotEqual(source,h.edited)
        session,receipt=self.review(h.h.graph,source,('choose',))
        self.assertEqual([(c.node_id,c.input_port) for c in receipt.changes],
                         [('a','left')])
        self.assertEqual(session.text,source)

    def test_dynamic_or_truthy_noop_guard_is_not_erased(self):
        h=self.harness()
        anchor='    _smi_value_2 = difference('
        for condition in ('x', '1', 'unknown()', '(1 / 0) == 0'):
            with self.subTest(condition=condition):
                source=h.base.replace(anchor,
                    f'    if {condition}:\n        pass\n'+anchor)
                original=h.h.graph.state
                with self.assertRaises(ProgramGraphError):
                    self.review(h.h.graph,source,('caller',))
                self.assertEqual(h.h.graph.state,original)

    def test_unsupported_or_new_local_annotation_is_not_erased(self):
        h=self.harness()
        anchor='    _smi_value_2 = difference('
        for line in ('unknown: int', '_smi_value_2: T',
                     '_smi_value_2: dangerous()', '_smi_value_2: int = 5'):
            with self.subTest(line=line):
                source=h.base.replace(anchor,f'    {line}\n'+anchor)
                with self.assertRaises(ProgramGraphError):
                    self.review(h.h.graph,source,('caller',))

    def test_only_noop_in_branch_not_silently_erased(self):
        h=self.harness()
        anchor='    _smi_value_2 = difference('
        source=h.base.replace(anchor,
            '    if True:\n        _smi_value_2: int\n'+anchor)
        with self.assertRaises(ProgramGraphError):
            self.review(h.h.graph,source,('caller',))

    def test_mismatched_graph_revision_refuses(self):
        h=self.harness()
        source=h.base.replace('    _smi_value_2 = difference(',
            '    _smi_value_2: int\n    _smi_value_2 = difference(')
        session,receipt=self.review(h.h.graph,source,('caller',))
        with self.assertRaises(GraphConflict):
            import_independent_source_functions(h.h.graph,session,receipt.functions,
                expected_graph_revision=receipt.graph_revision+1,
                expected_source_revision=receipt.source_revision,
                expected_source_sha256=receipt.source_sha256)

if __name__=='__main__':
    unittest.main()
