"""Text-to-graph authority, UTF-16 source highlighting, return boundary tests."""
import tempfile
import unittest
from pathlib import Path

from studio_native.python_graph import PythonDocument, SourceError
from studio_native.source_editor import span_to_utf16,prepare_source_change,save_source_change


class TextEditorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'demo.py'
        self.path.write_text('def fun(x):\n    return x + 2\n',encoding='utf-8')

    def doc(self):return PythonDocument(self.path)

    def test_edit_save_and_graph_reparse(self):
        doc=self.doc()
        backup=save_source_change(doc,'def fun(x):\n    return x + 9\n')
        self.assertIsNotNone(backup)
        self.assertEqual(backup.read_bytes(),doc.raw)
        new=PythonDocument(self.path)
        self.assertIn('x + 9',new.source)
        self.assertEqual(len(new.scopes),len(doc.scopes))

    def test_invalid_edit_retains_file_and_creates_no_backup(self):
        doc=self.doc()
        with self.assertRaisesRegex(SourceError,'syntax'):
            save_source_change(doc,'def fun(x):\n    return (\n')
        self.assertEqual(self.path.read_bytes(),doc.raw)
        self.assertEqual(list(self.path.parent.glob('*.smi-backup*')),[])

    def test_stale_external_edit_refused(self):
        doc=self.doc()
        self.path.write_text('changed = True\n')
        with self.assertRaisesRegex(SourceError,'changed externally'):
            save_source_change(doc,'def fun(x):\n    return x + 12\n')
        self.assertEqual(self.path.read_text(),'changed = True\n')

    def test_no_edit_no_backup(self):
        self.assertIsNone(save_source_change(self.doc(),self.doc().source))
        self.assertEqual(list(self.path.parent.glob('*.smi-backup*')),[])

    def test_preserves_crlf(self):
        self.path.write_bytes(b'def fun(x):\r\n    return x + 2\r\n')
        doc=self.doc()
        save_source_change(doc,'def fun(x):\n    return x + 3\n')
        self.assertEqual(self.path.read_bytes(),b'def fun(x):\r\n    return x + 3\r\n')

    def test_multiple_backups_never_overwritten(self):
        doc=self.doc()
        b1=save_source_change(doc,'def fun(x):\n    return x + 4\n')
        doc2=self.doc()
        b2=save_source_change(doc2,'def fun(x):\n    return x + 5\n')
        self.assertNotEqual(b1,b2)
        self.assertEqual(b1.read_bytes(),doc.raw)
        self.assertEqual(b2.read_bytes(),doc2.raw)

    def test_function_parameter_nodes_have_source_locations(self):
        doc=self.doc()
        scope=next(key for key in doc.scopes if key!='module')
        graph=doc.scope_graph(scope)
        param=next(n for n in graph['nodes'] if n['source_kind']=='param')
        start,end=span_to_utf16(doc.source,param['source_span'])
        self.assertEqual(doc.source[start:end],'x')

    def test_utf16_offsets_for_non_bmp_and_python_utf8_ast(self):
        text='emoji = "🎯"\nvalue = emoji + 1\n'
        self.path.write_text(text,encoding='utf-8')
        import ast
        node=ast.parse(text).body[1].value.right
        start,end=span_to_utf16(text,{'line':node.lineno,'col':node.col_offset,
                                     'end_line':node.end_lineno,'end_col':node.end_col_offset})
        encoded=text.encode('utf-16-le')
        self.assertEqual(encoded[start*2:end*2].decode('utf-16-le'),'1')

    def test_utf8_ast_multibyte_columns(self):
        text='a = "café" + 4\n'
        import ast
        value=ast.parse(text).body[0].value.right
        start,end=span_to_utf16(text,dict(line=value.lineno,col=value.col_offset,
                 end_line=value.end_lineno,end_col=value.end_col_offset))
        self.assertEqual(text[start:end],'4')


class CompositeReturnTests(unittest.TestCase):
    def composite(self,source):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'source.py';path.write_text(source)
            doc=PythonDocument(path)
            graph=doc.composite_file_graph(set(doc.scopes)-{'module'})
            return graph

    def test_single_terminal_return_is_boundary_projection(self):
        graph=self.composite('def add(a, b):\n    value = a + b\n    return value\n')
        ret=next(n for n in graph['nodes'] if n['source_kind']=='return')
        self.assertTrue(ret['presentation_hidden'])
        self.assertTrue(ret['terminal_boundary_owner'])
        owner=next(n for n in graph['nodes'] if n['source_kind']=='function')
        self.assertEqual(sum(p['label']=='return' for p in owner['draft_ports']['outputs']),1)
        self.assertTrue(any(e['target']==ret['id'] for e in graph['edges']))

    def test_multiple_early_returns_remain_nodes(self):
        graph=self.composite('def choose(x):\n    if x > 2:\n        return 3\n    return x\n')
        rets=[n for n in graph['nodes'] if n['source_kind']=='return']
        self.assertGreaterEqual(len(rets),2)
        self.assertFalse(any(n.get('terminal_boundary_owner') for n in rets))

    def test_early_loop_return_prevents_terminal_boundary_folding(self):
        graph=self.composite('def f(items):\n    for item in items:\n        if item < 0:\n            return 0\n    return 1\n')
        returns=[n for n in graph['nodes'] if n['source_kind']=='return']
        self.assertEqual(len(returns),2)
        self.assertFalse(any(n.get('terminal_boundary_owner') for n in returns))

    def test_non_terminal_return_remains(self):
        graph=self.composite('def f(x):\n    if x > 2:\n        return x\n    x += 1\n')
        rets=[n for n in graph['nodes'] if n['source_kind']=='return']
        self.assertFalse(any(n.get('terminal_boundary_owner') for n in rets))


if __name__=='__main__':unittest.main()
