"""Readability is a semantic projection contract, not a per-node UI hack.

No Qt or execution required: assert source identity, visible statement counts,
actual port/edge validity, binding semantics and exact edit spans.
"""
import ast
import tempfile
import unittest
from pathlib import Path

from studio_native.python_graph import PythonDocument
from studio_native.python_edit import change_literal, rewire_source_operand


class ReadableGraphTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path=Path(temp.name)/'example.py'

    def graphs(self,code, function='f'):
        self.path.write_text(code,encoding='utf-8')
        doc=PythonDocument(self.path)
        key=next(k for k,s in doc.scopes.items() if s.title==function)
        return doc,key,doc.scope_graph(key),doc.presentation_graph(key)

    @staticmethod
    def check_edges(g):
        nodes={n['id']:n for n in g['nodes']}
        assert len(nodes)==len(g['nodes'])
        for e in g['edges']:
            assert e['source'] in nodes and e['target'] in nodes, e
            assert e['sourcePort'] in {p['id'] for p in nodes[e['source']]['draft_ports']['outputs']}, e
            assert e['targetPort'] in {p['id'] for p in nodes[e['target']]['draft_ports']['inputs']}, e

    def test_simple_loop_is_four_real_nodes_and_five_grounded_edges(self):
        source='''def f(value):
    while value > 10:
        value -= 2
    return value
'''
        doc,key,analysis,display=self.graphs(source)
        self.assertEqual(len(analysis['nodes']),8)
        self.assertEqual(len(display['nodes']),4)
        self.assertEqual([n['title'] for n in display['nodes']],
                         ['PARAMETER value','WHILE value > 10','-=','RETURN'])
        self.assertEqual(len(display['edges']),4)
        self.assertEqual({n['source_kind'] for n in display['nodes']},
                         {'param','loop','assignment','return'})
        self.assertFalse(any(n['source_kind'] in {'entry','exit','loop_test','loop_value','literal'}
                             for n in display['nodes']))
        self.assertEqual(self.path.read_text(),source)
        self.assertEqual(doc.sha256,PythonDocument(self.path).sha256)
        self.check_edges(display)

    def test_simple_while_body_repeat_and_completed_are_control_edges(self):
        _,_,_,g=self.graphs('''def f(n):
    while n > 0:
        n -= 1
    return n
''')
        names={n['title']:n['id'] for n in g['nodes']}
        flow={(e['source'],e['target'],e['sourcePort'].split(':')[-1],
               e['targetPort'].split(':')[-1]) for e in g['edges'] if e['relation']=='control'}
        self.assertIn((names['WHILE n > 0'],names['-='],'body','in'),flow)
        self.assertNotIn((names['-='],names['WHILE n > 0'],'out','in'),flow)
        self.assertEqual(next(n for n in g['nodes'] if n['source_kind']=='loop')
                         .get('presentation_repeat'),'implicit_normal_completion')
        self.assertIn((names['WHILE n > 0'],names['RETURN'],'complete','in'),flow)
        self.assertFalse(any(e['targetPort'].endswith(':repeat') for e in g['edges']))

    def test_binding_references_are_not_frozen_value_edges(self):
        _,_,_,g=self.graphs('''def f(n):
    while n > 10:
        n -= 2
    return n
''')
        refs=[e for e in g['edges'] if e['relation']=='reference']
        self.assertEqual(len(refs),2)
        node_by_id={n['id']:n for n in g['nodes']}
        self.assertEqual({node_by_id[e['target']]['title'] for e in refs},
                         {'WHILE n > 10','-='})
        ret=next(n for n in g['nodes'] if n['source_kind']=='return')
        value=next(p for p in ret['draft_ports']['inputs'] if p['id'].endswith(':value'))
        self.assertEqual(value['inline_source_name'],'n')
        self.assertEqual(value['binding_mode'],'current_binding')
        self.assertFalse(any(e['target']==ret['id'] and e['relation']=='data' for e in g['edges']))

    def test_inline_literal_is_real_source_edit_target(self):
        code='''def f(n):
    while n > 10:
        n -= 2
    return n
'''
        doc,key,analysis,g=self.graphs(code)
        update=next(n for n in g['nodes'] if n['source_kind']=='assignment')
        rhs=next(p for p in update['draft_ports']['inputs'] if p['id'].endswith(':operand'))
        self.assertEqual(rhs['default'],2)
        self.assertEqual(rhs['source_literal_text'],'2')
        proposal=change_literal(doc,rhs['source_literal_span'],'3')
        self.assertIn('n -= 3',proposal.candidate.decode())
        self.assertEqual(self.path.read_text(),code)
        self.assertIn('n -= 3',proposal.diff)
        ast.parse(proposal.candidate)

    def test_rewiring_uses_unchanged_id_and_analysis_contract(self):
        doc,key,raw,g=self.graphs('''def f(n, other):
    while n > 10:
        n -= 2
    return n
''')
        param=next(n for n in g['nodes'] if n['title']=='PARAMETER other')
        update=next(n for n in g['nodes'] if n['source_kind']=='assignment')
        source=param['draft_ports']['outputs'][0]
        target=next(p for p in update['draft_ports']['inputs'] if p['id'].endswith(':operand'))
        self.assertIn(target['id'],{p['id'] for node in raw['nodes'] for p in node['draft_ports']['inputs']})
        # Loop-carried edits must still be refused by the original edit verifier.
        from studio_native.python_graph import SourceError
        with self.assertRaises(SourceError):
            rewire_source_operand(doc,key,param['id'],source['id'],update['id'],target['id'])

    def test_branch_join_is_not_a_user_node_but_keeps_both_paths(self):
        _,_,analysis,g=self.graphs('''def f(n):
    if n > 0:
        n = 1
    else:
        n = 2
    return n
''')
        self.assertTrue(any(n['source_kind']=='control_join' for n in analysis['nodes']))
        self.assertFalse(any(n['source_kind'] in ('control_join','value_merge') for n in g['nodes']))
        ret=next(n for n in g['nodes'] if n['source_kind']=='return')
        writes=[n for n in g['nodes'] if n['source_kind']=='assignment']
        self.assertEqual(len(writes),2)
        for write in writes:
            self.assertTrue(any(e['source']==write['id'] and e['target']==ret['id']
                                and e['relation']=='control' for e in g['edges']))
        self.check_edges(g)

    def test_ambiguous_loop_values_not_shown_as_fake_nodes(self):
        _,_,_,g=self.graphs('''def f(n):
    while n > 0:
        if n > 3:
            n -= 2
        else:
            n -= 1
    return n
''')
        self.assertFalse(any('LOOP VALUE' in n['title'] or 'UNCERTAIN' in n['title']
                             or 'MERGE' in n['title'] for n in g['nodes']))
        self.assertEqual(len([n for n in g['nodes'] if n['source_kind']=='assignment']),2)
        self.check_edges(g)

    def test_for_target_is_real_loop_binding_not_an_invented_read(self):
        _,_,_,g=self.graphs('''def f(items):
    total = 0
    for item in items:
        total += item
    return total
''')
        self.assertFalse(any(n['source_kind']=='loop_value' for n in g['nodes']))
        loop=next(n for n in g['nodes'] if n['source_kind']=='loop')
        update=next(n for n in g['nodes'] if n['source_kind']=='assignment' and n['title']=='+=' and n.get('binding_name')=='total')
        self.assertTrue(any(e['source']==loop['id'] and e['target']==update['id']
                            and e['relation'] in ('data','reference') for e in g['edges']))
        self.check_edges(g)

    def test_future_assignment_is_not_misread_as_loop_initial_binding(self):
        _,_,_,g=self.graphs('''def f():
    while x > 0:
        x = x - 1
    return x
''')
        loop=next(n for n in g['nodes'] if n['source_kind']=='loop')
        value=next(p for p in loop['draft_ports']['inputs'] if p['label']=='x')
        self.assertTrue(value.get('unresolved_binding'))
        self.assertFalse(any(e['target']==loop['id'] and e['targetPort']==value['id']
                             and e['relation']=='reference' for e in g['edges']))
        self.check_edges(g)

    def test_whole_file_expansion_uses_same_readable_projection(self):
        source='''def f(n):
    while n > 10:
        n -= 2
    return n
'''
        self.path.write_text(source,encoding='utf-8')
        doc=PythonDocument(self.path)
        analysis=doc.whole_file_graph(detail='analysis')
        readable=doc.whole_file_graph(detail='readable')
        self.assertLess(len(readable['nodes']),len(analysis['nodes']))
        self.assertEqual(len(readable['scope_regions']),len(analysis['scope_regions']))
        self.check_edges(readable)

    def test_view_is_pure_and_two_views_share_real_node_ids(self):
        doc,key,analysis,g=self.graphs('''def f(n):
    while n > 10:
        n -= 2
    return n
''')
        raw_ids={n['id'] for n in analysis['nodes']}
        self.assertTrue({n['id'] for n in g['nodes']} <= raw_ids)
        self.assertEqual(analysis,doc.scope_graph(key))
        self.assertEqual(g,doc.presentation_graph(key))
        self.assertEqual(doc.presentation_graph(key,detail='analysis'),analysis)


if __name__=='__main__':unittest.main()
