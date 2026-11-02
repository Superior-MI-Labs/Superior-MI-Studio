"""v0.8: executable CONTROL projection for a bounded set of Python loops.

The semantics are Python's normal sequential control transfers, not an
in-house runtime or source-generating 'WHILE BODY' abstraction.
Data dependencies across iteration remain explicitly uncertain.
"""
import tempfile
import unittest
from pathlib import Path
from studio_native.python_graph import PythonDocument, SourceError
from studio_native.python_edit import rewire_source_operand


class LoopControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'loop.py'

    def graph(self,body):
        self.path.write_text(body, encoding='utf-8')
        doc=PythonDocument(self.path)
        key=next(k for k,s in doc.scopes.items() if s.kind=='function' and k!='module')
        return doc,key,doc.scope_graph(key)

    @staticmethod
    def ids(g):
        return {n['id']:n for n in g['nodes']}

    @staticmethod
    def nodes(g,title):
        return [n for n in g['nodes'] if n['title']==title]

    @staticmethod
    def connected(g,a,b,relation='control',target_suffix=None):
        ids={n['id'] for n in a};targets={n['id'] for n in b}
        return any(e['relation']==relation and e['source'] in ids and e['target'] in targets
                   and (target_suffix is None or e['targetPort'].endswith(':'+target_suffix))
                   for e in g['edges'])

    def test_while_body_is_real_update_not_opaque_wrapper(self):
        _,_,g=self.graph('''def reduce(n):
    while n > 10:
        n -= 2
    return n
''')
        self.assertFalse(any('BODY' in n['title'] for n in g['nodes']))
        loop=self.nodes(g,'WHILE');update=self.nodes(g,'UPDATE n');ret=self.nodes(g,'RETURN')
        self.assertEqual(len(loop),1);self.assertEqual(len(update),1)
        self.assertTrue(self.connected(g,loop,update,target_suffix='in'))
        self.assertTrue(self.connected(g,update,loop,target_suffix='repeat'))
        self.assertTrue(self.connected(g,loop,ret,target_suffix='in'))
        self.assertEqual(loop[0]['loop_semantics']['normal_backedges'],1)
        self.assertEqual(loop[0]['loop_semantics']['condition_evaluation'],'per_iteration')

    def test_for_body_item_is_loop_output_and_backedge(self):
        _,_,g=self.graph('''def f(items):
    total = 0
    for item in items:
        total += item
    return total
''')
        loop=self.nodes(g,'FOR');update=self.nodes(g,'UPDATE total')
        self.assertTrue(self.connected(g,loop,update,'control','in'))
        self.assertTrue(self.connected(g,update,loop,'control','repeat'))
        self.assertTrue(any(e['source']==loop[0]['id'] and e['target']==update[0]['id']
                            and e['relation']=='data' and e['sourcePort'].endswith(':item')
                            for e in g['edges']))
        self.assertEqual([p['label'] for p in loop[0]['draft_ports']['outputs']],
                         ['body','completed','item'])

    def test_continue_resumes_nearest_loop_without_fallthrough(self):
        _,_,g=self.graph('''def f(items):
    x = 0
    for item in items:
        if item > 2:
            continue
        x += 1
    return x
''')
        loop=self.nodes(g,'FOR');cont=self.nodes(g,'CONTINUE');update=self.nodes(g,'UPDATE x')
        self.assertTrue(self.connected(g,cont,loop,'control','repeat'))
        self.assertFalse(self.connected(g,cont,update))
        self.assertEqual(loop[0]['loop_semantics']['continue_paths'],1)

    def test_break_bypasses_for_else_while_complete_runs_else(self):
        _,_,g=self.graph('''def f(items):
    x = 0
    for item in items:
        if item == 9:
            break
        x += 1
    else:
        x += 100
    return x
''')
        loop=self.nodes(g,'FOR');br=self.nodes(g,'BREAK')
        updates=self.nodes(g,'UPDATE x')
        self.assertEqual(len(updates),2)
        else_update=next(n for n in updates if n['source_span']['line']==8)
        self.assertTrue(self.connected(g,br,loop,'control','break'))
        self.assertTrue(self.connected(g,loop,[else_update],'control','in'))
        self.assertFalse(self.connected(g,br,[else_update]))
        joins=self.nodes(g,'MERGE')
        self.assertTrue(any(e['source']==loop[0]['id'] and e['sourcePort'].endswith(':broken')
                            and e['target'] in {n['id'] for n in joins} for e in g['edges']))
        self.assertEqual(loop[0]['loop_semantics']['break_paths'],1)

    def test_nested_break_targets_inner_not_outer(self):
        _,_,g=self.graph('''def f(xs,ys):
    for x in xs:
        for y in ys:
            break
        pass
    return 0
''')
        outer,inner=sorted(self.nodes(g,'FOR'),key=lambda n:n['source_span']['line'])
        br=self.nodes(g,'BREAK')
        self.assertTrue(self.connected(g,br,[inner],'control','break'))
        self.assertFalse(self.connected(g,br,[outer]))
        self.assertEqual(outer['loop_semantics']['break_paths'],0)
        self.assertEqual(inner['loop_semantics']['break_paths'],1)

    def test_while_true_no_fake_normal_completion(self):
        _,_,g=self.graph('''def f(n):
    while True:
        if n > 2:
            break
        n += 1
    return n
''')
        loop=self.nodes(g,'WHILE')[0]
        self.assertFalse(any(p['label']=='completed' for p in loop['draft_ports']['outputs']))
        self.assertTrue(any(p['label']=='broken' for p in loop['draft_ports']['outputs']))
        self.assertTrue(self.connected(g,[loop],self.nodes(g,'RETURN'),'control','in'))

    def test_while_false_has_no_body_and_preserves_old_binding(self):
        _,_,g=self.graph('''def f(n):
    x = 4
    while False:
        x += 5
    return x
''')
        self.assertFalse(self.nodes(g,'UPDATE x'))
        self.assertFalse(self.nodes(g,'UNCERTAIN x'))
        loop=self.nodes(g,'WHILE')[0]
        self.assertEqual(loop['loop_semantics']['normal_backedges'],0)
        self.assertFalse(any(p['label']=='body' for p in loop['draft_ports']['outputs']))
        self.assertTrue(self.connected(g,[loop],self.nodes(g,'RETURN'),'control','in'))

    def test_while_else_skip_on_break(self):
        _,_,g=self.graph('''def f(n):
    while n > 0:
        if n == 7:
            break
        n -= 1
    else:
        n = -1
    return n
''')
        loop=self.nodes(g,'WHILE')
        set_else=self.nodes(g,'SET n')
        self.assertTrue(self.connected(g,loop,set_else,'control','in'))
        self.assertFalse(self.connected(g,self.nodes(g,'BREAK'),set_else))

    def test_unsupported_async_for_does_not_invent_backedge(self):
        _,_,g=self.graph('''async def f(stream):
    async for value in stream:
        value += 1
    return 0
''')
        loop=self.nodes(g,'ASYNC FOR')[0]
        self.assertTrue(loop['loop_semantics']['source_backed'])
        self.assertFalse(any(e['target']==loop['id'] and e['targetPort'].endswith(':repeat')
                             for e in g['edges']))
        self.assertFalse(self.nodes(g,'UPDATE value'))

    def test_complex_target_for_stays_source_backed(self):
        _,_,g=self.graph('''def f(pairs):
    for a, b in pairs:
        pass
    return 1
''')
        loop=self.nodes(g,'FOR')[0]
        self.assertTrue(loop['loop_semantics']['source_backed'])
        self.assertFalse(any(p['label']=='body' for p in loop['draft_ports']['outputs']))
        self.assertFalse(self.nodes(g,'PASS'))

    def test_unresolved_body_refuses_to_invent_backedge(self):
        _,_,g=self.graph('''def f(n):
    while n > 0:
        raise RuntimeError('stop')
    return n
''')
        loop=self.nodes(g,'WHILE')[0]
        self.assertEqual(loop['loop_semantics']['normal_backedges'],0)
        self.assertFalse(any(e['target']==loop['id'] and e['targetPort'].endswith(':repeat')
                             for e in g['edges']))
        self.assertTrue(any('source-backed' in w for w in g['warnings']))

    def test_nested_conditional_loop_control_pin_integrity(self):
        _,_,g=self.graph('''def f(xs):
    result = 0
    for x in xs:
        if x > 4:
            if x == 8:
                break
            else:
                result += 1
        else:
            continue
    return result
''')
        byid=self.ids(g)
        for e in g['edges']:
            self.assertIn(e['source'],byid)
            self.assertIn(e['target'],byid)
            self.assertIn(e['sourcePort'],{p['id'] for p in byid[e['source']]['draft_ports']['outputs']})
            self.assertIn(e['targetPort'],{p['id'] for p in byid[e['target']]['draft_ports']['inputs']})
        self.assertFalse(any(n['title'].endswith(' BODY') for n in g['nodes']))
        self.assertGreaterEqual(len([e for e in g['edges'] if e['relation']=='control']),8)

    def test_source_rewire_inside_loop_remains_refused(self):
        doc,key,g=self.graph('''def f(n):
    while n > 0:
        n -= 1
        out = n + 2
    return n
''')
        source=self.nodes(g,'UPDATE n')[0]
        dst=next(n for n in g['nodes'] if n['source_kind']=='operation' and 'n + 2' in n['subtitle'])
        with self.assertRaises(SourceError):
            rewire_source_operand(doc,key,source['id'],source['draft_ports']['outputs'][0]['id'],
                                  dst['id'],dst['draft_ports']['inputs'][1]['id'])

if __name__=='__main__':unittest.main()

class GraphIdentityTests(unittest.TestCase):
    def test_nested_operators_have_unique_stable_ids_and_valid_edges(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'nested.py'
            path.write_text('''def f(a,b,c,d):
    result = a + b + c + d
    return result
''')
            doc=PythonDocument(path)
            key=next(k for k in doc.scopes if k!='module')
            graph=doc.scope_graph(key)
            operations=[n for n in graph['nodes'] if n['source_kind']=='operation']
            self.assertEqual(len(operations),3)
            self.assertEqual(len(set(n['id'] for n in operations)),3)
            byid={n['id']:n for n in graph['nodes']}
            self.assertEqual(len(byid),len(graph['nodes']))
            for edge in graph['edges']:
                self.assertIn(edge['sourcePort'],[p['id'] for p in byid[edge['source']]['draft_ports']['outputs']])
                self.assertIn(edge['targetPort'],[p['id'] for p in byid[edge['target']]['draft_ports']['inputs']])
            self.assertEqual({n['id'] for n in operations},
                             {n['id'] for n in doc.scope_graph(key)['nodes'] if n['source_kind']=='operation'})

    def test_all_bundled_samples_are_graph_identity_sound(self):
        examples=Path(__file__).resolve().parents[1]/'examples'
        for path in examples.glob('*.py'):
            doc=PythonDocument(path)
            projections=[doc.scope_graph(key) for key in doc.scopes]
            projections.append(doc.whole_file_graph())
            for graph in projections:
                with self.subTest(sample=path.name,scope=graph['scope']):
                    byid={n['id']:n for n in graph['nodes']}
                    self.assertEqual(len(byid),len(graph['nodes']))
                    for edge in graph['edges']:
                        self.assertIn(edge['source'],byid)
                        self.assertIn(edge['target'],byid)
                        self.assertIn(edge['sourcePort'],
                                      [p['id'] for p in byid[edge['source']]['draft_ports']['outputs']])
                        self.assertIn(edge['targetPort'],
                                      [p['id'] for p in byid[edge['target']]['draft_ports']['inputs']])
