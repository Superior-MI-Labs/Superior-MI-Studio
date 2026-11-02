"""Source evidence is exact, function-scoped, and never a second edit authority."""
import ast
import tempfile
from pathlib import Path
import unittest

from studio_native.python_lowering import (
    PythonPreview, SourceEditChange, _independent_change_lines,
    preview_python, review_independent_source_functions,
    import_independent_source_functions,
)
from studio_native.source_editor import SourceDocumentSession
from tests import test_v2102_semantic_input_reconciliation as prior


class SourceReceiptOwnershipTests(unittest.TestCase):
    def session(self, authored):
        temporary=tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        filename=Path(temporary.name)/'source.py'
        filename.write_text(authored,encoding='utf-8')
        return SourceDocumentSession.open(filename)

    def assert_span(self, review, authored, node_id, fragment):
        locations=[(line,start,end_line,end) for _,node,line,start,end_line,end
                   in review.change_spans if node==node_id]
        self.assertEqual(len(locations),1, (node_id,review.change_spans))
        line,start,end_line,end=locations[0]
        self.assertEqual(line,end_line)
        self.assertEqual(authored.splitlines()[line-1][start-1:end-1],fragment)

    def test_occurrence_counts_are_function_local_for_multi_function_review(self):
        # Distinct function regions have independent assignment occurrence
        # indices. The last function must not overwrite earlier counts.
        source=('def alpha():\n'
                '    _smi_value_1 = 1\n'
                '    _smi_slot_1 = _smi_value_1\n'
                '    _smi_slot_1 = _smi_value_1\n'
                '    return _smi_slot_1\n\n'
                'def beta():\n'
                '    _smi_value_2 = 9\n'
                '    return _smi_value_2\n')
        canonical=ast.parse(source)
        authored='# user header\n'+source
        external=ast.parse(authored)
        functions={fn.name:fn for fn in external.body if isinstance(fn,ast.FunctionDef)}
        receipt=PythonPreview(source,(),(('alpha-first',3),('alpha-second',4),('beta-value',8)))
        changes=tuple(SourceEditChange(fn,id,'replace_input',None,None,'value') for fn,id in (
            ('alpha','alpha-first'),('alpha','alpha-second'),('beta','beta-value')))
        lines,spans=_independent_change_lines(functions,canonical,receipt,changes,authored)
        self.assertEqual({id for _,id,_ in lines},{'alpha-first','alpha-second','beta-value'})
        self.assertEqual([line for _,_,line in lines],[4,5,9])
        self.assertEqual([authored.splitlines()[line-1][start-1:end-1]
                          for _,_,line,start,_,end in spans],
                         ['_smi_value_1','_smi_value_1','9'])

    def test_not_and_selection_report_the_exact_changed_input(self):
        h=prior.SemanticRewiringTests('runTest')
        graph=h.make_boolean()
        source=graph.source()
        tree=ast.parse(source)
        nots=[n for n in ast.walk(tree) if isinstance(n,ast.Assign) and
              isinstance(n.value,ast.UnaryOp) and isinstance(n.value.op,ast.Not)]
        select=next(n for n in ast.walk(tree) if isinstance(n,ast.Assign) and
                    isinstance(n.value,ast.IfExp))
        lines=source.splitlines(keepends=True)
        lines[nots[0].lineno-1]=lines[nots[0].lineno-1].replace(
            nots[0].value.operand.id,nots[1].value.operand.id)
        lines[select.lineno-1]=(f'    {select.targets[0].id} = '
            f'{select.value.orelse.id} if {select.value.test.id} else '
            f'{select.value.body.id}\n')
        modified=''.join(lines)
        authored='# comment\n\n'+modified
        session=self.session(authored)
        review=review_independent_source_functions(graph.graph,session,('choose',),
            expected_graph_revision=graph.graph.revision)
        self.assertEqual({(change.node_id,change.input_port) for change in review.changes},
                         {('not1','value'),('choice','true_value'),('choice','false_value')})
        self.assert_span(review,authored,'not1',nots[1].value.operand.id)
        # The two changed inputs are on the same IfExp; source receipts may
        # share the node identity but must select the actual child operands.
        choice_spans=[authored.splitlines()[line-1][start-1:end-1]
                      for _,id,line,start,_,end in review.change_spans if id=='choice']
        self.assertCountEqual(choice_spans,[select.value.orelse.id,select.value.body.id])
        before=graph.graph.state
        self.assertTrue(import_independent_source_functions(graph.graph,session,review.functions,
            expected_graph_revision=review.graph_revision,
            expected_source_revision=review.source_revision,
            expected_source_sha256=review.source_sha256))
        self.assertEqual(session.text,authored)
        self.assertTrue(graph.graph.undo(graph.graph.revision))
        self.assertEqual(graph.graph.state['edges'],before['edges'])

    def test_selection_condition_reports_only_its_expression(self):
        h=prior.SemanticRewiringTests('runTest')
        graph=h.make_boolean()
        source=graph.source()
        tree=ast.parse(source)
        select=next(item for item in ast.walk(tree) if isinstance(item,ast.Assign)
                    and isinstance(item.value,ast.IfExp))
        comparisons=[item for item in ast.walk(tree) if isinstance(item,ast.Assign)
                     and isinstance(item.value,ast.Compare)]
        self.assertEqual(len(comparisons),2)
        original=select.value.test.id
        alternative=next(item.targets[0].id for item in comparisons
                         if item.targets[0].id!=original)
        lines=source.splitlines(keepends=True)
        lines[select.lineno-1]=lines[select.lineno-1].replace(
            f' if {original} else ',f' if {alternative} else ')
        authored='# é unicode comment\n'+''.join(lines)
        session=self.session(authored)
        review=review_independent_source_functions(graph.graph,session,('choose',),
            expected_graph_revision=graph.graph.revision)
        self.assertEqual([(c.node_id,c.input_port) for c in review.changes],
                         [('choice','condition')])
        self.assert_span(review,authored,'choice',alternative)

    def test_arithmetic_right_operand_is_not_whole_statement(self):
        # Use canonical ProgramGraph operations and unique existing values.
        from tests.test_v2102_semantic_input_reconciliation import Harness
        graph=Harness(return_type='py:int')
        graph.parameter('x')
        graph.parameter('y')
        graph.node('add','python.add')
        graph.node('mul','python.multiply')
        graph.node('ret','python.return')
        for src,target,port in (('x','add','left'),('y','add','right'),
                                ('add','mul','left'),('x','mul','right'),
                                ('mul','ret','value')):
            graph.wire(src,target,port)
        # Keep x alive as add's input and y alive as the other input.
        source=graph.source()
        tree=ast.parse(source)
        multiply=next(item for item in ast.walk(tree) if isinstance(item,ast.Assign)
                      and isinstance(item.value,ast.BinOp)
                      and isinstance(item.value.op,ast.Mult))
        x_assigned=next(item.targets[0].id for item in ast.walk(tree)
                        if isinstance(item,ast.Assign) and isinstance(item.value,ast.Name)
                        and item.value.id=='x')
        y_assigned=next(item.targets[0].id for item in ast.walk(tree)
                        if isinstance(item,ast.Assign) and isinstance(item.value,ast.Name)
                        and item.value.id=='y')
        lines=source.splitlines(keepends=True)
        lines[multiply.lineno-1]=lines[multiply.lineno-1].replace(
            f'* {x_assigned}',f'* {y_assigned}')
        authored='β = 5\n'+''.join(lines)
        session=self.session(authored)
        review=review_independent_source_functions(graph.graph,session,('choose',),
            expected_graph_revision=graph.graph.revision)
        self.assertEqual([(c.node_id,c.input_port) for c in review.changes],
                         [('mul','right')])
        self.assert_span(review,authored,'mul',y_assigned)

    def test_structured_return_receipt_selects_value_only(self):
        h=prior.SemanticRewiringTests('runTest')
        graph=h.make_flow()
        source=graph.source()
        returns=[n for n in ast.walk(ast.parse(source)) if isinstance(n,ast.Return)]
        self.assertEqual(len(returns),2)
        first,second=returns
        line=source.splitlines()[first.lineno-1]
        edited=source.replace(line,' '*(first.col_offset)+'return '+second.value.id)
        authored='import os\n\n'+edited
        session=self.session(authored)
        review=review_independent_source_functions(graph.graph,session,('choose',),
            expected_graph_revision=graph.graph.revision)
        self.assertEqual([(c.node_id,c.input_port) for c in review.changes],
                         [('true_ret','value')])
        self.assert_span(review,authored,'true_ret',second.value.id)

    def test_no_fabricated_spans_for_ambiguous_occurrence(self):
        source=('def alpha():\n'
                '    _smi_slot_1 = 1\n'
                '    return _smi_slot_1\n')
        altered=source.replace('    return','    _smi_slot_1 = 2\n    return')
        tree=ast.parse(source)
        external={n.name:n for n in ast.parse(altered).body}
        preview=PythonPreview(source,(),(('write',2),))
        lines,spans=_independent_change_lines(external,tree,preview,
            (SourceEditChange('alpha','write','replace_input',None,None,'value'),),altered)
        self.assertEqual(lines,())
        self.assertEqual(spans,())


if __name__ == '__main__':
    unittest.main()
