import ast
import tempfile
import unittest
from pathlib import Path

from studio_native.python_graph import PythonDocument, SourceError
from studio_native.python_edit import change_literal, add_constant_operand, apply_proposal


CODE='''tax: int = 2

def outer(base: int) -> int:
    increment = 10
    def inner(value: int) -> int:
        result = base + increment + value + tax
        return result
    return inner(5)

def inc(a: int) -> int:
    total = a + 10
    return total
'''


class PythonGraphTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'sample.py'
        self.path.write_text(CODE, encoding='utf-8')

    def document(self):return PythonDocument(self.path)

    def test_nested_scopes_are_derived_from_python(self):
        doc=self.document()
        self.assertEqual(len(doc.scopes),4)
        nested=next(k for k in doc.scopes if k.endswith('function:inner:5:4'))
        self.assertEqual(doc.scopes[nested].parent, 'module/function:outer:3:0')
        self.assertEqual(doc.scopes[nested].kind,'function')

    def test_module_has_signature_pins_and_real_variable(self):
        doc=self.document()
        g=doc.scope_graph()
        value=next(n for n in g['nodes'] if n['title']=='tax')
        self.assertEqual(value['draft_ports']['outputs'][0]['type'],'py:int')
        outer=next(n for n in g['nodes'] if n['title']=='OUTER')
        self.assertEqual(outer['draft_ports']['inputs'][0]['label'],'base')
        self.assertEqual(outer['draft_ports']['outputs'][0]['label'],'return')

    def test_closure_capture_and_global_read_are_not_public_parameters(self):
        doc=self.document()
        k=next(k for k in doc.scopes if k.endswith('function:inner:5:4'))
        g=doc.scope_graph(k)
        anchors={n['title']:n for n in g['nodes'] if n['source_kind'] in ('param','capture','global')}
        self.assertIn('PARAMETER value',anchors)
        self.assertIn('CAPTURE base',anchors)
        self.assertIn('CAPTURE increment',anchors)
        self.assertIn('GLOBAL READ tax',anchors)
        self.assertEqual(sum(n['source_kind']=='operation' for n in g['nodes']),3)
        for e in g['edges']:
            self.assertIn(e['relation'],('data','reference','control','call'))

    def test_expression_creates_typed_value_pins_and_connections(self):
        doc=self.document()
        key=next(k for k in doc.scopes if k.endswith('function:inc:10:0'))
        g=doc.scope_graph(key)
        add=next(n for n in g['nodes'] if n['title']=='ADD')
        self.assertEqual(len(add['draft_ports']['inputs']),2)
        self.assertEqual(add['draft_ports']['outputs'][0]['type'],'py:int')
        self.assertEqual(len([e for e in g['edges'] if e['target']==add['id']]),2)

    def test_if_true_return_false_falls_through(self):
        self.path.write_text('def f(x):\n    if x:\n        return 3\n    return 4\n',encoding='utf-8')
        doc=self.document()
        scope=next(k for k in doc.scopes if k!='module')
        g=doc.scope_graph(scope)
        self.assertEqual(sum(n['source_kind']=='branch' for n in g['nodes']),1)
        self.assertTrue(any(e['relation']=='control' for e in g['edges']))
        self.assertEqual(sum(n['source_kind']=='return' for n in g['nodes']),2)
        self.assertFalse(any(n['source_kind']=='control_join' for n in g['nodes']))

    def test_static_open_does_not_import_or_execute_file(self):
        victim=Path(self.tmp.name)/'side_effect.txt'
        self.path.write_text(f'from pathlib import Path\nPath({str(victim)!r}).write_text("BAD")\n',encoding='utf-8')
        doc=self.document();doc.scope_graph()
        self.assertFalse(victim.exists())

    def test_invalid_python_fails_explicitly(self):
        self.path.write_text('def foo(:\n', encoding='utf-8')
        with self.assertRaises(SourceError):self.document()

    def test_edit_literal_review_and_backup(self):
        doc=self.document();g=doc.scope_graph('module/function:inc:10:0')
        literal=next(n for n in g['nodes'] if n['source_kind']=='literal')
        prop=change_literal(doc,literal['source_span'],'25')
        self.assertIn('+ 25',prop.candidate.decode())
        self.assertIn('-    total = a + 10',prop.diff)
        self.assertEqual(self.path.read_bytes(),doc.raw)
        back=apply_proposal(prop)
        self.assertEqual(back.read_bytes(),doc.raw)
        self.assertEqual(self.path.read_bytes(),prop.candidate)
        ast.parse(self.path.read_text())

    def test_add_numeric_operand_to_return_preserves_code(self):
        doc=self.document();g=doc.scope_graph('module/function:inc:10:0')
        ret=next(n for n in g['nodes'] if n['source_kind']=='return')
        prop=add_constant_operand(doc,ret['source_span'],'7')
        self.assertIn('return (total) + 7',prop.candidate.decode())
        self.assertEqual(self.path.read_text(),CODE)

    def test_edit_refuses_executing_payload(self):
        doc=self.document();g=doc.scope_graph('module/function:inc:10:0')
        lit=next(n for n in g['nodes'] if n['source_kind']=='literal')
        with self.assertRaises(SourceError):change_literal(doc,lit['source_span'], '__import__("os").system("date")')
        ret=next(n for n in g['nodes'] if n['source_kind']=='return')
        with self.assertRaises(SourceError):add_constant_operand(doc,ret['source_span'],'1 + 2')

    def test_concurrent_edit_guard_preserves_external_change(self):
        doc=self.document();g=doc.scope_graph('module/function:inc:10:0')
        lit=next(n for n in g['nodes'] if n['source_kind']=='literal')
        prop=change_literal(doc,lit['source_span'],'99')
        self.path.write_text('# another editor changed the source\n'+CODE,encoding='utf-8')
        with self.assertRaises(SourceError):apply_proposal(prop)
        self.assertTrue(self.path.read_text().startswith('# another editor'))

    def test_utf8_byte_offset_edit(self):
        self.path.write_text('def g():\n    return "λhéllo"\n', encoding='utf-8')
        doc=self.document();k=next(k for k in doc.scopes if k!='module')
        g=doc.scope_graph(k)
        literal=next(n for n in g['nodes'] if n['source_kind']=='literal')
        prop=change_literal(doc,literal['source_span'], '"Edited Ω"')
        self.assertIn('return "Edited Ω"',prop.candidate.decode())
        self.assertEqual(self.path.read_text(),'def g():\n    return "λhéllo"\n')


if __name__=='__main__':unittest.main()
