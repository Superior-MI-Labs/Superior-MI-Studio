"""All typed integer comparison variants use one compiler/edit proof and graph contract."""
import tempfile
import unittest
from pathlib import Path
from studio_native.program_graph import ProgramGraph, ProgramGraphError, NODE_TEMPLATES, template_ports
from studio_native.python_lowering import (
    INTEGER_COMPARISON_AST, preview_python, review_generated_source_edit,
    import_generated_source_edit, review_independent_source_functions,
    import_independent_source_functions,
)
from studio_native.source_editor import SourceDocumentSession

EXAMPLES = Path(__file__).resolve().parents[1] / 'examples'
SYNTAX = {'python.less_than':'<', 'python.equal_int':'==',
          'python.greater_than':'>', 'python.less_or_equal':'<=',
          'python.greater_or_equal':'>=', 'python.not_equal_int':'!='}


class IntegerComparisonFamilyTests(unittest.TestCase):
    def graph(self, name='qualified-conditional-program'):
        return ProgramGraph.open(EXAMPLES / (name+'.smi-graph'))

    def test_graph_and_compiler_share_full_typed_family(self):
        self.assertEqual(set(INTEGER_COMPARISON_AST),set(SYNTAX))
        for operation in SYNTAX:
            with self.subTest(operation=operation):
                self.assertEqual(NODE_TEMPLATES[operation], NODE_TEMPLATES['python.less_than'])
                self.assertEqual(template_ports(operation)['outputs'][0]['type'], 'py:bool')

    def test_all_six_operations_publish_and_return_correct_results(self):
        cases=((3,5),(5,5),(9,5))
        for operation, token in SYNTAX.items():
            with self.subTest(operation=operation):
                graph=self.graph()
                if operation!='python.less_than':
                    self.assertTrue(graph.edit(graph.revision,'replace_node_operation',
                        node='condition',operation=operation))
                result=preview_python(graph.state)
                self.assertFalse(result.issues)
                self.assertIn(' '+token+' ',result.source)
                scope={}
                exec(compile(result.source,'<trusted-test-generated>','exec'),scope)
                for x,limit in cases:
                    expected = x+1 if eval(f'x {token} limit') else x
                    self.assertEqual(scope['choose'](x,limit),expected)

    def test_generated_edit_all_comparison_variants_and_atomic_undo(self):
        for operation, token in SYNTAX.items():
            with self.subTest(operation=operation):
                graph=self.graph()
                base=preview_python(graph.state).source
                edited=base.replace(' < ', ' '+token+' ')
                review=review_generated_source_edit(graph,base,edited,
                    expected_revision=graph.revision)
                expected_changes=0 if operation=='python.less_than' else 1
                self.assertEqual(len(review.changes),expected_changes)
                if not expected_changes:
                    self.assertFalse(import_generated_source_edit(graph,base,edited,
                        expected_revision=graph.revision))
                    continue
                self.assertEqual(review.changes[0].after,operation)
                before=graph.state
                self.assertTrue(import_generated_source_edit(graph,base,edited,
                    expected_revision=graph.revision))
                self.assertEqual(preview_python(graph.state).source,edited)
                self.assertEqual(before['edges'],graph.state['edges'])
                self.assertEqual(before['layout'],graph.state['layout'])
                self.assertEqual({n['id']:n['ports'] for n in before['nodes']},
                                 {n['id']:n['ports'] for n in graph.state['nodes']})
                self.assertTrue(graph.undo(graph.revision))
                self.assertEqual(preview_python(graph.state).source,base)
                self.assertTrue(graph.redo(graph.revision))
                self.assertEqual(preview_python(graph.state).source,edited)

    def test_structured_flow_comparisons_preserve_branch_semantics(self):
        for name in ('qualified-structured-branch', 'qualified-nested-branches'):
            for operation in SYNTAX:
                with self.subTest(name=name,operation=operation):
                    graph=self.graph(name)
                    baseline=preview_python(graph.state).source
                    edited=baseline.replace(' < ', ' '+SYNTAX[operation]+' ')
                    if edited==baseline:
                        continue
                    self.assertTrue(import_generated_source_edit(graph,baseline,edited,
                        expected_revision=graph.revision))
                    self.assertEqual(preview_python(graph.state).source,edited)

    def test_independent_batch_with_unmodeled_file_and_source_only_trivia(self):
        for operation in ('python.greater_than', 'python.greater_or_equal',
                          'python.not_equal_int','python.less_or_equal'):
            with self.subTest(operation=operation):
                graph=self.graph()
                base=preview_python(graph.state).source
                text=('import math\n\ndef unmodeled():\n    return math.pi\n\n'
                      +base.replace(' < ', ' '+SYNTAX[operation]+' '))
                folder=tempfile.TemporaryDirectory()
                self.addCleanup(folder.cleanup)
                path=Path(folder.name)/'foreign.py';path.write_text(text,encoding='utf-8')
                session=SourceDocumentSession.open(path)
                receipt=review_independent_source_functions(graph,session,('choose',),
                    expected_graph_revision=graph.revision)
                self.assertEqual(receipt.changes[0].after,operation)
                self.assertTrue(import_independent_source_functions(graph,session,receipt.functions,
                    expected_graph_revision=receipt.graph_revision,
                    expected_source_revision=receipt.source_revision,
                    expected_source_sha256=receipt.source_sha256))
                self.assertEqual(session.text,text)

    def test_independent_invalid_source_reports_actual_line_without_guessing(self):
        graph=self.graph()
        base=preview_python(graph.state).source
        broken='import math\n\ndef other(:\n    return 10\n\n'+base
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        path=Path(folder.name)/'unparseable.py'
        path.write_text(broken,encoding='utf-8')
        session=SourceDocumentSession.open(path)
        before=graph.state
        with self.assertRaisesRegex(ProgramGraphError,
                'Independent Python source syntax at line 3, column'):
            review_independent_source_functions(graph,session,('choose',),
                expected_graph_revision=graph.revision)
        self.assertEqual(before,graph.state)
        self.assertEqual(session.text,broken)

    def test_unqualified_and_ambiguous_comparisons_refuse_without_mutation(self):
        graph=self.graph()
        base=preview_python(graph.state).source
        candidates=[
            base.replace(' < ',' is '),
            base.replace(' < ',' in '),
            base.replace('_smi_value_0 < _smi_value_1', '_smi_value_0 < _smi_value_1 < 10'),
            base.replace('_smi_value_0 < _smi_value_1', '_smi_value_1 >= (_smi_value_0 + 1)'),
            base.replace(' < ', ' != ').replace('return _smi_value_5','return 0'),
        ]
        previous=graph.state
        for candidate in candidates:
            with self.subTest(candidate=candidate),self.assertRaises(ProgramGraphError):
                review_generated_source_edit(graph,base,candidate,expected_revision=graph.revision)
            self.assertEqual(graph.state,previous)

if __name__=='__main__':unittest.main()
