"""Source/resource port rendering must stay bound to validated interface identities."""
from __future__ import annotations

import copy
import unittest

from studio_native.semantic_contract import ContractError, describe_graph, validated_port_payloads


def fixture(origin='source'):
    graph={'nodes':[{'id':'owner','title':'Adapter composite',
                     'draft_ports':{'inputs':[{'id':'b','label':'b','type':'py:int'},
                                              {'id':'a','label':'a','type':'execution'}],
                                    'outputs':[{'id':'out','label':'return','type':'py:int'}]}}],
           'edges':[]}
    return describe_graph(graph,origin=origin).nodes[0],graph['nodes'][0]


class DescriptorPortPresentationTests(unittest.TestCase):
    def test_contract_order_survives_raw_presentation_reorder(self):
        node, raw=fixture()
        raw['draft_ports']['inputs'].reverse()
        self.assertEqual(tuple(p['id'] for p in validated_port_payloads(node,raw,'inputs')),('b','a'))

    def test_same_boundary_pins_for_resource_adapter(self):
        node, raw=fixture('resource')
        self.assertEqual(tuple(p['id'] for p in validated_port_payloads(node,raw,'outputs')),('out',))

    def test_identity_mismatch_refuses_instead_of_guessing(self):
        node, raw=fixture()
        raw=copy.deepcopy(raw)
        raw['draft_ports']['inputs'][0]['id']='renamed'
        with self.assertRaisesRegex(ContractError,'identity changed'):
            validated_port_payloads(node,raw,'inputs')

    def test_changed_type_refuses_fake_execution_pin(self):
        node, raw=fixture()
        raw=copy.deepcopy(raw)
        raw['draft_ports']['inputs'][0]['type']='execution'
        with self.assertRaisesRegex(ContractError,'contract changed'):
            validated_port_payloads(node,raw,'inputs')

    def test_changed_label_refuses_stale_tooltip(self):
        node, raw=fixture()
        raw=copy.deepcopy(raw)
        raw['draft_ports']['outputs'][0]['label']='nowhere'
        with self.assertRaisesRegex(ContractError,'contract changed'):
            validated_port_payloads(node,raw,'outputs')

    def test_duplicate_refuses(self):
        node, raw=fixture()
        raw=copy.deepcopy(raw)
        raw['draft_ports']['inputs'][1]['id']='b'
        with self.assertRaisesRegex(ContractError,'Duplicate renderer port'):
            validated_port_payloads(node,raw,'inputs')

    def test_missing_refuses(self):
        node, raw=fixture()
        raw=copy.deepcopy(raw)
        raw['draft_ports']['inputs'].pop()
        with self.assertRaisesRegex(ContractError,'Port count changed'):
            validated_port_payloads(node,raw,'inputs')

    def test_wrong_direction_and_owner_refuse(self):
        node, raw=fixture()
        with self.assertRaises(ContractError):
            validated_port_payloads(node,raw,'other')
        raw['id']='other-owner'
        with self.assertRaises(ContractError):
            validated_port_payloads(node,raw,'inputs')


if __name__=='__main__': unittest.main()
