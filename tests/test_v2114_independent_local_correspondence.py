"""Bounded independent-source trivia / local aliases; graph compiler remains authority."""
import ast
import tempfile
import unittest
from pathlib import Path

from studio_native.program_graph import ProgramGraphError
from studio_native.python_lowering import (
    preview_python, review_independent_source_functions,
    import_independent_source_functions, review_generated_source_edit)
from studio_native.source_editor import SourceDocumentSession
from tests import test_v2113_keyword_call_reconciliation as keyword_fixtures


class IndependentLocalCorrespondenceTests(unittest.TestCase):
    def setUp(self):
        fixture=keyword_fixtures.KeywordCallReconciliationTests('test_unchanged_keyword_spelling_is_no_graph_change')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.h=fixture.h
        self.base=fixture.base
        self.directory=tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path=Path(self.directory.name)/'author.py'

    def source(self, candidate):
        self.path.write_text(candidate, encoding='utf-8')
        return SourceDocumentSession.open(self.path)

    def split(self):
        front,back=self.base.split('\ndef difference(',1)
        return front,'\ndef difference('+back

    def review(self, source, functions=('caller',)):
        session=self.source(source)
        return session,review_independent_source_functions(
            self.h.graph,session,functions,
            expected_graph_revision=self.h.graph.revision)

    def test_human_readable_local_name_with_keyword_argument_rewires_atomically(self):
        front,back=self.split()
        front=front.replace('_smi_value_2','call_result')
        front=front.replace('difference(_smi_value_0, _smi_value_1)',
                            'difference(b=_smi_value_0, a=_smi_value_1)')
        source='import math\n'+front+'\n'+back
        session,receipt=self.review(source)
        self.assertEqual({(c.node_id,c.input_port) for c in receipt.changes},
                         {('z-call','a'),('z-call','b')})
        before=self.h.graph.state
        self.assertTrue(import_independent_source_functions(
            self.h.graph,session,receipt.functions,
            expected_graph_revision=receipt.graph_revision,
            expected_source_revision=receipt.source_revision,
            expected_source_sha256=receipt.source_sha256))
        self.assertEqual(session.text,source)
        self.assertEqual(self.path.read_text(encoding='utf-8'),source)
        self.assertTrue(self.h.graph.undo(self.h.graph.revision))
        self.assertEqual({k:v for k,v in self.h.graph.state.items() if k != 'revision'},
                         {k:v for k,v in before.items() if k != 'revision'})

    def test_source_owned_docstring_pass_and_local_alpha_rename_are_not_graph_edits(self):
        front,back=self.split()
        front=front.replace('def caller(x, y):\n',
                            'def caller(x, y):\n    """Visible only in source."""\n    pass\n')
        front=front.replace('_smi_value_2','call_result')
        front+='    pass\n'  # Even unreachable no-op syntax remains source owned.
        source=front+back
        session,receipt=self.review(source)
        self.assertEqual(receipt.changes,())
        self.assertEqual(session.text,source)
        self.assertIn('"""Visible only in source."""',source)
        with self.assertRaises(ProgramGraphError):
            review_generated_source_edit(self.h.graph,self.base,source,
                expected_revision=self.h.graph.revision)

    def test_each_selected_function_owns_its_local_aliases(self):
        source=self.base.replace('    _smi_value_2 = difference(',
                                 '    difference_result = difference(')
        source=source.replace('    _smi_value_4 = _smi_value_2 +',
                              '    _smi_value_4 = difference_result +')
        source=source.replace('    _smi_value_2 = _smi_value_0 - _smi_value_1',
                              '    delta = _smi_value_0 - _smi_value_1')
        source=source.replace('    return _smi_value_2\n','    return delta\n')
        session,receipt=self.review(source,('caller','difference'))
        self.assertEqual(receipt.changes,())
        self.assertEqual(receipt.functions,('caller','difference'))

    def test_renaming_to_parameter_or_callee_is_refused_without_mutation(self):
        front,back=self.split()
        original=self.h.graph.state
        for alias in ('x','difference','_smi_value_3'):
            with self.subTest(alias=alias):
                candidate=front.replace('_smi_value_2',alias)+back
                with self.assertRaises(ProgramGraphError):
                    self.review(candidate)
                self.assertEqual(self.h.graph.state,original)

    def test_repeated_or_conflicting_assignments_are_not_guessed(self):
        front,back=self.split()
        duplicate=front.replace('    _smi_value_2 = difference(',
                                '    _smi_value_3 = difference(')+back
        with self.assertRaises(ProgramGraphError):
            self.review(duplicate)
        candidate=front.replace('_smi_value_2','net')
        candidate=candidate.replace('    _smi_value_3 =',
                                    '    net =')+back
        with self.assertRaises(ProgramGraphError):
            self.review(candidate)

    def test_nonleading_string_expression_not_ignored(self):
        front,back=self.split()
        candidate=front.replace('    _smi_value_1 = y\n',
                                '    _smi_value_1 = y\n    "Not a docstring"\n')+back
        with self.assertRaises(ProgramGraphError):
            self.review(candidate)

    def test_real_statement_or_scope_change_still_refused(self):
        front,back=self.split()
        cases=[front.replace('    _smi_value_2 =', '    pass\n    _smi_value_2 =').replace(
                      'difference(_smi_value_0, _smi_value_1)', '42')+back,
               front.replace('    _smi_value_2 =',
                             '    _smi_value_2 = (lambda: 5)()\n    _smi_value_2 =')+back,
               front.replace('    _smi_value_2 =',
                             '    global call_result\n    call_result = 1\n    _smi_value_2 =')+back]
        for candidate in cases:
            with self.subTest(candidate=candidate[:90]):
                with self.assertRaises(ProgramGraphError):
                    self.review(candidate)

    def test_revision_conflict_still_refuses_commit(self):
        front,back=self.split()
        source=front.replace('_smi_value_2','call_result').replace(
            'difference(_smi_value_0, _smi_value_1)',
            'difference(b=_smi_value_0, a=_smi_value_1)')+back
        session,receipt=self.review(source)
        before=self.h.graph.state
        # Another legitimate source revision invalidates the preflight receipt.
        self.path.write_text(source+'\n# external edit\n',encoding='utf-8')
        with self.assertRaises(Exception):
            import_independent_source_functions(
                self.h.graph,session,receipt.functions,
                expected_graph_revision=receipt.graph_revision,
                expected_source_revision=receipt.source_revision,
                expected_source_sha256=receipt.source_sha256)
        self.assertEqual(self.h.graph.state,before)


if __name__=='__main__':
    unittest.main()
