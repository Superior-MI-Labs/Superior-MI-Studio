# v0.9: source-aware value merges and label-contract regression.
import ast
import tempfile
import unittest
from pathlib import Path
from studio_native.python_graph import PythonDocument


class V09LoopDataTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'example.py'

    def graph(self,code):
        self.path.write_text(code,encoding='utf-8')
        doc=PythonDocument(self.path)
        key=next(k for k,s in doc.scopes.items() if s.title=='f')
        return doc.scope_graph(key)

    @staticmethod
    def one(g,title):
        return next(n for n in g['nodes'] if n['title']==title)

    @staticmethod
    def edge(g,src,dst,*,target_key=None):
        return next((e for e in g['edges'] if e['source']==src['id'] and
            e['target']==dst['id'] and (target_key is None or
            e['targetPort'].endswith(':'+target_key))),None)

    def test_while_initial_next_test_and_return_are_linked(self):
        g=self.graph('''def f(n):
    while n > 10:
        n -= 2
    return n
''')
        init=self.one(g,'PARAMETER n');carry=self.one(g,'LOOP VALUE n')
        update=self.one(g,'UPDATE n');test=self.one(g,'TEST');ret=self.one(g,'RETURN')
        self.assertTrue(self.edge(g,init,carry,target_key='initial'))
        self.assertTrue(self.edge(g,update,carry,target_key='next'))
        self.assertTrue(self.edge(g,carry,test,target_key='read:n'))
        self.assertTrue(self.edge(g,carry,update,target_key='previous'))
        self.assertTrue(self.edge(g,carry,ret,target_key='value'))
        self.assertEqual(carry['loop_value_semantics'],'initial_or_previous_iteration')
        self.assertFalse(any(n['title']=='UNCERTAIN n' for n in g['nodes']))

    def test_for_accumulator_is_seeded_but_item_not_assumed_bound(self):
        g=self.graph('''def f(xs):
    total = 0
    for x in xs:
        total += x
    return total
''')
        initial=self.one(g,'SET total');carry=self.one(g,'LOOP VALUE total')
        update=self.one(g,'UPDATE total');ret=self.one(g,'RETURN')
        self.assertTrue(self.edge(g,initial,carry,target_key='initial'))
        self.assertTrue(self.edge(g,update,carry,target_key='next'))
        self.assertTrue(self.edge(g,carry,ret,target_key='value'))
        loop=self.one(g,'FOR')
        self.assertTrue(self.edge(g,loop,update) or any(e['source']==loop['id'] and
                         e['target']==update['id'] for e in g['edges']))

    def test_ambiguous_conditional_loop_writer_keeps_uncertainty(self):
        g=self.graph('''def f(n):
    while n > 0:
        if n > 3:
            n -= 2
        else:
            n -= 1
    return n
''')
        carry=self.one(g,'LOOP VALUE n');test=self.one(g,'TEST');ret=self.one(g,'RETURN')
        uncertain=self.one(g,'UNCERTAIN n')
        self.assertTrue(self.edge(g,carry,test,target_key='read:n'))
        self.assertFalse(any(p['id'].endswith(':next') for p in carry['draft_ports']['inputs']))
        self.assertTrue(self.edge(g,uncertain,ret,target_key='value'))

    def test_zero_iterations_preserve_original_binding(self):
        g=self.graph('''def f(n):
    while False:
        n -= 1
    return n
''')
        self.assertFalse(any(n['title']=='LOOP VALUE n' for n in g['nodes']))
        self.assertTrue(self.edge(g,self.one(g,'PARAMETER n'),self.one(g,'RETURN'),target_key='value'))

    def test_unbound_conditional_read_resolves_scope_honestly(self):
        g=self.graph('''def f():
    while x > 0:
        x = x - 1
    return x
''')
        test=self.one(g,'TEST')
        self.assertTrue(any(e['target']==test['id'] and e['targetPort'].endswith(':read:x') for e in g['edges']))
        self.assertFalse(any(n['title']=='GLOBAL READ x' for n in g['nodes']))

    def test_nested_function_locals_do_not_leak_into_loop_state(self):
        g=self.graph('''def f(n):
    while n > 0:
        def helper():
            internal = 99
            return internal
        n -= 1
    return n
''')
        self.assertFalse(any(n['title'] in ('UNCERTAIN internal',
            'LOOP VALUE internal') for n in g['nodes']))

    def test_all_edges_have_real_ports(self):
        for sample in ('''def f(n):
    while n > 0:
        n -= 1
    return n
''','''def f(items):
    total = 0
    for x in items:
        total += x
    return total
'''):
            g=self.graph(sample);nodes={n['id']:n for n in g['nodes']}
            for edge in g['edges']:
                self.assertIn(edge['sourcePort'],{p['id'] for p in nodes[edge['source']]['draft_ports']['outputs']})
                self.assertIn(edge['targetPort'],{p['id'] for p in nodes[edge['target']]['draft_ports']['inputs']})


class PortLabelContractTests(unittest.TestCase):
    def test_port_item_uses_shared_measured_geometry(self):
        # Qt isn't installed in the headless build environment, so parse the
        # real source here; the native Qt smoke verifies pixel/hit geometry.
        path=Path(__file__).resolve().parents[1]/'studio_native/gui.py'
        tree=ast.parse(path.read_text(encoding='utf-8'))
        cls=next(c for c in tree.body if isinstance(c,ast.ClassDef) and c.name=='PortItem')
        methods={n.name:n for n in cls.body if isinstance(n,ast.FunctionDef)}
        self.assertIn('_label_geometry',methods)
        self.assertIn('paint',methods)
        self.assertIn('shape',methods)
        calls=lambda fn:[n.func.attr for n in ast.walk(methods[fn]) if
            isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)]
        self.assertIn('_label_geometry',calls('paint'))
        self.assertIn('_label_geometry',calls('shape'))
        self.assertIn('horizontalAdvance',calls('_label_geometry'))
        self.assertNotIn('label_rect',ast.unparse(cls))


if __name__=='__main__':unittest.main()
