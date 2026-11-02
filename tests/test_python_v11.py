"""Source-first readable projection: variable bindings, return, and loop UX."""
import tempfile
import unittest
from pathlib import Path

from studio_native import model
from studio_native.python_graph import PythonDocument
from studio_native.python_edit import change_literal, rewire_source_operand


class BindingAndFlowReadabilityTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.file=Path(tmp.name)/'f.py'

    def graphs(self, source):
        self.file.write_text(source,encoding='utf-8')
        doc=PythonDocument(self.file)
        key=next(k for k,s in doc.scopes.items() if s.kind=='function')
        return doc,key,doc.scope_graph(key),doc.presentation_graph(key)

    def assert_graph_integrity(self,g):
        by_id={n['id']:n for n in g['nodes']}
        self.assertEqual(len(by_id),len(g['nodes']))
        for e in g['edges']:
            self.assertIn(e['source'],by_id)
            self.assertIn(e['target'],by_id)
            self.assertIn(e['sourcePort'],{p['id'] for p in by_id[e['source']]['draft_ports']['outputs']})
            self.assertIn(e['targetPort'],{p['id'] for p in by_id[e['target']]['draft_ports']['inputs']})

    def test_three_variables_add_then_return_is_five_source_nodes(self):
        code='''def myDef():
    a = "a"
    b = "b"
    c = a + b
    return c
'''
        doc,key,raw,g=self.graphs(code)
        self.assertEqual([n['title'] for n in g['nodes']],['a','b','ADD','c','RETURN'])
        by_title={n['title']:n for n in g['nodes']}
        self.assertEqual([by_title[n]['binding_write_mode'] for n in ('a','b','c')],['initial']*3)
        self.assertEqual([by_title[n]['binding_name'] for n in ('a','b','c')],['a','b','c'])
        self.assertEqual(by_title['RETURN']['return_binding'],'c')
        self.assertEqual(by_title['RETURN']['draft_ports']['inputs'][0]['label'],'c')
        connected={(e['source'],e['target']) for e in g['edges'] if e['relation']=='data'}
        self.assertEqual(connected,{(by_title[a]['id'],by_title[b]['id']) for a,b in
                                   [('a','ADD'),('b','ADD'),('ADD','c'),('c','RETURN')]})
        self.assertLess(by_title['a']['x'],by_title['ADD']['x'])
        self.assertLess(by_title['ADD']['x'],by_title['c']['x'])
        self.assertLess(by_title['c']['x'],by_title['RETURN']['x'])
        self.assertEqual(doc.scope_graph(key),raw)
        self.assertEqual(self.file.read_text(),code)
        self.assert_graph_integrity(g)

    def test_literal_fields_keep_authored_quote_style(self):
        code="def f():\n    a = 'alpha'\n    b = \"beta\"\n    return b\n"
        _,_,_,g=self.graphs(code)
        nodes={n['title']:n for n in g['nodes']}
        a,b=(nodes[n]['draft_ports']['inputs'][0] for n in ('a','b'))
        self.assertEqual(model.format_input_default(a),"'alpha'")
        self.assertEqual(model.format_input_default(b),'"beta"')
        self.assertEqual(a['default'],'alpha')
        self.assertEqual(b['default'],'beta')
        self.assert_graph_integrity(g)

    def test_inline_binding_literal_can_still_be_edited(self):
        doc,_,_,g=self.graphs('def f():\n    a = "abc"\n    return a\n')
        p=next(n for n in g['nodes'] if n['title']=='a')['draft_ports']['inputs'][0]
        proposal=change_literal(doc,p['source_literal_span'],'"changed"')
        self.assertIn('a = "changed"',proposal.candidate.decode())
        self.assertEqual(self.file.read_text(),'def f():\n    a = "abc"\n    return a\n')

    def test_parameter_reassignment_is_not_new_variable(self):
        _,_,_,g=self.graphs('def f(a):\n    a = 2\n    return a\n')
        n=next(n for n in g['nodes'] if n['source_kind']=='assignment')
        self.assertEqual(n['title'],'SET a')
        self.assertEqual(n['binding_write_mode'],'reassign')

    def test_subsequent_local_reassignment_is_not_second_initialization(self):
        _,_,_,g=self.graphs('def f():\n    a = 1\n    a = 2\n    return a\n')
        nodes=[n for n in g['nodes'] if n['source_kind']=='assignment']
        self.assertEqual([(n['title'],n['binding_write_mode']) for n in nodes],
                         [('a','initial'),('SET a','reassign')])
        self.assert_graph_integrity(g)

    def test_conditional_assignment_not_misclassified_as_unconditional_initialization(self):
        _,_,_,g=self.graphs('def f(flag):\n    if flag:\n        x = 1\n    x = 2\n    return x\n')
        nodes=[n for n in g['nodes'] if n['source_kind']=='assignment']
        self.assertEqual([n['binding_write_mode'] for n in nodes],['reassign','reassign'])
        self.assert_graph_integrity(g)

    def test_loop_has_one_control_entry_and_implicit_repeat(self):
        code='''def accumulate(items):
    total = 0
    for item in items:
        total += item
    return total
'''
        doc,key,raw,g=self.graphs(code)
        self.assertEqual([n['title'] for n in g['nodes']],
                         ['PARAMETER items','total','FOR item','+=','RETURN'])
        loop=next(n for n in g['nodes'] if n['source_kind']=='loop')
        self.assertEqual(loop['presentation_repeat'],'implicit_normal_completion')
        self.assertFalse(any(p['id'].endswith(':repeat') for p in loop['draft_ports']['inputs']))
        self.assertFalse(any(e['targetPort'].endswith(':repeat') for e in g['edges']))
        analysis_loop=next(n for n in raw['nodes'] if n['id']==loop['id'])
        self.assertTrue(any(p['id'].endswith(':repeat') for p in analysis_loop['draft_ports']['inputs']))
        total=next(n for n in g['nodes'] if n['title']=='total')
        update=next(n for n in g['nodes'] if n['title']=='+=' and n.get('binding_name')=='total')
        self.assertTrue(any(e['source']==total['id'] and e['target']==update['id']
                            and e['relation']=='reference' for e in g['edges']))
        self.assertFalse(any(e['source']==update['id'] and e['target']==loop['id']
                             and e['relation']=='control' for e in g['edges']))
        self.assertTrue(any(e['source']==loop['id'] and e['target']==update['id']
                            and e['relation']=='control' for e in g['edges']))
        self.assert_graph_integrity(g)

    def test_continue_is_explicit_control_transfer_without_repeat_port(self):
        code='''def f(items):
    for item in items:
        if item == 0:
            continue
        print(item)
    return 1
'''
        _,_,_,g=self.graphs(code)
        loop=next(n for n in g['nodes'] if n['source_kind']=='loop')
        continues=[n for n in g['nodes'] if n['source_kind']=='continue']
        self.assertEqual(len(continues),1)
        self.assertTrue(any(e['source']==continues[0]['id'] and e['target']==loop['id']
                            and e['flow_role']=='continue' and e['targetPort'].endswith(':in')
                            for e in g['edges']))
        self.assert_graph_integrity(g)

    def test_global_assignment_is_a_write_not_a_new_local_binding(self):
        _,_,_,g=self.graphs('x = 0\ndef f():\n    global x\n    x = 2\n    return x\n')
        n=next(n for n in g['nodes'] if n['source_kind']=='assignment')
        self.assertEqual(n['title'],'SET x')
        self.assertEqual(n['binding_write_mode'],'reassign')

    def test_source_edit_validator_accepts_initial_binding_as_source(self):
        code='''def f():
    a = 3
    b = 5
    return a + b
'''
        doc,key,_,g=self.graphs(code)
        source=next(n for n in g['nodes'] if n.get('binding_name')=='a')
        target=next(n for n in g['nodes'] if n['source_kind']=='operation')
        port=target['draft_ports']['inputs'][1]
        try:
            proposal=rewire_source_operand(doc,key,source['id'],
                                            source['draft_ports']['outputs'][0]['id'],
                                            target['id'],port['id'])
        except Exception as exc:
            self.fail(f'Renamed first-binding projection broke validated rewiring: {exc}')
        self.assertIn('return a + a',proposal.candidate.decode())
        self.assert_graph_integrity(g)


    def test_imported_name_reassignment_is_not_a_new_local_declaration(self):
        _,_,_,g=self.graphs('def f():\n    import math as m\n    m = 2\n    return m\n')
        node=next(n for n in g['nodes'] if n.get('binding_name')=='m')
        self.assertEqual(node['binding_write_mode'],'reassign')

    def test_annotation_without_value_does_not_create_runtime_binding(self):
        _,_,_,g=self.graphs('def f():\n    x: int\n    x = 2\n    return x\n')
        node=next(n for n in g['nodes'] if n.get('binding_name')=='x')
        self.assertEqual(node['binding_write_mode'],'initial')

    def test_unpacking_before_single_assignment_blocks_first_binding_claim(self):
        _,_,_,g=self.graphs('def f():\n    a, b = (1, 2)\n    a = 3\n    return a\n')
        node=next(n for n in g['nodes'] if n.get('binding_name')=='a')
        self.assertEqual(node['binding_write_mode'],'reassign')

    def test_nested_definition_prior_name_is_binding_not_initialization(self):
        _,_,_,g=self.graphs('def f():\n    def inner():\n        return 1\n    inner = 5\n    return inner\n')
        node=next(n for n in g['nodes'] if n.get('binding_name')=='inner')
        self.assertEqual(node['binding_write_mode'],'reassign')

    def test_while_implicit_repetition_and_break_paths_survive_projection(self):
        _,_,raw,g=self.graphs('def f(n):\n    while n > 0:\n        if n == 2:\n            break\n        n -= 1\n    return n\n')
        loop=next(n for n in g['nodes'] if n['source_kind']=='loop')
        break_node=next(n for n in g['nodes'] if n['source_kind']=='break')
        self.assertFalse(any(p['id'].endswith(':repeat') for p in loop['draft_ports']['inputs']))
        self.assertTrue(any(e['source']==break_node['id'] and e['target']==loop['id']
                            and e['targetPort'].endswith(':break') for e in g['edges']))
        self.assertTrue(any(e['targetPort'].endswith(':repeat') for e in raw['edges']))
        self.assert_graph_integrity(g)

if __name__=='__main__':unittest.main()
