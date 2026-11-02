"""v2.51: source-authoritative input replacement, modal test supervision contracts."""
from pathlib import Path
import ast
import tempfile
import unittest
from studio_native.python_graph import PythonDocument, SourceError
from studio_native.python_edit import replace_source_input_literal, apply_proposal, SourceEditHistory

class InputEditingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'code.py'
        self.path.write_bytes(b'def f(value):\n    total = value + 2\n    return total\n')
        self.refresh()

    def refresh(self):
        self.doc=PythonDocument(self.path)
        self.scope=next(key for key,info in self.doc.scopes.items() if info.title=='f')
        self.graph=self.doc.scope_graph(self.scope)

    def input(self,kind,port):
        node=next(n for n in self.graph['nodes'] if n['source_kind']==kind)
        pin=next(x['id'] for x in node['draft_ports']['inputs'] if x['id'].endswith(':'+port))
        return node['id'],pin

    def test_replace_connected_name_and_round_trip(self):
        target,pin=self.input('return','value')
        original=self.path.read_bytes()
        proposal=replace_source_input_literal(self.doc,self.scope,target,pin,'None')
        self.assertEqual(self.path.read_bytes(),original)
        history=SourceEditHistory();history.apply(proposal)
        self.assertIn(b'return None',self.path.read_bytes())
        self.refresh()
        self.assertIn('None',self.doc.source)
        history.undo(self.path)
        self.assertEqual(self.path.read_bytes(),original)
        history.redo(self.path)
        self.assertIn(b'return None',self.path.read_bytes())

    def test_replace_binary_operand_without_wiping_other_expression(self):
        target,pin=self.input('operation','lhs')
        proposal=replace_source_input_literal(self.doc,self.scope,target,pin,'7')
        self.assertIn(b'total = 7 + 2',proposal.candidate)
        self.assertIn(b'return total',proposal.candidate)

    def test_replace_simple_assignment_value(self):
        target,pin=self.input('assignment','value')
        # The old value contains arithmetic and may call user-defined
        # operators, so it is intentionally ineligible for destructive reset.
        with self.assertRaisesRegex(SourceError,'complex inputs'):
            replace_source_input_literal(self.doc,self.scope,target,pin,'0')

    def test_replace_call_positional_and_keyword_reads(self):
        self.path.write_text('def f(value):\n    return render(value, label=value)\n')
        self.refresh()
        for operand,expected in (('arg0',b'render(10, label=value)'),
                                 ('kw_label',b'render(value, label=10)')):
            node,pin=self.input('call',operand)
            proposal=replace_source_input_literal(self.doc,self.scope,node,pin,'10')
            self.assertIn(expected,proposal.candidate)
            self.assertIn(b'return',proposal.candidate)
            self.assertEqual(self.path.read_text(),'def f(value):\n    return render(value, label=value)\n')

    def test_comparison_port_reset_round_trips(self):
        self.path.write_text('def f(value):\n    return value > 0\n')
        self.refresh()
        node,pin=self.input('compare','lhs')
        proposal=replace_source_input_literal(self.doc,self.scope,node,pin,'-1')
        self.assertIn(b'return -1 > 0',proposal.candidate)
        apply_proposal(proposal)
        self.refresh()
        self.assertIn('return -1 > 0',self.doc.source)

    def test_refuse_call_expression_erasure(self):
        self.path.write_text('def f(value):\n    return dangerous(value)\n')
        self.refresh()
        target,pin=self.input('return','value')
        with self.assertRaisesRegex(SourceError,'complex inputs'):
            replace_source_input_literal(self.doc,self.scope,target,pin,'0')

    def test_refuse_executable_or_untrusted_literals(self):
        target,pin=self.input('return','value')
        for value in ('dangerous()','__import__("os")','value','[1,2]','lambda:0','1+1',''):
            with self.subTest(value=value),self.assertRaises(SourceError):
                replace_source_input_literal(self.doc,self.scope,target,pin,value)

    def test_refuse_malformed_port_cross_scope_and_missing_node(self):
        target,pin=self.input('return','value')
        for scope,node,port in ((self.scope,target,pin+'fake'),('module',target,pin),
                                (self.scope,'py:fake',pin)):
            with self.assertRaises(SourceError):
                replace_source_input_literal(self.doc,scope,node,port,'0')
        target,flow=self.input('return','in')
        with self.assertRaises(SourceError):
            replace_source_input_literal(self.doc,self.scope,target,flow,'0')

    def test_refuse_external_save_race(self):
        target,pin=self.input('return','value')
        proposal=replace_source_input_literal(self.doc,self.scope,target,pin,'False')
        self.path.write_bytes(b'# external change\n'+self.path.read_bytes())
        with self.assertRaisesRegex(SourceError,'externally'):
            apply_proposal(proposal)

    def test_preserve_unicode_comments_crlf(self):
        raw=b'# caf\xc3\xa9\r\ndef f(value):\r\n    total = value + 2\r\n    return total\r\n'
        self.path.write_bytes(raw);self.refresh()
        target,pin=self.input('return','value')
        proposal=replace_source_input_literal(self.doc,self.scope,target,pin,'-3')
        self.assertIn(b'caf\xc3\xa9\r\n',proposal.candidate)
        self.assertIn(b'    return -3\r\n',proposal.candidate)

class QtSmokeContractTests(unittest.TestCase):
    def test_modal_paths_use_one_supervisor_instead_of_singleshot(self):
        source=(Path(__file__).resolve().parents[1]/'studio_native/qt_smoke.py').read_text()
        tree=ast.parse(source)
        self.assertNotIn('QTimer.singleShot(',source)
        calls=[node for node in ast.walk(tree) if isinstance(node,ast.Call) and
               isinstance(node.func,ast.Name) and node.func.id=='exercise_modal']
        self.assertGreaterEqual(len(calls),6, 'Every new modal path must use the shared supervisor')
        self.assertIn('QElapsedTimer',source)
        self.assertIn('QT_STAGE function-call-form',source)
        self.assertIn('QT_STAGE file-picker',source)

if __name__=='__main__':unittest.main()
