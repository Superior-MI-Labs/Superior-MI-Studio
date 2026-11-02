"""Graph-owned authoring v2.65: function interfaces, literal editing, pin replacement, Save As."""
from __future__ import annotations

import ast
import copy
from pathlib import Path
import tempfile
import unittest

from studio_native.program_graph import (
    ProgramGraph, ProgramGraphError, GraphConflict, template_ports,
    descriptor, validate,
)

ROOT=Path(__file__).resolve().parents[1]


class AuthoringTransactions(unittest.TestCase):
    def setUp(self):
        self.graph=ProgramGraph()
        self.graph.edit(0,'add_function',id='f',name='compute')

    def commit(self,action,**kwargs):
        return self.graph.edit(self.graph.revision,action,**kwargs)

    def node(self,ident,operation):
        self.commit('add_node',id=ident,function='f',operation=operation,**template_ports(operation))
        return next(n for n in self.graph.state['nodes'] if n['id']==ident)

    def test_function_interface_edits_preserve_id_and_undo(self):
        self.commit('add_parameter',function='f',id='p',name='number',type='py:int')
        self.commit('rename_function',function='f',name='process')
        self.commit('rename_parameter',function='f',parameter='p',name='input_value')
        self.commit('set_return_type',function='f',type='py:unknown')
        func=self.graph.state['functions'][0]
        self.assertEqual((func['id'],func['name'],func['parameters'][0]['id'],func['parameters'][0]['name']),
                         ('f','process','p','input_value'))
        self.assertTrue(self.graph.undo(self.graph.revision))
        self.assertEqual(self.graph.state['functions'][0]['parameters'][0]['name'],'number')
        self.assertTrue(self.graph.redo(self.graph.revision))
        self.assertEqual(self.graph.state['functions'][0]['parameters'][0]['name'],'input_value')
        self.commit('remove_parameter',function='f',parameter='p')
        self.assertEqual(self.graph.state['functions'][0]['parameters'],[])
        self.graph.undo(self.graph.revision)
        self.assertEqual(self.graph.state['functions'][0]['parameters'][0]['id'],'p')

    def test_invalid_interface_edits_are_atomic(self):
        self.commit('add_parameter',function='f',id='p',name='value')
        for action,kwargs in [
            ('rename_function',{'function':'f','name':'class'}),
            ('rename_function',{'function':'f','name':'not valid'}),
            ('rename_parameter',{'function':'f','parameter':'p','name':'for'}),
            ('rename_parameter',{'function':'f','parameter':'p','name':'bad value'}),
            ('add_parameter',{'function':'f','name':'value'}),
            ('remove_parameter',{'function':'f','parameter':'missing'}),
            ('set_return_type',{'function':'f','type':'py:bad type'}),
        ]:
            with self.subTest(action=action,kwargs=kwargs):
                before=self.graph.state
                with self.assertRaises((ProgramGraphError,KeyError)):
                    self.commit(action,**kwargs)
                self.assertEqual(self.graph.state,before)

    def test_interface_and_nodes_round_trip_without_code_generation(self):
        self.commit('add_parameter',function='f',id='p',name='café_value')
        self.node('lit','python.literal')
        self.commit('set_property',node='lit',key='value',value='hello ☀')
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'sample.smi-graph'
            self.graph.save(p)
            other=ProgramGraph.open(p)
            self.assertEqual(other.state,self.graph.state)
            self.assertEqual(other.state['nodes'][0]['properties']['value'],'hello ☀')
            self.assertEqual(descriptor(other.state,'f').origin,'program')

    def test_replace_input_is_single_revision_keeps_edge_id(self):
        n1=self.node('first','python.literal')
        n2=self.node('second','python.literal')
        target=self.node('ret','python.return')
        pin=target['ports']['inputs'][0]['id']
        src1=n1['ports']['outputs'][0]['id']
        src2=n2['ports']['outputs'][0]['id']
        self.commit('connect',id='wire',source='first',source_port=src1,target='ret',target_port=pin)
        revision=self.graph.revision
        self.commit('replace_input',source='second',source_port=src2,target='ret',target_port=pin)
        self.assertEqual(self.graph.revision,revision+1)
        self.assertEqual([(e['id'],e['source']) for e in self.graph.state['edges']],[('wire','second')])
        self.graph.undo(self.graph.revision)
        self.assertEqual(self.graph.state['edges'][0]['source'],'first')
        self.graph.redo(self.graph.revision)
        self.assertEqual(self.graph.state['edges'][0]['source'],'second')

    def test_replace_input_failure_does_not_disconnect_existing(self):
        first=self.node('first','python.literal')
        target=self.node('ret','python.return')
        pin=target['ports']['inputs'][0]['id']
        self.commit('connect',id='wire',source='first',source_port=first['ports']['outputs'][0]['id'],
                    target='ret',target_port=pin)
        for update in ({'source':'missing','source_port':'nope','target':'ret','target_port':pin},
                       {'source':'ret','source_port':pin,'target':'ret','target_port':pin},
                       {'source':'first','source_port':'missing','target':'ret','target_port':pin},
                       {'source':'first','source_port':first['ports']['outputs'][0]['id'],
                        'target':'ret','target_port':'absent'}):
            with self.subTest(update=update):
                before=self.graph.state
                with self.assertRaises(ProgramGraphError): self.commit('replace_input',**update)
                self.assertEqual(self.graph.state,before)

    def test_replace_input_noop_keeps_redo_stack(self):
        first=self.node('first','python.literal')
        target=self.node('ret','python.return')
        source=first['ports']['outputs'][0]['id']; pin=target['ports']['inputs'][0]['id']
        self.commit('connect',id='wire',source='first',source_port=source,target='ret',target_port=pin)
        self.commit('annotate',function='f',text='pending')
        self.graph.undo(self.graph.revision)
        revision=self.graph.revision
        self.assertFalse(self.commit('replace_input',source='first',source_port=source,target='ret',target_port=pin))
        self.assertEqual(self.graph.revision,revision)
        self.assertTrue(self.graph.redo(revision))

    def test_save_as_creates_new_identity_and_original_is_unchanged(self):
        self.node('lit','python.literal')
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder)/'original.smi-graph'; copy_path=Path(folder)/'copy.smi-graph'
            self.graph.save(base)
            raw=base.read_bytes()
            self.commit('set_property',node='lit',key='value',value=5)
            fork=self.graph.save_as(copy_path)
            self.assertEqual(base.read_bytes(),raw)
            self.assertEqual(self.graph.path,base)
            self.assertTrue(self.graph.dirty)
            self.assertEqual(fork.path,copy_path)
            self.assertNotEqual(self.graph.state['id'],fork.state['id'])
            self.assertEqual(fork.state['nodes'],self.graph.state['nodes'])
            self.assertEqual(fork.state['functions'],self.graph.state['functions'])
            self.assertFalse(fork.dirty)
            fork.undo(fork.revision)
            self.assertEqual(fork.state['nodes'],self.graph.state['nodes'])  # fork has no predecessor
            fork.edit(fork.revision,'add_parameter',function='f',name='next')
            self.assertEqual(len(self.graph.state['functions'][0]['parameters']),0)

    def test_save_as_refuses_collision_and_symlink_without_mutating_source(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder)/'original.smi-graph'; other=Path(folder)/'other.smi-graph'
            self.graph.save(base)
            other.write_text('leave alone')
            for path in (base,other):
                with self.assertRaises(GraphConflict): self.graph.save_as(path)
                self.assertEqual(self.graph.path,base)
            self.assertEqual(other.read_text(),'leave alone')
            link=Path(folder)/'linked.smi-graph';link.symlink_to(other)
            with self.assertRaises(GraphConflict):self.graph.save_as(link)
            self.assertTrue(link.is_symlink())

    def test_save_as_failure_preserves_dirty_unsaved_graph(self):
        self.node('lit','python.literal')
        before=self.graph.state
        with tempfile.TemporaryDirectory() as folder:
            missing=Path(folder)/'missing'/'graph.smi-graph'
            with self.assertRaises(ProgramGraphError):self.graph.save_as(missing)
            self.assertEqual(self.graph.state,before)
            self.assertIsNone(self.graph.path)
            self.assertTrue(self.graph.dirty)

    def test_stale_revision_rejects_both_interface_and_replacement(self):
        old=self.graph.revision
        self.commit('add_parameter',function='f',name='x')
        for action,kwargs in [('rename_function',{'function':'f','name':'changed'}),
                              ('set_property',{'node':'missing','key':'value','value':2})]:
            with self.assertRaises(GraphConflict):self.graph.edit(old,action,**kwargs)


class GuiContractTests(unittest.TestCase):
    def setUp(self):
        tree=ast.parse((ROOT/'studio_native/gui.py').read_text(encoding='utf-8'))
        self.workspace=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='ProgramWorkspace')
        self.methods={f.name:f for f in self.workspace.body if isinstance(f,ast.FunctionDef)}

    def test_editor_exposes_existing_authority_commands(self):
        for name in ('function_menu','rename_function','add_parameter','edit_parameter','edit_literal','save_as','connect'):
            self.assertIn(name,self.methods)
        source=ast.get_source_segment((ROOT/'studio_native/gui.py').read_text(),self.methods['connect'])
        self.assertIn("'replace_input' if occupied else 'connect'",source)

    def test_save_as_routes_to_program_document_not_legacy_draft(self):
        source=(ROOT/'studio_native/gui.py').read_text()
        self.assertIn('return program.save_as()',source)
        self.assertIn('fork=self.document.save_as(path)',source)
        self.assertIn('self.document=fork',source)

if __name__=='__main__':unittest.main()
