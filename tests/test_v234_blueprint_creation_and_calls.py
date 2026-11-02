"""Source-qualified creation search and module nested call semantics.

No Qt import: assertions independently verify the source adapter and action
planner before native GUI smoke exercises the Qt presentation on Mint.
"""
from pathlib import Path
import tempfile
import unittest
from studio_native.python_graph import PythonDocument, SourceError
from studio_native.python_edit import apply_proposal
from studio_native.python_authoring import (
    eligible_pass_targets, compatible_parameter_pin, propose_return_parameter_from_pass)
from studio_native.authoring_actions import available_actions, search_actions
from studio_native.semantic_contract import describe_graph


class BlueprintCreationAndModuleCalls(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'src.py'

    def source(self,body):
        self.path.write_text(body,encoding='utf-8')
        return PythonDocument(self.path)

    def test_search_and_library_share_one_qualified_source(self):
        doc=self.source('def passthrough(value):\n    pass\n')
        actions=available_actions(doc)
        ids={a.id for a in actions}
        self.assertTrue({'python.return-from-pass.v1','python.return-parameter-from-pass.v1',
                               'python.arithmetic-return-from-pass.v1','python.create-function.v1',
                               'python.add-optional-keyword-parameter.v1'}.issubset(ids))
        self.assertEqual([a.id for a in search_actions(actions,'parameter RETURN')],
                         ['python.return-parameter-from-pass.v1',
                          'python.arithmetic-return-from-pass.v1'])
        self.assertEqual(search_actions(actions,'does-not-exist'),())

    def test_parameter_pin_is_exact_adapter_identity_not_just_a_matching_type(self):
        doc=self.source('def f(value, *items):\n    pass\n')
        scope,anchor=eligible_pass_targets(doc)[0]
        node=f'py:{scope}|param|value';port=node+':outputs:value'
        matches=compatible_parameter_pin(doc,node,port)
        self.assertEqual(matches,((scope,'value',anchor),))
        choices=available_actions(doc,pin=(node,port))
        self.assertEqual(len(choices),5)
        self.assertEqual((choices[0].source_scope,choices[0].parameter),(scope,'value'))
        self.assertEqual(available_actions(doc,pin=(node,port+':bogus')),())
        self.assertEqual(available_actions(doc,pin=('any-other-node',port)),())
        self.assertEqual(available_actions(doc,pin=(node,'some:execution:pin')),())

    def test_parameter_return_round_trip_produces_true_data_connection(self):
        doc=self.source('def f(value):\n    pass\n')
        scope,anchor=eligible_pass_targets(doc)[0]
        proposal=propose_return_parameter_from_pass(doc,scope,'value',anchor)
        self.assertEqual(self.path.read_bytes(),doc.raw,'Proposal must not save until approved')
        self.assertIn('return value',proposal.candidate.decode('utf-8'))
        apply_proposal(proposal)
        fresh=PythonDocument(self.path)
        g=fresh.scope_graph(scope)
        desc=describe_graph(g,origin='source')
        param=next(n for n in g['nodes'] if n['source_kind']=='param')
        ret=next(n for n in g['nodes'] if n['source_kind']=='return')
        self.assertTrue(any(e['source']==param['id'] and e['target']==ret['id'] and
                            e['relation']=='data' for e in g['edges']))
        self.assertEqual(len(desc.nodes),len(g['nodes']))

    def test_wrong_parameters_and_stale_anchors_refused(self):
        doc=self.source('def f(value):\n    pass\n')
        scope,anchor=eligible_pass_targets(doc)[0]
        with self.assertRaises(SourceError):
            propose_return_parameter_from_pass(doc,scope,'not_declared',anchor)
        with self.assertRaises(SourceError):
            propose_return_parameter_from_pass(doc,scope,'value',dict(anchor,line=anchor['line']+1))
        self.assertEqual(self.path.read_bytes(),doc.raw)

    def test_module_nested_calls_expose_arguments_and_order(self):
        doc=self.source("def choose(a,b): return a\n"
            "def nested_expression(a,b,c,d): return a\n"
            "def early_exit(a): return a\n"
            "if __name__ == '__main__':\n"
            "    print(choose(3, 9))\n"
            "    print(nested_expression(1, 2, 3, 4))\n"
            "    print(early_exit(-1))\n")
        g=doc.scope_graph()
        d=describe_graph(g,origin='source')
        guard=next(n for n in g['nodes'] if n.get('semantic_role')=='control_operation')
        self.assertEqual(next(n for n in d.nodes if n.id==guard['id']).operation_kind,'branch')
        self.assertEqual(guard['source_guard_test'],"__name__ == '__main__'")
        invocations=[n for n in g['nodes'] if n.get('call_expression')]
        self.assertEqual(len(invocations),6)
        for inner_name,expect in [('choose',['3','9']),('nested_expression',['1','2','3','4']),
                                  ('early_exit',['-1'])]:
            inner=next(n for n in invocations if n.get('call_direct_name')==inner_name)
            inputs=[p for p in inner['draft_ports']['inputs'] if p['id'].split(':inputs:')[-1].startswith('arg:')]
            self.assertEqual([p['source_expression_preview'] for p in inputs],expect)
            outer=next(n for n in invocations if n.get('call_direct_name')=='print'
                       and n['source_span']['line']==inner['source_span']['line'])
            self.assertTrue(any(e['relation']=='data' and e['source']==inner['id'] and
                                e['target']==outer['id'] for e in g['edges']))
            self.assertTrue(any(e['relation']=='control' and e['source']==inner['id'] and
                                e['target']==outer['id'] for e in g['edges']))
            self.assertLess(inner['x'],outer['x'])
            self.assertEqual(inner['y'],outer['y'])
        self.assertEqual(len(g['edges']),len(d.edges))
        self.assertTrue(any(e['source']==guard['id'] and e['relation']=='control'
                            for e in g['edges']))

    def test_complex_module_call_is_not_assigned_invented_exec_wires(self):
        doc=self.source("if flag:\n    print((lambda x: x)(compute()))\n    print('done')\n")
        g=doc.scope_graph()
        self.assertFalse(any(n.get('semantic_role')=='control_operation' for n in g['nodes']))
        self.assertFalse(any(e['relation']=='control' for e in g['edges']))
        self.assertEqual(len(describe_graph(g,origin='source').nodes),len(g['nodes']))

    def test_module_call_arguments_have_stable_identity_and_source_preview(self):
        doc=self.source("print(choose(3, 9))\n")
        before=doc.scope_graph()
        after=PythonDocument(self.path).scope_graph()
        b={n['id']:n for n in before['nodes'] if n.get('call_expression')}
        a={n['id']:n for n in after['nodes'] if n.get('call_expression')}
        self.assertEqual(set(a),set(b))
        for identity in a:
            self.assertEqual([p['id'] for p in a[identity]['draft_ports']['inputs']],
                             [p['id'] for p in b[identity]['draft_ports']['inputs']])
        self.assertTrue(any(p.get('source_literal_text')=='3' for n in b.values()
                            for p in n['draft_ports']['inputs']))

    def test_persistent_palette_search_filters_same_operation_definitions(self):
        source=(Path(__file__).parents[1]/'studio_native/gui.py').read_text()
        self.assertIn("self.source_operation_search.setObjectName('SourceLibrarySearch')",source)
        self.assertIn('self.source_operation_search.textChanged.connect(self._refresh_operation_library)',source)
        self.assertIn("catalog={entry.id:entry for entry in qualified_operations('python')}",source)
        self.assertIn('button.setVisible(not query',source)

    def test_all_creation_surfaces_are_wired_to_same_adapter_operation_id(self):
        gui=(Path(__file__).parents[1]/'studio_native/gui.py').read_text()
        self.assertIn('open_creation_menu',gui)
        self.assertIn('available_actions(self.python_doc,pin=pin)',gui)
        self.assertIn('self._create_qualified_operation(action.id,pin=pin',gui)
        self.assertIn('propose_return_parameter_from_pass',gui)
        self.assertIn('self.review_source_proposal(proposal)',gui)
        self.assertIn('QualifiedGraphCreationSearch',gui)
        self.assertNotIn('eval(',gui)


if __name__=='__main__':unittest.main()
