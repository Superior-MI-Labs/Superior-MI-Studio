"""v0.5 source-edit qualification: an edge drag creates a Python edit proposal.

Tests never run untrusted Python. Original file is unchanged until explicit apply.
"""
from __future__ import annotations
import ast
import tempfile
import unittest
from pathlib import Path

from studio_native.python_graph import PythonDocument, SourceError
from studio_native.python_edit import rewire_source_operand, apply_proposal

SRC = '''def example(a: int, b: int):
    first = a + 10
    second = b * 20
    test = second > 10
    return first + second
'''

class RewireTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'example.py'
        self.path.write_text(SRC,encoding='utf-8')
        self.doc=PythonDocument(self.path)
        self.scope=next(k for k in self.doc.scopes if k!='module')
        self.graph=self.doc.scope_graph(self.scope)

    def node(self,kind,contains=None):
        return next(n for n in self.graph['nodes'] if n['source_kind']==kind and
                    (contains is None or contains in n.get('subtitle','')))

    def source_output(self,node):
        return node['draft_ports']['outputs'][0]['id']

    def input(self,node,which):
        return next(p['id'] for p in node['draft_ports']['inputs']
                    if p['id'].endswith(':'+which))

    def test_copy_parameter_into_binary_operand(self):
        param=self.node('param')
        op=next(n for n in self.graph['nodes'] if n['source_kind']=='operation' and 'a + 10' in n['subtitle'])
        proposal=rewire_source_operand(self.doc,self.scope,param['id'],self.source_output(param),op['id'],self.input(op,'rhs'))
        self.assertIn('first = a + a',proposal.candidate.decode())
        self.assertEqual(self.path.read_text(),SRC)
        self.assertIn('first = a + a',proposal.diff)
        ast.parse(proposal.candidate)

    def test_copy_literal_into_comparison_input(self):
        lit=self.node('literal','20')
        comparison=next(n for n in self.graph['nodes'] if n['source_kind']=='compare')
        proposal=rewire_source_operand(self.doc,self.scope,lit['id'],self.source_output(lit),comparison['id'],self.input(comparison,'rhs'))
        self.assertIn('test = second > 20',proposal.candidate.decode())
        backup=apply_proposal(proposal)
        self.assertEqual(backup.read_text(),SRC)
        self.assertIn('test = second > 20',self.path.read_text())

    def test_self_or_incorrect_port_refuses(self):
        lit=self.node('literal','20')
        compare=next(n for n in self.graph['nodes'] if n['source_kind']=='compare')
        with self.assertRaises(SourceError):
            rewire_source_operand(self.doc,self.scope,lit['id'],'fake-output',compare['id'],self.input(compare,'rhs'))
        with self.assertRaises(SourceError):
            rewire_source_operand(self.doc,self.scope,lit['id'],self.source_output(lit),compare['id'],'fake-input')
        with self.assertRaises(SourceError):
            rewire_source_operand(self.doc,'module',lit['id'],self.source_output(lit),compare['id'],self.input(compare,'rhs'))
        with self.assertRaises(SourceError):
            rewire_source_operand(self.doc,self.scope,lit['id'],self.source_output(lit),lit['id'],self.source_output(lit))

    def test_unsupported_source_is_not_treated_as_pure(self):
        operation=next(n for n in self.graph['nodes'] if n['source_kind']=='operation' and 'b * 20' in n['subtitle'])
        compare=next(n for n in self.graph['nodes'] if n['source_kind']=='compare')
        with self.assertRaisesRegex(SourceError,'bounded constant-only'):
            rewire_source_operand(self.doc,self.scope,operation['id'],self.source_output(operation),compare['id'],self.input(compare,'rhs'))

    def test_stale_document_rejected_on_commit(self):
        lit=self.node('literal','20')
        compare=next(n for n in self.graph['nodes'] if n['source_kind']=='compare')
        proposal=rewire_source_operand(self.doc,self.scope,lit['id'],self.source_output(lit),compare['id'],self.input(compare,'rhs'))
        self.path.write_text('# external\n'+SRC,encoding='utf-8')
        with self.assertRaisesRegex(SourceError,'changed externally'):
            apply_proposal(proposal)

    def test_unicode_bytes_and_preserves_other_source(self):
        src='''def example(a: int):
    note = "Ωλ"
    total = a + 10
    return total
'''
        self.path.write_text(src,encoding='utf-8')
        doc=PythonDocument(self.path)
        scope=next(k for k in doc.scopes if k!='module')
        g=doc.scope_graph(scope)
        param=next(n for n in g['nodes'] if n['source_kind']=='param')
        op=next(n for n in g['nodes'] if n['source_kind']=='operation')
        proposal=rewire_source_operand(doc,scope,param['id'],param['draft_ports']['outputs'][0]['id'],op['id'],self.input(op,'rhs'))
        self.assertEqual(proposal.candidate.decode(),src.replace('a + 10','a + a'))

    def test_reject_wrong_function_scope(self):
        self.path.write_text('''def first(a):
    return a + 2

def second(b):
    return b + 3
''')
        doc=PythonDocument(self.path)
        scopes=[k for k in doc.scopes if k!='module']
        g1,g2=(doc.scope_graph(k) for k in scopes)
        param=next(n for n in g1['nodes'] if n['source_kind']=='param')
        op=next(n for n in g2['nodes'] if n['source_kind']=='operation')
        with self.assertRaises(SourceError):
            rewire_source_operand(doc,scopes[0],param['id'],param['draft_ports']['outputs'][0]['id'],op['id'],self.input(op,'rhs'))

if __name__=='__main__':unittest.main()
