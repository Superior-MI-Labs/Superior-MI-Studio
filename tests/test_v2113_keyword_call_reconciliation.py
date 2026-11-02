"""Keyword-call syntax stays source-owned; only compiler-proven existing wires import."""
import ast
import tempfile
import unittest
from pathlib import Path

from studio_native.program_graph import ProgramGraphError, GraphConflict, template_ports
from studio_native.python_lowering import (
    preview_python, review_generated_source_edit,
    review_independent_source_functions, import_independent_source_functions)
from studio_native.source_editor import SourceDocumentSession
from tests.test_v2102_semantic_input_reconciliation import Harness


class KeywordCallReconciliationTests(unittest.TestCase):
    def setUp(self):
        h=Harness(name='caller', return_type='py:int')
        for name in ('x','y'):
            h.parameter(name)
        h.edit('add_function',id='callee',name='difference')
        h.edit('set_return_type',function='callee',type='py:int')
        for name in ('a','b'):
            h.edit('add_parameter',function='callee',id='p-'+name,name=name,type='py:int')
            self.callee_node(h,name,'python.parameter',{'parameter_id':'p-'+name})
        for node,operation in [('cal-add','python.subtract'),('cal-ret','python.return')]:
            self.callee_node(h,node,operation)
        for src,out,dst,port in [('a','value','cal-add','left'),('b','value','cal-add','right'),
                                  ('cal-add','result','cal-ret','value')]:
            h.edit('connect',source=src,source_port=f'{src}-{out}',
                   target=dst,target_port=f'{dst}-{port}')
        h.edit('add_node',id='z-call',function='fn',operation='python.call',
               inputs=[{'id':'z-call-a','name':'a','type':'py:int'},
                       {'id':'z-call-b','name':'b','type':'py:int'}],
               outputs=[{'id':'z-call-result','name':'result','type':'py:int','required':False}],
               properties={'callee_id':'callee'})
        for node,operation in [('z-sum','python.add'),('zz-final','python.add'),('zz-return','python.return')]:
            h.node(node,operation)
        for src,dst,port in [('x','z-call','a'),('y','z-call','b'),('x','z-sum','left'),
                              ('y','z-sum','right'),('z-call','zz-final','left'),
                              ('z-sum','zz-final','right'),('zz-final','zz-return','value')]:
            h.wire(src,dst,port)
        self.h=h
        self.base=h.source()
        self.original='difference(_smi_value_0, _smi_value_1)'
        self.assertIn(self.original,self.base)
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'developer.py'

    def callee_node(self,h,ident,operation,properties=None):
        ports=template_ports(operation)
        for side in ports:
            for port in ports[side]:
                port['id']=ident+'-'+port['name']
        h.edit('add_node',id=ident,function='callee',operation=operation,
               inputs=ports['inputs'],outputs=ports['outputs'],properties=properties or {})

    def source(self,expr):
        authored='import os\n# source-only heading\n'+self.base.replace(self.original,expr)+\
                 '\n# source-only footer\n'
        self.assertNotEqual(authored,'import os\n# source-only heading\n'+self.base+'\n# source-only footer\n')
        self.path.write_text(authored,encoding='utf-8')
        return SourceDocumentSession.open(self.path),authored

    def review(self,expr,functions=('caller',)):
        session,text=self.source(expr)
        receipt=review_independent_source_functions(self.h.graph,session,functions,
                                                    expected_graph_revision=self.h.graph.revision)
        return session,text,receipt

    def test_named_arguments_in_reverse_order_import_two_wires_and_preserve_source(self):
        session,text,receipt=self.review('difference(b=_smi_value_0, a=_smi_value_1)')
        self.assertEqual([(c.node_id,c.input_port) for c in receipt.changes],
                         [('z-call','a'),('z-call','b')])
        self.assertEqual(len(receipt.change_spans),2)
        locations={text.splitlines()[line-1][start-1:end-1]
                   for _,_,line,start,last,end in receipt.change_spans if line==last}
        self.assertEqual(locations,{'_smi_value_0','_smi_value_1'})
        before=self.h.graph.state
        before_symbols={}
        exec(self.base,before_symbols)
        authored_symbols={}
        exec(text,authored_symbols)
        self.assertNotEqual(before_symbols['caller'](4,7),authored_symbols['caller'](4,7))
        self.assertTrue(import_independent_source_functions(self.h.graph,session,receipt.functions,
            expected_graph_revision=receipt.graph_revision,
            expected_source_revision=receipt.source_revision,
            expected_source_sha256=receipt.source_sha256))
        self.assertEqual(session.text,text)
        self.assertEqual(self.path.read_text(),text)
        self.assertIn('difference(_smi_value_1, _smi_value_0)',self.h.source())
        after_symbols={}
        exec(self.h.source(),after_symbols)
        self.assertEqual(after_symbols['caller'](4,7),authored_symbols['caller'](4,7))
        self.assertTrue(self.h.graph.undo(self.h.graph.revision))
        self.assertEqual(self.h.graph.state['edges'],before['edges'])

    def test_mixed_positional_and_keyword_input_import(self):
        session,text,receipt=self.review('difference(_smi_value_1, b=_smi_value_0)')
        self.assertEqual({c.input_port for c in receipt.changes},{'a','b'})

    def test_unchanged_keyword_spelling_is_no_graph_change(self):
        session,text,receipt=self.review('difference(a=_smi_value_0, b=_smi_value_1)')
        self.assertEqual(receipt.changes,())
        self.assertEqual(session.text,text)

    def test_generated_source_dialog_does_not_accept_keyword_rewriting(self):
        candidate=self.base.replace(self.original,'difference(b=_smi_value_0, a=_smi_value_1)')
        with self.assertRaises(ProgramGraphError):
            review_generated_source_edit(self.h.graph,self.base,candidate,
                                         expected_revision=self.h.graph.revision)

    def test_unqualified_keyword_forms_refuse_atomically(self):
        bad=[
            'difference(a=_smi_value_1, a=_smi_value_0)',
            'difference(a=_smi_value_0)',
            'difference(z=_smi_value_0, b=_smi_value_1)',
            'difference(a=_smi_value_0, b=42)',
            'difference(*(_smi_value_0,), b=_smi_value_1)',
            'difference(**mapping)',
            'difference(a=probe(), b=_smi_value_1)',
            'difference(a=_smi_value_0, b=_smi_value_1, **mapping)',
        ]
        original=self.h.graph.state
        for expression in bad:
            with self.subTest(expression=expression):
                session,_=self.source(expression)
                with self.assertRaises(ProgramGraphError):
                    review_independent_source_functions(self.h.graph,session,('caller',),
                                                        expected_graph_revision=self.h.graph.revision)
                self.assertEqual(self.h.graph.state,original)

    def test_changed_unselected_callee_is_not_canonicalized(self):
        session,text=self.source('difference(a=_smi_value_1, b=_smi_value_0)')
        text=text.replace('return _smi_value_2\n','return _smi_value_0\n')
        self.path.write_text(text,encoding='utf-8')
        session=SourceDocumentSession.open(self.path)
        with self.assertRaises(ProgramGraphError):
            review_independent_source_functions(self.h.graph,session,('caller',),
                                                expected_graph_revision=self.h.graph.revision)

    def test_selected_modified_callee_remains_full_compiler_qualified(self):
        session,text,receipt=self.review('difference(b=_smi_value_0, a=_smi_value_1)',
                                        ('caller','difference'))
        self.assertEqual({c.input_port for c in receipt.changes},{'a','b'})

    def test_execution_ordered_keyword_call_uses_same_graph_input_proof(self):
        # Reuse the existing native execution-call fixture rather than adding
        # another execution graph implementation just for keyword syntax.
        from tests.test_v2105_execution_call_argument_reconciliation import (
            ExecutionCallArgumentReconciliationTests,
        )
        fixture=ExecutionCallArgumentReconciliationTests(methodName='test_independent_source_keeps_other_functions_and_text_unchanged')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        candidate=fixture.base.replace('guarded(_smi_value_0)',
                                       'guarded(x=_smi_value_1)')
        self.assertNotEqual(candidate,fixture.base)
        session=fixture.session(candidate)
        receipt=review_independent_source_functions(fixture.h.graph,session,('invoke',),
            expected_graph_revision=fixture.h.graph.revision)
        self.assertEqual([(c.node_id,c.input_port) for c in receipt.changes],
                         [('ordered','x')])
        self.assertTrue(import_independent_source_functions(fixture.h.graph,session,receipt.functions,
            expected_graph_revision=receipt.graph_revision,
            expected_source_revision=receipt.source_revision,
            expected_source_sha256=receipt.source_sha256))
        self.assertEqual(session.text,candidate)
        self.assertIn('guarded(_smi_value_1)',preview_python(fixture.h.graph.state).source)

    def test_shadowed_unselected_callee_refuses_keyword_canonicalization(self):
        session,text=self.source('difference(a=_smi_value_1, b=_smi_value_0)')
        shadowed=text+'difference = lambda a, b: 999\n'
        self.path.write_text(shadowed,encoding='utf-8')
        session=SourceDocumentSession.open(self.path)
        with self.assertRaises(ProgramGraphError):
            review_independent_source_functions(self.h.graph,session,('caller',),
                                                expected_graph_revision=self.h.graph.revision)

    def test_keyword_call_no_graph_mutation_if_other_selected_function_invalid(self):
        session,text=self.source('difference(a=_smi_value_1, b=_smi_value_0)')
        self.path.write_text(text.replace('return _smi_value_2\n',
                                          'return object()\n'),encoding='utf-8')
        session=SourceDocumentSession.open(self.path)
        baseline=self.h.graph.state
        with self.assertRaises(ProgramGraphError):
            review_independent_source_functions(self.h.graph,session,('caller','difference'),
                                                expected_graph_revision=self.h.graph.revision)
        self.assertEqual(baseline,self.h.graph.state)

    def test_stale_source_revision_refuses_import(self):
        session,text,receipt=self.review('difference(b=_smi_value_0, a=_smi_value_1)')
        session.update(text+'\n# revision changed\n')
        with self.assertRaises(GraphConflict):
            import_independent_source_functions(self.h.graph,session,receipt.functions,
                expected_graph_revision=receipt.graph_revision,
                expected_source_revision=receipt.source_revision,
                expected_source_sha256=receipt.source_sha256)

if __name__=='__main__':
    unittest.main()
