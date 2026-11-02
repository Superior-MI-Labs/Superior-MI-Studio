"""v2.39: single-evaluation Call-result connections use stored locals, never copy a call."""
import ast
from pathlib import Path
import tempfile
import unittest

from studio_native.python_graph import PythonDocument
from studio_native.python_edit import apply_proposal
from studio_native.source_connection import inspect_connection


BASE = '''def dispatch(value):
    stored = calculate(value)
    return deliver(0, label="before")

def calculate(x):
    return x

def deliver(x, *, label):
    return x
'''


class StoredCallResultTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / 'source.py'
        self.path.write_text(BASE, encoding='utf-8')
        self.refresh()

    def refresh(self):
        self.doc=PythonDocument(self.path)
        self.scope=next(k for k,s in self.doc.scopes.items() if s.title=='dispatch')
        self.graph=self.doc.scope_graph(self.scope)

    def call(self,name):
        matches=[n for n in self.graph['nodes']
                 if n.get('source_kind')=='call' and n.get('subtitle','').startswith(name+'(')]
        self.assertEqual(len(matches),1)
        return matches[0]

    def port(self,node,side,suffix):
        matches=[p['id'] for p in node['draft_ports'][side] if p['id'].endswith(':'+suffix)]
        self.assertEqual(len(matches),1)
        return matches[0]

    def inspect(self,port='arg0'):
        src=self.call('calculate');dst=self.call('deliver')
        return inspect_connection(self.doc,src['id'],self.port(src,'outputs','result'),
                                  dst['id'],self.port(dst,'inputs',port))

    def test_preflight_is_stored_reference_and_never_writes(self):
        before=self.path.read_bytes()
        check=self.inspect()
        self.assertTrue(check.allowed,check.reason)
        self.assertEqual(check.mode,'stored-reference')
        self.assertIn('does not invoke it again',check.reason)
        self.assertEqual(check.proposal.candidate.count(b'calculate(value)'),1)
        self.assertIn(b'deliver(stored, label=',check.proposal.candidate)
        self.assertEqual(self.path.read_bytes(),before)

    def test_apply_reparse_has_call_to_set_to_call_data_path(self):
        check=self.inspect()
        self.assertTrue(check.allowed,check.reason)
        apply_proposal(check.proposal)
        self.refresh()
        calculate=self.call('calculate')
        deliver=self.call('deliver')
        stored=next(n for n in self.graph['nodes']
                    if n.get('source_kind')=='assignment' and n.get('binding_name')=='stored')
        self.assertTrue(any(e['source']==calculate['id'] and e['target']==stored['id']
                            and e['relation']=='data' for e in self.graph['edges']))
        self.assertTrue(any(e['source']==stored['id'] and e['target']==deliver['id']
                            and e['targetPort'].endswith(':arg0') and e['relation']=='data'
                            for e in self.graph['edges']))
        self.assertEqual(self.path.read_text().count('calculate(value)'),1)

    def test_named_keyword_is_supported(self):
        check=self.inspect('kw_label')
        self.assertTrue(check.allowed,check.reason)
        self.assertIn(b'label=stored',check.proposal.candidate)

    def test_literal_and_local_modes_are_not_mislabeled_as_stored_call(self):
        call=self.call('deliver')
        arg=self.port(call,'inputs','arg0')
        literal=next(n for n in self.graph['nodes'] if n['source_kind']=='literal' and n['subtitle']=='0')
        check=inspect_connection(self.doc,literal['id'],self.port(literal,'outputs','value'),
                                 call['id'],arg)
        self.assertFalse(check.allowed)  # unchanged operand, no false-positive edit
        stored=next(n for n in self.graph['nodes'] if n.get('binding_name')=='stored')
        check=inspect_connection(self.doc,stored['id'],self.port(stored,'outputs','value'),
                                 call['id'],arg)
        self.assertTrue(check.allowed,check.reason)
        self.assertEqual(check.mode,'name-reference')

    def test_call_without_stored_assignment_is_rejected(self):
        self.path.write_text(BASE.replace('stored = calculate(value)',
                                          'calculate(value)'),encoding='utf-8')
        self.refresh()
        check=self.inspect()
        self.assertFalse(check.allowed)
        self.assertIn('existing single local assignment',check.reason)

    def test_returned_call_cannot_be_reexecuted_for_wiring(self):
        self.path.write_text(BASE.replace('stored = calculate(value)',
                                          'if value:\n        return calculate(value)'),encoding='utf-8')
        self.refresh()
        check=self.inspect()
        self.assertFalse(check.allowed)

    def test_rebinding_is_rejected(self):
        self.path.write_text(BASE.replace('    return deliver',
                                          '    stored = 7\n    return deliver'),encoding='utf-8')
        self.refresh()
        check=self.inspect()
        self.assertFalse(check.allowed)
        self.assertIn('rebound',check.reason)

    def test_intervening_effect_is_rejected(self):
        self.path.write_text(BASE.replace('    return deliver',
                                          '    log(stored)\n    return deliver'),encoding='utf-8')
        self.refresh()
        check=self.inspect()
        self.assertFalse(check.allowed)
        self.assertIn('effect',check.reason)

    def test_prior_call_argument_effect_is_rejected(self):
        self.path.write_text(BASE.replace('deliver(0, label="before")',
                                          'deliver(side_effect(), label="before")'),encoding='utf-8')
        self.refresh()
        check=self.inspect('kw_label')
        self.assertFalse(check.allowed)
        self.assertIn('context',check.reason)

    def test_nested_call_source_must_be_direct_assignment(self):
        self.path.write_text(BASE.replace('stored = calculate(value)',
                                          'stored = wrapper(calculate(value))'),encoding='utf-8')
        self.refresh()
        check=self.inspect()
        self.assertFalse(check.allowed)
        self.assertIn('existing single local assignment',check.reason)

    def test_cross_conditional_arms_are_rejected(self):
        self.path.write_text(BASE.replace('    stored = calculate(value)\n    return deliver(0, label="before")',
                     '    if value:\n        stored = calculate(value)\n'
                     '    else:\n        return deliver(0, label="before")'),encoding='utf-8')
        self.refresh()
        check=self.inspect()
        self.assertFalse(check.allowed)
        self.assertIn('different control-flow regions',check.reason)

    def test_stale_file_rejected_after_preview(self):
        check=self.inspect()
        self.assertTrue(check.allowed)
        self.path.write_text(BASE+'# modified externally\n',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'externally'):
            apply_proposal(check.proposal)
        self.assertFalse((self.path.parent/'source.py.smi-backup').exists())

    def test_unicode_crlf_preserved(self):
        text=BASE.replace('stored','résultat').replace('\n','\r\n')
        self.path.write_bytes(text.encode('utf-8'))
        self.refresh()
        check=self.inspect()
        self.assertTrue(check.allowed,check.reason)
        self.assertIn('résultat'.encode(),check.proposal.candidate)
        self.assertEqual(check.proposal.candidate.count(b'\r\n'),text.count('\r\n'))
        self.assertIn(b'deliver(r',check.proposal.candidate)


if __name__=='__main__':
    unittest.main()
