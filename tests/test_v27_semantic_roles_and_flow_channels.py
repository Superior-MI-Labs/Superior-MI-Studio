"""v2.7: adapter-owned invocation/definition roles and typed execution channels.

These tests verify source-graph evidence, not visual Qt qualification or an
execution engine. The renderer must not infer call effects or runtime order.
"""
import copy
import tempfile
import unittest
from pathlib import Path

from studio_native.python_graph import PythonDocument
from studio_native.semantic_contract import (
    ContractError, describe_graph, port_presentation_role,
)


class DefinitionAndInvocationContractTests(unittest.TestCase):
    def graph(self, source):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'source.py'
            path.write_text(source,encoding='utf-8')
            doc=PythonDocument(path)
            raw=doc.composite_file_graph(set(doc.scopes)-{'module'},detail='readable')
            return raw,describe_graph(raw,origin='source')

    def test_definition_without_call_has_no_invocation_or_control_pulse(self):
        raw,graph=self.graph('def f(x):\n    return x\n')
        defs=[n for n in graph.nodes if n.semantic_role=='definition']
        self.assertEqual(len(defs),1)
        self.assertFalse(any(n.semantic_role=='invocation' for n in graph.nodes))
        self.assertEqual(defs[0].interface.category,'function')
        return_port=defs[0].interface.exits[0].value_port
        self.assertEqual(port_presentation_role(defs[0],return_port),'definition-result-interface')
        self.assertFalse(any(e.relation=='control' and e.source_node==defs[0].id for e in graph.edges))
        self.assertEqual(len(raw['nodes']),len(graph.nodes))

    def test_call_result_is_not_definition_return(self):
        _,graph=self.graph('def f(x):\n    return x\n\nvalue = f(2)\n')
        definition=next(n for n in graph.nodes if n.semantic_role=='definition')
        invocation=next(n for n in graph.nodes if n.semantic_role=='invocation')
        result=next(p for p in invocation.ports if p.direction=='outputs')
        self.assertEqual(invocation.effect_verification,'unverified')
        self.assertEqual(port_presentation_role(invocation,result.id),'invocation-result')
        self.assertEqual(port_presentation_role(definition,definition.interface.exits[0].value_port),
                         'definition-result-interface')
        self.assertTrue(any(e.relation=='call' and e.source_node==definition.id and
                            e.target_node==invocation.id for e in graph.edges))
        self.assertFalse(any(e.relation=='data' and e.source_node==definition.id and
                             e.target_node==invocation.id for e in graph.edges))
        # Impure source invocations now expose source-backed evaluation flow.
        # The output VALUE still belongs to this call, not its definition.
        self.assertTrue(any(p.type_id=='execution' for p in invocation.ports))

    def test_nested_definition_time_control_is_not_function_entry(self):
        _,graph=self.graph('def outer(x):\n    def inner(y):\n        return y\n    return inner(x)\n')
        inner=next(n for n in graph.nodes if n.semantic_role=='definition' and n.title=='INNER')
        self.assertEqual(inner.interface.category,'function')
        controls=[p for p in inner.ports if p.type_id=='execution']
        self.assertEqual({p.label for p in controls},{'flow','next'})
        self.assertTrue(all(port_presentation_role(inner,p.id)=='definition-time-execution' for p in controls))
        # The readable graph deliberately hides bookkeeping ENTRY cards.
        # No wire from evaluating the nested definition may enter its body.
        self.assertFalse(any(e.source_node==inner.id and
                             e.target_node.startswith('py:'+inner.child_graph+'|entry')
                             for e in graph.edges))
        self.assertTrue(any(n.semantic_role=='invocation' for n in graph.nodes))

    def test_class_method_uses_same_definition_contract(self):
        _,graph=self.graph('class A:\n    def method(self):\n        return 7\n')
        method=next(n for n in graph.nodes if n.title=='METHOD')
        self.assertEqual(method.semantic_role,'definition')
        self.assertEqual(method.interface.category,'function')

    def test_effects_remain_unverified_for_unresolved_callee_and_nested_calls(self):
        _,graph=self.graph('def run(x):\n    return print(len(x))\n')
        calls=[n for n in graph.nodes if n.semantic_role=='invocation']
        self.assertEqual(len(calls),2)
        self.assertTrue(all(n.effect_verification=='unverified' for n in calls))
        self.assertFalse(any(p.type_id=='execution' for n in calls for p in n.ports))

    def test_unknown_source_adapter_can_expose_opaque_data_types(self):
        # Contract is deliberately language-neutral: source AST names and
        # Python type identifiers are not a requirement for a new producer.
        raw={'scope':'other:unit','nodes':[
            {'id':'foreign-definition','title':'fn','semantic_role':'definition',
             'draft_ports':{'inputs':[], 'outputs':[{'id':'r','label':'return','type':'rust:Result<T,E>'}]},
             'graph_interface':{'category':'function','inputs':[],'outputs':['r'],
                                'exits':[{'id':'exit','kind':'return','value_port':'r',
                                          'control_port':None,'sites':[]}]}},
            {'id':'foreign-call','title':'fn(…)','semantic_role':'invocation',
             'effect_verification':'unverified',
             'draft_ports':{'inputs':[], 'outputs':[{'id':'value','label':'result',
                                                  'type':'rust:Result<T,E>'}]}},
        ],'edges':[]}
        desc=describe_graph(raw,origin='source')
        self.assertEqual(port_presentation_role(desc.nodes[0],'r'),'definition-result-interface')
        self.assertEqual(port_presentation_role(desc.nodes[1],'value'),'invocation-result')
        self.assertEqual(len(desc.nodes),2)
        self.assertEqual(len(desc.edges),0)

    def test_reject_forged_semantic_roles_and_purity_claims(self):
        raw,_=self.graph('def f():\n    return 1\n\nf()\n')
        for role in ('invented','executed-definition'):
            bad=copy.deepcopy(raw)
            next(n for n in bad['nodes'] if n.get('semantic_role')=='definition')['semantic_role']=role
            with self.assertRaises(ContractError):describe_graph(bad,origin='source')
        bad=copy.deepcopy(raw)
        next(n for n in bad['nodes'] if n.get('semantic_role')=='invocation')['effect_verification']='verified-pure'
        with self.assertRaises(ContractError):describe_graph(bad,origin='source')
        bad=copy.deepcopy(raw)
        next(n for n in bad['nodes'] if n.get('graph_interface',{}).get('category')=='function')['semantic_role']='invocation'
        with self.assertRaises(ContractError):describe_graph(bad,origin='source')

    def test_malformed_data_control_and_call_edges_refused(self):
        raw,_=self.graph('def f(x):\n    y = x+1\n    return y\n')
        def mismatch(relation,source,source_port,target,target_port):
            bad=copy.deepcopy(raw)
            bad['edges']=[{'id':'wrong','source':source,'sourcePort':source_port,
                           'target':target,'targetPort':target_port,'relation':relation}]
            with self.assertRaises(ContractError):describe_graph(bad,origin='source')
        portnodes=[n for n in raw['nodes'] if n.get('draft_ports')]
        data_source=next((n,p) for n in portnodes for p in n['draft_ports']['outputs']
                         if p['type']!='execution')
        data_target=next((n,p) for n in portnodes for p in n['draft_ports']['inputs']
                         if p['type']!='execution')
        exec_source=next((n,p) for n in portnodes for p in n['draft_ports']['outputs']
                         if p['type']=='execution')
        exec_target=next((n,p) for n in portnodes for p in n['draft_ports']['inputs']
                         if p['type']=='execution')
        mismatch('control',data_source[0]['id'],data_source[1]['id'],data_target[0]['id'],data_target[1]['id'])
        mismatch('control',exec_source[0]['id'],exec_source[1]['id'],data_target[0]['id'],data_target[1]['id'])
        mismatch('data',exec_source[0]['id'],exec_source[1]['id'],exec_target[0]['id'],exec_target[1]['id'])
        mismatch('call',exec_source[0]['id'],exec_source[1]['id'],exec_target[0]['id'],exec_target[1]['id'])

    def test_invalid_port_identity_rejected_without_mutation(self):
        raw,graph=self.graph('def f(x):\n    return x\n')
        snapshot=copy.deepcopy(raw)
        definition=next(n for n in graph.nodes if n.semantic_role=='definition')
        with self.assertRaises(ContractError):port_presentation_role(definition,'fake')
        self.assertEqual(raw,snapshot)


if __name__=='__main__':
    unittest.main()
