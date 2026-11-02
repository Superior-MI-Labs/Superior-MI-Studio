"""v0.7: arm-local dominance, statement rewiring and honest loop boundaries.

No source file is executed during these tests. All edits are proposals until
explicitly committed, and loop projections never invent executable backedges.
"""
import tempfile
import unittest
from pathlib import Path

from studio_native.python_graph import PythonDocument, SourceError
from studio_native.python_edit import rewire_source_operand, apply_proposal


class V07Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'sample.py'

    def graph(self, source):
        self.path.write_text(source,encoding='utf-8')
        doc=PythonDocument(self.path)
        key=next(k for k,v in doc.scopes.items() if k!='module' and v.kind=='function')
        return doc,key,doc.scope_graph(key)

    def node(self, graph, kind, fragment=''):
        return next(n for n in graph['nodes'] if n['source_kind']==kind
                    and (fragment in n.get('subtitle','') or
                         any(fragment in str(r.get('value','')) for c in n.get('containers',[]) for r in c['rows'])))

    @staticmethod
    def pin(node, side, suffix=None):
        ports=node['draft_ports'][side]
        return (next(p['id'] for p in ports if p['id'].endswith(':'+suffix))
                if suffix is not None else ports[0]['id'])

    def edit(self, doc,key,src,dst,target_suffix='rhs'):
        return rewire_source_operand(doc,key,src['id'],self.pin(src,'outputs'),
                                     dst['id'],self.pin(dst,'inputs',target_suffix))

    def test_same_if_arm_local_assignment_can_rewire_comparison(self):
        source='''def choose(a):
    if a > 0:
        count = a + 4
        valid = a > 8
        return valid
    return False
'''
        doc,key,g=self.graph(source)
        src=self.node(g,'assignment','count = a + 4')
        target=self.node(g,'compare','a > 8')
        proposal=self.edit(doc,key,src,target)
        self.assertIn('valid = a > count',proposal.candidate.decode())
        self.assertEqual(self.path.read_text(),source)
        backup=apply_proposal(proposal)
        self.assertEqual(backup.read_text(),source)
        self.assertIn('valid = a > count',self.path.read_text())

    def test_same_else_arm_rewire(self):
        doc,key,g=self.graph('''def choose(a):
    if a:
        return 0
    else:
        count = 2
        ok = a > 4
        return ok
''')
        src=self.node(g,'assignment','count = 2')
        dst=self.node(g,'compare','a > 4')
        self.assertIn('a > count',self.edit(doc,key,src,dst).candidate.decode())

    def test_cross_branch_write_refused(self):
        doc,key,g=self.graph('''def choose(a):
    if a:
        count = 2
    else:
        ok = a > 4
    return 0
''')
        src=self.node(g,'assignment','count = 2')
        dst=self.node(g,'compare','a > 4')
        with self.assertRaisesRegex(SourceError,'different control-flow'):
            self.edit(doc,key,src,dst)

    def test_post_branch_write_refused_even_if_all_arms_assign(self):
        doc,key,g=self.graph('''def choose(a):
    if a:
        count = 2
    else:
        count = 3
    return a > 4
''')
        src=self.node(g,'assignment','count = 2')
        dst=self.node(g,'compare','a > 4')
        with self.assertRaises(SourceError):
            self.edit(doc,key,src,dst)

    def test_globals_not_treated_as_local(self):
        doc,key,g=self.graph('''x = 0
def choose(a):
    global x
    x = 2
    return a > 4
''')
        src=self.node(g,'assignment','x = 2')
        dst=self.node(g,'compare','a > 4')
        with self.assertRaisesRegex(SourceError,'Global/nonlocal'):
            self.edit(doc,key,src,dst)

    def test_local_rebinding_inside_arm_refused(self):
        doc,key,g=self.graph('''def choose(a):
    if a:
        x = 1
        x = 2
        return a > 5
    return False
''')
        src=self.node(g,'assignment','x = 1')
        dst=self.node(g,'compare','a > 5')
        with self.assertRaisesRegex(SourceError,'rebound'):
            self.edit(doc,key,src,dst)

    def test_parameter_to_return_value(self):
        doc,key,g=self.graph('''def choose(a):
    return a + 1
''')
        src=self.node(g,'param')
        dst=self.node(g,'return')
        p=self.edit(doc,key,src,dst,'value')
        self.assertIn('return a\n',p.candidate.decode())
        self.assertNotIn('return a\n',self.path.read_text())

    def test_literal_to_simple_assignment_value(self):
        doc,key,g=self.graph('''def choose(a):
    value = a + 2
    other = 9
    return value
''')
        src=self.node(g,'literal','9')
        dst=self.node(g,'assignment','value = a + 2')
        p=self.edit(doc,key,src,dst,'value')
        self.assertIn('value = 9',p.candidate.decode())

    def test_refuse_rewiring_control_pin(self):
        doc,key,g=self.graph('''def choose(a):
    b = 5
    return a + b
''')
        src=self.node(g,'param')
        dst=self.node(g,'return')
        with self.assertRaises(SourceError):
            self.edit(doc,key,src,dst,'in')

    def test_loop_boundaries_lower_real_statements_not_body_placeholders(self):
        doc,key,g=self.graph('''def choose(values):
    total = 0
    for item in values:
        total += item
    while total > 4:
        total -= 1
    return total
''')
        loops=[n for n in g['nodes'] if n['source_kind']=='loop']
        self.assertEqual({n['title'] for n in loops},{'FOR','WHILE'})
        self.assertFalse(any(n['title'].endswith(' BODY') for n in g['nodes']))
        self.assertEqual(sum(n['title']=='UPDATE total' for n in g['nodes']),2)
        self.assertTrue(all(n['loop_semantics']['normal_backedges']==1 for n in loops))
        self.assertTrue(all(any(e['target']==loop['id'] and e['targetPort'].endswith(':repeat')
                                and e['relation']=='control' for e in g['edges']) for loop in loops))
        self.assertTrue(all(any(e['source']==loop['id'] and e['sourcePort'].endswith(':body')
                                and e['relation']=='control' for e in g['edges']) for loop in loops))
        ret=self.node(g,'return')
        incoming=[e for e in g['edges'] if e['target']==ret['id'] and e['relation']=='data']
        self.assertEqual(len(incoming),1)
        self.assertEqual(next(n for n in g['nodes'] if n['id']==incoming[0]['source'])['title'],
                         'LOOP VALUE total')
        self.assertTrue(any('loop' in w.lower() for w in g['warnings']))

    def test_while_test_is_not_frozen_initial_value(self):
        doc,key,g=self.graph('''def countdown(n):
    while n > 0:
        n -= 1
    return n
''')
        loop=next(n for n in g['nodes'] if n['source_kind']=='loop')
        test=next(n for n in g['nodes'] if n['source_kind']=='loop_test')
        self.assertIn('n > 0',test['subtitle'])
        self.assertEqual(loop['loop_semantics']['condition_evaluation'],'per_iteration')
        self.assertTrue(any(e['source']==test['id'] and e['target']==loop['id'] for e in g['edges']))
        self.assertFalse(any(n['source_kind']=='compare' for n in g['nodes']))

    def test_loop_internal_set_is_visible_but_source_rewiring_after_loop_stays_refused(self):
        doc,key,g=self.graph('''def choose(a):
    for item in a:
        value = 3
    return a > 5
''')
        src=self.node(g,'assignment','value = 3')
        dst=self.node(g,'compare','a > 5')
        with self.assertRaises(SourceError):
            self.edit(doc,key,src,dst)
        self.assertFalse(any(n['title'].endswith(' BODY') for n in g['nodes']))


if __name__=='__main__':
    unittest.main()
