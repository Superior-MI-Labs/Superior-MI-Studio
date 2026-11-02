"""v2.38: real source-backed expression composition and named keyword wiring."""
import ast
from pathlib import Path
import tempfile
import unittest
from studio_native.python_graph import PythonDocument
from studio_native.python_edit import apply_proposal
from studio_native.source_connection import inspect_connection

EXAMPLE = '''def caller(value):
    constant_math = 2 + 3 * 4
    constant_test = (4 + 5) > 7
    return deliver(0, label="before", priority=1)

def deliver(number, *, label, priority):
    return number
'''

class ExpressionAndKeywordWiringTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path=Path(tmp.name)/'example.py'
        self.path.write_text(EXAMPLE,encoding='utf-8')
        self.refresh()

    def refresh(self):
        self.doc=PythonDocument(self.path)
        self.scope=next(k for k,s in self.doc.scopes.items() if s.title=='caller')
        self.graph=self.doc.scope_graph(self.scope)

    def node(self,kind,subtitle=None):
        matches=[n for n in self.graph['nodes'] if n['source_kind']==kind and
                 (subtitle is None or subtitle in n['subtitle'])]
        self.assertEqual(len(matches),1,(kind,subtitle,[(n['source_kind'],n['subtitle']) for n in self.graph['nodes']]))
        return matches[0]

    def port(self,node,side,ending):
        matches=[p['id'] for p in node['draft_ports'][side] if p['id'].endswith(':'+ending)]
        self.assertEqual(len(matches),1,(node['id'],ending))
        return matches[0]

    def check(self,source,target,suffix):
        return inspect_connection(self.doc,source['id'],self.port(source,'outputs','result'),
                                  target['id'],self.port(target,'inputs',suffix))

    def test_keyword_arguments_get_real_named_input_ports_and_edges(self):
        call=self.node('call')
        self.assertEqual([p['label'] for p in call['draft_ports']['inputs'] if ':kw_' in p['id']],
                         ['label=','priority='])
        for kw in ('label','priority'):
            self.assertTrue(any(e['target']==call['id'] and
                                e['targetPort']==self.port(call,'inputs','kw_'+kw)
                                for e in self.graph['edges']))

    def test_parameter_to_named_keyword_is_qualified_and_reparses(self):
        param=self.node('param')
        call=self.node('call')
        before=self.path.read_bytes()
        check=inspect_connection(self.doc,param['id'],param['draft_ports']['outputs'][0]['id'],
                                 call['id'],self.port(call,'inputs','kw_label'))
        self.assertTrue(check.allowed,check.reason)
        self.assertIn(b'label=value',check.proposal.candidate)
        self.assertEqual(before,self.path.read_bytes())
        apply_proposal(check.proposal)
        self.refresh()
        call=self.node('call')
        self.assertTrue(any(e['source']==param['id'] and e['target']==call['id']
                            and e['targetPort']==self.port(call,'inputs','kw_label')
                            for e in self.graph['edges']))

    def test_constant_expression_to_positional_call_argument(self):
        src=self.node('operation','2 + 3 * 4')
        dst=self.node('call')
        check=self.check(src,dst,'arg0')
        self.assertTrue(check.allowed,check.reason)
        self.assertIn(b'deliver((2 + 3 * 4),',check.proposal.candidate)
        apply_proposal(check.proposal)
        updated=ast.parse(self.path.read_text())
        fn=updated.body[0]
        self.assertIsInstance(fn.body[-1].value.args[0],ast.BinOp)
        self.refresh()
        self.assertGreaterEqual(sum(n['source_kind']=='operation' for n in self.graph['nodes']),3)

    def test_constant_comparison_to_keyword_and_return(self):
        src=self.node('compare')
        dst=self.node('call')
        check=self.check(src,dst,'kw_priority')
        self.assertTrue(check.allowed,check.reason)
        self.assertIn(b'priority=((4 + 5) > 7)',check.proposal.candidate)

    def test_arithmetic_result_to_comparison_operand_is_qualified(self):
        expression=self.node('operation','2 + 3 * 4')
        comparison=self.node('compare')
        check=self.check(expression,comparison,'rhs')
        self.assertTrue(check.allowed,check.reason)
        self.assertIn(b'(4 + 5) > (2 + 3 * 4)',check.proposal.candidate)

    def test_reject_dynamic_operator_names_and_unsafe_sources(self):
        self.path.write_text('''def caller(value):
    computed = value + 2
    return deliver(0, label="x")
''')
        self.refresh()
        src=self.node('operation')
        check=self.check(src,self.node('call'),'arg0')
        self.assertFalse(check.allowed)
        self.assertIn('constant-only',check.reason)

    def test_reject_division_and_potential_exception(self):
        self.path.write_text('''def caller(value):
    computed = 1 / 0
    return deliver(0)
''')
        self.refresh()
        check=self.check(self.node('operation'),self.node('call'),'arg0')
        self.assertFalse(check.allowed)
        self.assertIn('constant-only',check.reason)

    def test_reject_source_expression_used_as_own_operand(self):
        expression=self.node('operation','2 + 3 * 4')
        check=self.check(expression,expression,'rhs')
        self.assertFalse(check.allowed)

    def test_reject_duplicate_keyword_and_bad_output(self):
        call=self.node('call')
        param=self.node('param')
        check=inspect_connection(self.doc,param['id'],param['draft_ports']['outputs'][0]['id'],
                                 call['id'],call['id']+':inputs:kw_invalid')
        self.assertFalse(check.allowed)
        src=self.node('operation','2 + 3 * 4')
        self.assertFalse(inspect_connection(self.doc,src['id'],self.port(src,'outputs','result'),
                                            call['id'],call['id']+':inputs:kw_invalid').allowed)
        src=self.node('operation','2 + 3 * 4')
        check=inspect_connection(self.doc,src['id'],src['id']+':outputs:fake',
                                 call['id'],self.port(call,'inputs','arg0'))
        self.assertFalse(check.allowed)

    def test_refuse_keyword_unpack_writes(self):
        self.path.write_text('''def caller(value):
    return deliver(1, **{"label": "x"})
''')
        self.refresh()
        call=self.node('call')
        self.assertTrue(any('** unpack' in p['label'] for p in call['draft_ports']['inputs']))
        param=self.node('param')
        port=next(p['id'] for p in call['draft_ports']['inputs'] if 'kw_unpack' in p['id'])
        check=inspect_connection(self.doc,param['id'],param['draft_ports']['outputs'][0]['id'],call['id'],port)
        self.assertFalse(check.allowed)

    def test_external_change_after_preview_is_rejected(self):
        check=self.check(self.node('operation','2 + 3 * 4'),self.node('call'),'arg0')
        self.assertTrue(check.allowed)
        self.path.write_text(self.path.read_text()+'\n# external change\n')
        with self.assertRaisesRegex(ValueError,'externally'):
            apply_proposal(check.proposal)
        self.assertFalse(list(self.path.parent.glob('*.smi-backup*')))

    def test_byte_ranges_preserve_unicode_comments_and_crlf(self):
        source=EXAMPLE.replace('    constant_math','    # café\n    constant_math')
        self.path.write_bytes(source.replace('\n','\r\n').encode('utf-8'))
        self.refresh()
        check=self.check(self.node('operation','2 + 3 * 4'),self.node('call'),'arg0')
        self.assertTrue(check.allowed,check.reason)
        self.assertIn('café'.encode(),check.proposal.candidate)
        self.assertIn(b'\r\n    return deliver((2',check.proposal.candidate)
        self.assertEqual(check.proposal.candidate.count(b'\n'),EXAMPLE.count('\n')+1)
        self.assertIn(b'\r\n',check.proposal.candidate)

if __name__=='__main__':unittest.main()
