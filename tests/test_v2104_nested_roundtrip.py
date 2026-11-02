"""Branch-local source reconciliation uses the actual ProgramGraph compiler."""
import tempfile
import unittest
from pathlib import Path

from studio_native.program_graph import ProgramGraphError
from studio_native.python_lowering import (
    preview_python, review_generated_source_edit,
    review_independent_source_functions, import_independent_source_functions,
)
from studio_native.source_editor import SourceDocumentSession
from tests.test_v2102_semantic_input_reconciliation import Harness


class BranchLocalReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness(return_type='py:int')
        for name in ('x','y'):
            self.h.parameter(name)
        for name,operation in (
            ('entry','python.entry'),('less','python.less_than'),
            ('branch','python.branch'),('a','python.add'),('b','python.add'),
            ('total','python.add'),('true','python.return_flow'),
            ('false','python.return_flow')):
            self.h.node(name,operation)
        for source,target,port in (
            ('x','less','left'),('y','less','right'),('less','branch','condition'),
            ('x','a','left'),('y','a','right'),
            ('x','b','left'),('y','b','right'),
            ('a','total','left'),('b','total','right'),
            ('total','true','value'),('y','false','value')):
            self.h.wire(source,target,port)
        self.h.wire('entry','branch','exec','then','control')
        self.h.wire('branch','true','exec','true','control')
        self.h.wire('branch','false','exec','false','control')
        self.base = self.h.source()
        self.before = ('        _smi_value_3 = _smi_value_0 + _smi_value_1\n'
                       '        _smi_value_4 = _smi_value_0 + _smi_value_1')
        self.after = ('        _smi_value_4 = _smi_value_0 + _smi_value_1\n'
                      '        _smi_value_3 = _smi_value_4 + _smi_value_1')
        self.assertEqual(self.base.count(self.before),1)
        self.edited = self.base.replace(self.before,self.after)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'user.py'

    def session(self,text):
        self.path.write_text(text,encoding='utf-8')
        return SourceDocumentSession.open(self.path)

    def test_source_branch_rewire_and_reorder_is_atomic(self):
        text='import math\n\n# user source owner\n'+self.edited+'\n# footer\n'
        session=self.session(text)
        old=self.h.graph.state
        review=review_independent_source_functions(
            self.h.graph,session,('choose',),
            expected_graph_revision=self.h.graph.revision)
        self.assertEqual([(c.node_id,c.action,c.input_port) for c in review.changes],
                         [('a','replace_input','left')])
        self.assertEqual(old,self.h.graph.state)
        self.assertTrue(import_independent_source_functions(
            self.h.graph,session,('choose',),
            expected_graph_revision=review.graph_revision,
            expected_source_revision=review.source_revision,
            expected_source_sha256=review.source_sha256))
        self.assertEqual(session.text,text)
        self.assertEqual(self.path.read_text(encoding='utf-8'),text)
        compiled=preview_python(self.h.graph.state)
        self.assertIsNotNone(compiled.source,compiled.issues)
        self.assertIn('if _smi_value_2:',compiled.source)
        self.assertIn('else:\n        return _smi_value_1',compiled.source)
        self.assertTrue(self.h.graph.undo(self.h.graph.revision))
        self.assertEqual(self.h.graph.state['edges'],old['edges'])
        self.assertTrue(self.h.graph.redo(self.h.graph.revision))

    def test_generated_source_remains_strict_about_branch_reorder(self):
        with self.assertRaises(ProgramGraphError):
            review_generated_source_edit(self.h.graph,self.base,self.edited,
                                         expected_revision=self.h.graph.revision)

    def test_forward_reference_inside_branch_is_refused_without_mutation(self):
        invalid = self.base.replace(
            '        _smi_value_3 = _smi_value_0 + _smi_value_1',
            '        _smi_value_3 = _smi_value_4 + _smi_value_1')
        self.assertNotEqual(invalid,self.base)
        original=self.h.graph.state
        with self.assertRaises(ProgramGraphError):
            review_independent_source_functions(self.h.graph,self.session(invalid),('choose',),
                expected_graph_revision=self.h.graph.revision)
        self.assertEqual(self.h.graph.state,original)

if __name__=='__main__':
    unittest.main()
