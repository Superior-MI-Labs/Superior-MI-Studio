"""Multiple readable locals: match only uniquely proven pure value identities."""
import tempfile
import unittest
from pathlib import Path
from studio_native.program_graph import ProgramGraphError
from studio_native.python_lowering import (preview_python, review_independent_source_functions,
    import_independent_source_functions, review_generated_source_edit)
from studio_native.source_editor import SourceDocumentSession
from tests.test_v2102_semantic_input_reconciliation import Harness


class MultipleSourceAliases(unittest.TestCase):
    def setUp(self):
        self.h=Harness(name='compose',return_type='py:int')
        for name in ('x','y'):self.h.parameter(name)
        for name,operation in [('a','python.add'),('b','python.multiply'),
                               ('total','python.add'),('ret','python.return')]:
            self.h.node(name,operation)
        for source,target,port in [('x','a','left'),('y','a','right'),
            ('x','b','left'),('y','b','right'),('a','total','left'),
            ('b','total','right'),('total','ret','value')]:
            self.h.wire(source,target,port)
        self.base=self.h.source()
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'user.py'

    def author(self,text):
        self.path.write_text(text,encoding='utf-8')
        return SourceDocumentSession.open(self.path)

    def renamed(self,*,change_operator=True):
        source=self.base
        # Rename several binding owners, including two expressions that are
        # independent and can be reordered safely.
        for old,new in [('_smi_value_0','left_value'),('_smi_value_1','right_value'),
                        ('_smi_value_2','addition'),('_smi_value_3','product')]:
            source=source.replace(old,new)
        one='    addition = left_value + right_value\n    product = left_value * right_value'
        two='    product = left_value * right_value\n    addition = left_value + right_value'
        self.assertIn(one,source)
        source=source.replace(one,two)
        if change_operator:
            source=source.replace('    _smi_value_4 = addition + product',
                                  '    _smi_value_4 = addition - product')
        return source

    def test_multiple_uniquely_witnessed_renames_with_reorder_and_operator_edit(self):
        text='import math\n# unrelated source\n'+self.renamed()
        before=self.h.graph.state
        session=self.author(text)
        receipt=review_independent_source_functions(self.h.graph,session,('compose',),
            expected_graph_revision=self.h.graph.revision)
        self.assertEqual([(c.node_id,c.action) for c in receipt.changes],[('total','replace_node_operation')])
        self.assertEqual(before,self.h.graph.state)
        self.assertTrue(import_independent_source_functions(self.h.graph,session,('compose',),
            expected_graph_revision=receipt.graph_revision,
            expected_source_revision=receipt.source_revision,
            expected_source_sha256=receipt.source_sha256))
        self.assertEqual(session.text,text)
        self.assertEqual(self.path.read_text(encoding='utf-8'),text)
        self.assertIn(' - ',preview_python(self.h.graph.state).source)
        self.assertTrue(self.h.graph.undo(self.h.graph.revision))
        self.assertEqual(self.h.graph.state['edges'],before['edges'])
        with self.assertRaises(ProgramGraphError):
            review_generated_source_edit(self.h.graph,self.base,text,
                expected_revision=self.h.graph.revision)

    def test_unchanged_multiple_renames_do_not_modify_graph(self):
        text=self.renamed(change_operator=False)
        session=self.author(text)
        receipt=review_independent_source_functions(self.h.graph,session,('compose',),
            expected_graph_revision=self.h.graph.revision)
        self.assertEqual(receipt.changes,())

    def test_ambiguous_same_pure_producers_still_refused(self):
        # Duplicate pure expressions cannot uniquely identify renamed values.
        ambiguous=self.renamed(change_operator=False).replace(
            'product = left_value * right_value','product = left_value + right_value')
        original=self.h.graph.state
        with self.assertRaises(ProgramGraphError):
            review_independent_source_functions(self.h.graph,self.author(ambiguous),('compose',),
                expected_graph_revision=self.h.graph.revision)
        self.assertEqual(original,self.h.graph.state)

    def test_bad_collision_and_unbound_alias_refused(self):
        for text in [self.renamed().replace('addition','left_value'),
                     self.renamed().replace('addition - product','unknown - product'),
                     self.renamed().replace('left_value','_smi_value_9')]:
            with self.subTest(text=text[-90:]),self.assertRaises(ProgramGraphError):
                review_independent_source_functions(self.h.graph,self.author(text),('compose',),
                    expected_graph_revision=self.h.graph.revision)

    def test_branch_local_multiple_unique_aliases_with_wire_import(self):
        from tests.test_v2104_nested_roundtrip import BranchLocalReconciliationTests
        case=BranchLocalReconciliationTests('runTest')
        case.setUp()
        self.addCleanup(case.doCleanups)
        candidate=case.edited
        for old,new in [('_smi_value_0','left_input'),
                        ('_smi_value_1','right_input'),
                        ('_smi_value_2','condition_value')]:
            candidate=candidate.replace(old,new)
        old=case.h.graph.state
        session=self.author(candidate)
        receipt=review_independent_source_functions(case.h.graph,session,('choose',),
            expected_graph_revision=case.h.graph.revision)
        self.assertEqual([(c.node_id,c.action,c.input_port) for c in receipt.changes],
                         [('a','replace_input','left')])
        self.assertTrue(import_independent_source_functions(case.h.graph,session,('choose',),
            expected_graph_revision=receipt.graph_revision,
            expected_source_revision=receipt.source_revision,
            expected_source_sha256=receipt.source_sha256))
        self.assertEqual(session.text,candidate)
        self.assertTrue(case.h.graph.undo(case.h.graph.revision))
        self.assertEqual(case.h.graph.state['edges'],old['edges'])

    def test_stale_external_change_prevents_commit(self):
        text=self.renamed()
        session=self.author(text)
        receipt=review_independent_source_functions(self.h.graph,session,('compose',),
            expected_graph_revision=self.h.graph.revision)
        before=self.h.graph.state
        self.path.write_text(text+'\n# external\n',encoding='utf-8')
        with self.assertRaises(Exception):
            import_independent_source_functions(self.h.graph,session,('compose',),
                expected_graph_revision=receipt.graph_revision,
                expected_source_revision=receipt.source_revision,
                expected_source_sha256=receipt.source_sha256)
        self.assertEqual(before,self.h.graph.state)


if __name__=='__main__':unittest.main()
