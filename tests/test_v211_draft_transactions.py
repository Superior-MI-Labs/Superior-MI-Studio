"""Draft mutations must be atomic and return a fresh shared descriptor snapshot."""
from __future__ import annotations
import copy
import unittest
from studio_native import model as m
from studio_native.semantic_contract import describe_graph, validated_port_payloads


class DraftTransactionTests(unittest.TestCase):
    def setUp(self):
        self.state=m.new_state()
        self.before=copy.deepcopy(self.state)
        self.first=self.state['nodes'][0]

    def test_new_pin_publishes_new_validated_descriptor(self):
        pin=m.port('extra','f64')
        newer=m.transaction(self.state, lambda s: m.find_node(s,self.first['id'])['draft_ports']['inputs'].append(pin))
        self.assertEqual(self.state,self.before)
        desc=describe_graph(newer,origin='draft').nodes[0]
        self.assertIn(pin['id'],[p.id for p in desc.ports])
        self.assertEqual(validated_port_payloads(desc,newer['nodes'][0],'inputs')[-1]['id'],pin['id'])

    def test_invalid_edit_is_atomic(self):
        with self.assertRaisesRegex(ValueError,'Invalid port'):
            m.transaction(self.state, lambda s: m.find_node(s,self.first['id'])['draft_ports']['inputs'][0].update(type='made-up'))
        self.assertEqual(self.state,self.before)

    def test_duplicate_port_identity_rolls_back(self):
        def duplicate(s):
            pins=s['nodes'][0]['draft_ports']['inputs']
            pins[1]['id']=pins[0]['id']
        with self.assertRaisesRegex(ValueError,'duplicate port'):
            m.transaction(self.state,duplicate)
        self.assertEqual(self.state,self.before)

    def test_connection_preserves_existing_state_until_commit(self):
        first,second=self.state['nodes'][:2]
        output=first['draft_ports']['outputs'][0]['id']
        target=second['draft_ports']['inputs'][1]['id']
        result=m.transaction(self.state,lambda s: m.connect(s,first['id'],output,second['id'],target))
        self.assertEqual(len(result['edges']),2)
        self.assertEqual(len(self.state['edges']),1)
        self.assertEqual(len(describe_graph(result,origin='draft').edges),2)

    def test_invalid_channel_does_not_publish(self):
        target=self.state['nodes'][1]['draft_ports']['inputs'][0]
        # A data edge cannot be painted between execution pins.
        with self.assertRaisesRegex(ValueError,'Control|execution|mismatch'):
            m.transaction(self.state,lambda s: s['nodes'][1]['draft_ports']['inputs'][0].update(type='execution'))
        self.assertEqual(self.state,self.before)

    def test_edit_disconnects_incompatible_edge_then_validates(self):
        first,second=self.state['nodes'][:2]
        old_target=second['draft_ports']['inputs'][0]['id']
        def edit(s):
            m.find_node(s,second['id'])['draft_ports']['inputs'][0]['type']='f64'
            s['edges'][:]=[e for e in s['edges'] if e['targetPort']!=old_target]
        result=m.transaction(self.state,edit)
        self.assertEqual(result['edges'],[])
        self.assertEqual(len(self.state['edges']),1)

    def test_undeclared_type_mismatch_in_loaded_draft_refuses(self):
        malformed=copy.deepcopy(self.state)
        malformed['nodes'][1]['draft_ports']['inputs'][0]['type']='string'
        self.assertIn('Connected port type mismatch',m.validate(malformed))
        with self.assertRaisesRegex(ValueError,'Connected port type mismatch'):
            m.transaction(malformed,lambda s:None)

    def test_duplicate_incoming_edge_is_rejected(self):
        malformed=copy.deepcopy(self.state)
        edge=copy.deepcopy(malformed['edges'][0]);edge['id']='another-edge'
        malformed['edges'].append(edge)
        self.assertIn('Input already connected',m.validate(malformed))

    def test_unexpected_exception_never_publishes(self):
        def explode(s):
            s['nodes'].clear()
            raise RuntimeError('failure')
        with self.assertRaises(RuntimeError):m.transaction(self.state,explode)
        self.assertEqual(self.state,self.before)

    def test_title_edit_refreshes_contract_appearance(self):
        revised=m.transaction(self.state,lambda s: s['nodes'][0].update(title='Renamed'))
        desc=describe_graph(revised,origin='draft').nodes[0]
        self.assertEqual(desc.appearance.title,'Renamed')
        self.assertEqual(self.first['title'],self.before['nodes'][0]['title'])

    def test_source_graph_cannot_be_mistaken_for_draft(self):
        # The mutation contract intentionally validates prototype draft state.
        from studio_native.python_graph import PythonDocument
        graph=PythonDocument('examples/python-scope-demo.py').scope_graph('module')
        with self.assertRaisesRegex(ValueError,'Unrecognized'):
            m.transaction(graph,lambda s:None)


if __name__=='__main__': unittest.main()
