"""v2.37: one source-authoritative edit path for preview, release and legacy UI."""
from pathlib import Path
import ast
import tempfile
import unittest

from studio_native.python_graph import PythonDocument
from studio_native.python_edit import rewire_source_operand, apply_proposal
from studio_native.source_connection import inspect_connection

SOURCE='''def choose(x, y):
    return x + y

def caller(value):
    local = 7
    return choose(42, local)

def other(value):
    return value + 1
'''

class ConnectionPreflightTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path=Path(tmp.name)/'source.py'
        self.path.write_text(SOURCE,encoding='utf8')
        self.doc=PythonDocument(self.path)
        self.scope=next(k for k in self.doc.scopes if 'caller' in k)
        self.graph=self.doc.scope_graph(self.scope)
        self.source=next(n for n in self.graph['nodes'] if n['source_kind']=='param')
        self.call=next(n for n in self.graph['nodes'] if n['source_kind']=='call')
        self.output=self.source['draft_ports']['outputs'][0]['id']
        self.arg=next(p['id'] for p in self.call['draft_ports']['inputs'] if p['id'].endswith(':arg0'))

    def inspect(self,src=None,out=None,dest=None,port=None):
        return inspect_connection(self.doc,src or self.source['id'],out or self.output,
                                  dest or self.call['id'],port or self.arg)

    def test_preflight_returns_exact_existing_lowering_without_writing(self):
        before=self.path.read_bytes()
        check=self.inspect()
        self.assertTrue(check.allowed,check.reason)
        self.assertEqual(check.scope,self.scope)
        existing=rewire_source_operand(self.doc,self.scope,self.source['id'],self.output,
                                       self.call['id'],self.arg)
        self.assertEqual(check.proposal,existing)
        self.assertIn(b'choose(value, local)',check.proposal.candidate)
        ast.parse(check.proposal.candidate)
        self.assertEqual(self.path.read_bytes(),before)

    def test_approved_candidate_reparses_to_real_source_graph_edge(self):
        check=self.inspect()
        self.assertTrue(check.allowed,check.reason)
        apply_proposal(check.proposal)
        graph=PythonDocument(self.path).scope_graph(self.scope)
        new_call=next(n for n in graph['nodes'] if n['source_kind']=='call')
        new_arg=next(p['id'] for p in new_call['draft_ports']['inputs']
                     if p['id'].endswith(':arg0'))
        self.assertTrue(any(e['source']==self.source['id'] and e['target']==new_call['id']
                            and e['targetPort']==new_arg for e in graph['edges']))

    def test_same_operand_is_refused_without_fake_work(self):
        self.path.write_text(SOURCE.replace('choose(42, local)','choose(value, local)'),encoding='utf8')
        self.doc=PythonDocument(self.path)
        refreshed=self.doc.scope_graph(self.scope)
        self.call=next(n for n in refreshed['nodes'] if n['source_kind']=='call')
        self.arg=next(p['id'] for p in self.call['draft_ports']['inputs']
                      if p['id'].endswith(':arg0'))
        check=self.inspect()
        self.assertFalse(check.allowed)
        self.assertIn('already',check.reason)
        self.assertIsNone(check.proposal)

    def test_cross_function_refused_before_edit(self):
        other=next(n for k in self.doc.scopes if 'other' in k
                   for n in self.doc.scope_graph(k)['nodes'] if n['source_kind']=='return')
        check=self.inspect(dest=other['id'],port=other['draft_ports']['inputs'][0]['id'])
        self.assertFalse(check.allowed)
        self.assertIn('same function',check.reason)

    def test_invalid_ports_and_execution_endpoint_refused(self):
        self.assertFalse(self.inspect(out='not-a-port').allowed)
        self.assertFalse(self.inspect(port='not-an-input').allowed)
        self.assertFalse(inspect_connection(self.doc,'','',self.call['id'],self.arg).allowed)

    def test_unsafe_call_result_not_advertised_as_compatible_source(self):
        call_output=self.call['draft_ports']['outputs'][-1]['id']
        self.assertFalse(self.inspect(src=self.call['id'],out=call_output).allowed)

    def test_reject_unknown_or_missing_document(self):
        self.assertFalse(inspect_connection(None,'a','b','c','d').allowed)
        self.assertFalse(self.inspect(src='py:unknown|param|value').allowed)

    def test_approval_rejects_external_file_edit_after_green_preview(self):
        check=self.inspect()
        self.assertTrue(check.allowed)
        self.path.write_bytes(self.path.read_bytes()+b'# changed externally\n')
        with self.assertRaisesRegex(ValueError,'externally'):
            apply_proposal(check.proposal)
        self.assertFalse((self.path.parent/'source.py.smi-backup').exists())

    def test_qt_preview_and_release_share_inspector_and_clear_cache(self):
        source=Path(__file__).resolve().parents[1]/'studio_native/gui.py'
        code=source.read_text()
        self.assertIn('self.window.review_source_proposal(check.proposal)',code)
        self.assertIn('return inspect_connection(self.window.python_doc',code)
        self.assertIn('self.connection_hints.clear();self._connection_hover=None',code)
        self.assertIn('self._start_source_compatibility_preview()',code)
        self.assertNotIn('lambda draft: m.connect(draft,src,out,target.node.data',
                         code[code.index('    def _source_connection_check('):
                              code.index('    def update_port_appearance(',code.index('    def _source_connection_check('))]
                         .split('            elif target and target.direction==\'inputs\':')[0])

if __name__=='__main__': unittest.main()
