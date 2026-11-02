"""Original-source Python syntax admitted only by the graph-owned compiler proof."""
import tempfile
import unittest
from pathlib import Path
from studio_native.program_graph import ProgramGraphError
from studio_native.python_lowering import (
    preview_python, review_independent_source_functions,
    import_independent_source_functions, review_generated_source_edit)
from studio_native.source_editor import SourceDocumentSession
from tests.test_v2114_independent_local_correspondence import IndependentLocalCorrespondenceTests
from tests.test_v2104_nested_roundtrip import BranchLocalReconciliationTests


class IndependentSourceSyntaxTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'author.py'

    def session(self,text):
        self.path.write_text(text,encoding='utf-8')
        return SourceDocumentSession.open(self.path)

    def test_annotated_local_keyword_rewire_preserves_source_and_undo(self):
        harness=IndependentLocalCorrespondenceTests('runTest')
        harness.setUp()
        self.addCleanup(harness.doCleanups)
        front,back=harness.split()
        before='    _smi_value_2 = difference(_smi_value_0, _smi_value_1)'
        after='    _smi_value_2: int = difference(b=_smi_value_0, a=_smi_value_1)'
        self.assertEqual(front.count(before),1)
        text='import math\n'+front.replace(before,after)+back+'\n# untouched\n'
        session=self.session(text)
        state=harness.h.graph.state
        receipt=review_independent_source_functions(harness.h.graph,session,('caller',),
            expected_graph_revision=harness.h.graph.revision)
        self.assertEqual({(c.node_id,c.input_port) for c in receipt.changes},
                         {('z-call','a'),('z-call','b')})
        self.assertEqual(len(receipt.change_spans),2)
        self.assertTrue(all(text.splitlines()[line-1][col-1:end_col-1].startswith('_smi_value_')
                   for _,_,line,col,end_line,end_col in receipt.change_spans
                   if line==end_line))
        self.assertTrue(import_independent_source_functions(harness.h.graph,session,('caller',),
            expected_graph_revision=receipt.graph_revision,
            expected_source_revision=receipt.source_revision,
            expected_source_sha256=receipt.source_sha256))
        self.assertEqual(session.text,text)
        self.assertEqual(self.path.read_text(),text)
        self.assertTrue(harness.h.graph.undo(harness.h.graph.revision))
        self.assertEqual(harness.h.graph.state['edges'],state['edges'])
        with self.assertRaises(ProgramGraphError):
            review_generated_source_edit(harness.h.graph,harness.base,text,
                expected_revision=harness.h.graph.revision)

    def test_branch_pass_with_siblings_remains_source_owned(self):
        h=BranchLocalReconciliationTests('runTest')
        h.setUp()
        self.addCleanup(h.doCleanups)
        assert h.base.count('    if _smi_value_2:')==1
        text=h.base.replace('    if _smi_value_2:',
                             '    if _smi_value_2:\n        pass')
        self.assertNotEqual(text,h.base)
        session=self.session(text)
        receipt=review_independent_source_functions(h.h.graph,session,('choose',),
            expected_graph_revision=h.h.graph.revision)
        self.assertEqual(receipt.changes,())
        self.assertEqual(session.text,text)
        with self.assertRaises(ProgramGraphError):
            review_generated_source_edit(h.h.graph,h.base,text,
                expected_revision=h.h.graph.revision)

    def test_branch_with_pass_and_rewire_keeps_semantics_and_undo(self):
        h=BranchLocalReconciliationTests('runTest')
        h.setUp()
        self.addCleanup(h.doCleanups)
        text=h.edited.replace('    if _smi_value_2:',
                               '    if _smi_value_2:\n        pass')
        session=self.session(text)
        original=h.h.graph.state
        receipt=review_independent_source_functions(h.h.graph,session,('choose',),
            expected_graph_revision=h.h.graph.revision)
        self.assertEqual([(c.node_id,c.input_port) for c in receipt.changes],[('a','left')])
        self.assertTrue(import_independent_source_functions(h.h.graph,session,('choose',),
            expected_graph_revision=receipt.graph_revision,
            expected_source_revision=receipt.source_revision,
            expected_source_sha256=receipt.source_sha256))
        self.assertEqual(session.text,text)
        self.assertTrue(h.h.graph.undo(h.h.graph.revision))
        self.assertEqual(h.h.graph.state['edges'],original['edges'])

    def test_annotations_with_effectful_or_complex_forms_refuse(self):
        h=IndependentLocalCorrespondenceTests('runTest')
        h.setUp()
        self.addCleanup(h.doCleanups)
        base=h.base
        state=h.h.graph.state
        anchor='    _smi_value_2 = difference('
        self.assertIn(anchor,base)
        for replacement in ('    _smi_value_2: do_side_effect() = difference(',
                            '    _smi_value_2: float = difference(',
                            '    _smi_value_2: list[int] = difference(',
                            '    obj.value: int = difference('):
            with self.subTest(replacement=replacement):
                text=base.replace(anchor,replacement,1)
                with self.assertRaises(ProgramGraphError):
                    review_independent_source_functions(h.h.graph,self.session(text),('caller',),
                        expected_graph_revision=h.h.graph.revision)
                self.assertEqual(h.h.graph.state,state)

    def test_empty_branch_and_substantive_statement_refuse(self):
        h=BranchLocalReconciliationTests('runTest')
        h.setUp()
        self.addCleanup(h.doCleanups)
        base=h.base
        for text in (base.replace('    if _smi_value_2:',
                                  '    if _smi_value_2:\n        print("effect")'),
                     base.replace('        _smi_value_3 = _smi_value_0 + _smi_value_1',
                                  '        pass')):
            with self.subTest(text=text[:70]):
                with self.assertRaises(ProgramGraphError):
                    review_independent_source_functions(h.h.graph,self.session(text),('choose',),
                        expected_graph_revision=h.h.graph.revision)

if __name__=='__main__':
    unittest.main()
