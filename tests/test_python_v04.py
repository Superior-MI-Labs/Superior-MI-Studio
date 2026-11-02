"""Semantic/presentation tests for the v0.4 Python whole-file & conditional pilot.

These are intentionally headless: a Qt smoke is a separate Linux host gate.
"""
import ast
from pathlib import Path
import tempfile
import unittest

from studio_native.python_graph import PythonDocument, SourceError


class V04GraphTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'scope_example.py'

    def graph(self, text, func='calc'):
        self.path.write_text(text,encoding='utf-8')
        doc=PythonDocument(self.path)
        key=next(k for k,v in doc.scopes.items() if v.title==func)
        return doc,doc.scope_graph(key)

    def test_compact_comparisons_true_false_and_merge(self):
        doc,g=self.graph('''def calc(a: int) -> int:
    if a > 5:
        total = a + 10
    else:
        total = a - 10
    return total
''')
        branches=[n for n in g['nodes'] if n['source_kind']=='branch']
        self.assertEqual(len(branches),1)
        branch=branches[0]
        self.assertEqual([p['label'] for p in branch['draft_ports']['outputs']],['true','false'])
        self.assertTrue(all(p['type']=='execution' for p in branch['draft_ports']['outputs']))
        comp=next(n for n in g['nodes'] if n['source_kind']=='compare')
        self.assertEqual(comp['display_symbol'],'>')
        self.assertEqual(comp['draft_ports']['outputs'][0]['type'],'py:bool')
        self.assertEqual(len([e for e in g['edges'] if e['target']==comp['id']]),2)
        self.assertEqual(sum(n['source_kind']=='control_join' for n in g['nodes']),1)
        merged=next(n for n in g['nodes'] if n['source_kind']=='value_merge' and n['title']=='MERGE total')
        self.assertEqual(len([e for e in g['edges'] if e['target']==merged['id']]),2)
        ret=next(n for n in g['nodes'] if n['source_kind']=='return')
        self.assertTrue(any(e['source']==merged['id'] and e['target']==ret['id'] for e in g['edges']))
        self.assertTrue(any(e['relation']=='control' for e in g['edges']))

    def test_elif_is_second_branch_not_opaque(self):
        doc,g=self.graph('''def calc(n):
    if n > 10:
        result = 1
    elif n > 5:
        result = 2
    else:
        result = 3
    return result
''')
        self.assertEqual(sum(n['source_kind']=='branch' for n in g['nodes']),2)
        self.assertEqual(sum(n['source_kind']=='compare' for n in g['nodes']),2)
        self.assertTrue(any(e['relation']=='control' for e in g['edges']))

    def test_comparison_chain_and_short_circuit_remain_source_backed(self):
        doc,g=self.graph('''def calc(a, b, c):
    if a() and b():
        return 1
    return a < b < c
''')
        self.assertTrue(any(n['source_kind']=='opaque' and n['title']=='BOOLOP' for n in g['nodes']))
        self.assertTrue(any(n['source_kind']=='opaque' and n['title']=='COMPARE' for n in g['nodes']))
        self.assertFalse(any(n['source_kind']=='call' for n in g['nodes']))
        self.assertIn('short-circuit',str([n['containers'] for n in g['nodes']]))

    def test_unsupported_branch_does_not_infer_a_successor(self):
        doc,g=self.graph('''def calc(a):
    if a:
        print('some side effect')
    else:
        x = 10
    return x
''')
        self.assertFalse(any(n['source_kind']=='value_merge' for n in g['nodes']))
        self.assertTrue(any('unresolved effects/control' in w for w in g['warnings']))
        self.assertFalse(any(n['source_kind']=='control_join' for n in g['nodes']))

    def test_missing_else_does_not_invent_defined_value(self):
        doc,g=self.graph('''def calc(a):
    if a:
        x = 10
    return x
''')
        self.assertFalse(any(n['source_kind']=='value_merge' for n in g['nodes']))
        self.assertTrue(any(n['source_kind']=='maybe-unbound local' and 'x' in n['title']
                            for n in g['nodes']))

    def test_annotation_types_are_not_runtime_value_pins(self):
        doc,g=self.graph('def calc(a: int) -> int:\n    return a\n')
        self.assertFalse(any(n['title']=='GLOBAL READ int' for n in g['nodes']))
        root=doc.scope_graph('module')
        f=next(n for n in root['nodes'] if n['source_kind']=='function')
        self.assertFalse(any('int' in p['label'] for p in f['draft_ports']['inputs']))

    def test_module_has_actual_call_link_and_transitive_global_reference(self):
        source='''tax = 3

def calc(a: int):
    def nested():
        return tax + a
    return nested()

if __name__ == '__main__':
    print(calc(8))
'''
        self.path.write_text(source,encoding='utf-8')
        doc=PythonDocument(self.path)
        root=doc.scope_graph('module')
        self.assertIn('call',{e['relation'] for e in root['edges']})
        self.assertIn('reference',{e['relation'] for e in root['edges']})
        self.assertTrue(any(e.get('indirect') is True for e in root['edges']))
        # Nested callable arguments are evaluated before their containing
        # call; only exact source-backed expression control edges are allowed.
        self.assertTrue(all((e['sourcePort'].endswith(':exec-out') or
                             e['sourcePort'].endswith(':true')) and
                            e['targetPort'].endswith(':exec-in')
                            for e in root['edges'] if e['relation']=='control'))
        for e in root['edges']:
            start=next(n for n in root['nodes'] if n['id']==e['source'])
            finish=next(n for n in root['nodes'] if n['id']==e['target'])
            self.assertTrue(any(p['id']==e['sourcePort'] for p in start['draft_ports']['outputs']))
            self.assertTrue(any(p['id']==e['targetPort'] for p in finish['draft_ports']['inputs']))

    def test_whole_graph_is_projection_without_duplicate_ids(self):
        source='''def calc(a):
    def one():
        def two():
            def three():
                def four():
                    return a + 1
                return four()
            return three()
        return two()
    return one()
'''
        self.path.write_text(source,encoding='utf-8')
        doc=PythonDocument(self.path)
        whole=doc.whole_file_graph()
        self.assertEqual(len(whole['scope_regions']),len(doc.scopes))
        self.assertEqual(len({n['id'] for n in whole['nodes']}),len(whole['nodes']))
        collapsed=doc.whole_file_graph(set())
        self.assertEqual(len(collapsed['scope_regions']),1)
        self.assertLess(len(collapsed['nodes']),len(whole['nodes']))
        keys=list(doc.scopes)
        only_child=doc.whole_file_graph({keys[-1]})
        self.assertEqual(len(only_child['scope_regions']),1)  # ancestor not expanded
        for edge in whole['edges']:
            self.assertIn(edge['source'],{n['id'] for n in whole['nodes']})
            self.assertIn(edge['target'],{n['id'] for n in whole['nodes']})

    def test_source_parse_does_not_run_top_level_import(self):
        side_effect=Path(self.temp.name)/'executed.txt'
        self.path.write_text(f'open({str(side_effect)!r},"w").write("bad")\n\ndef calc():\n    return 2\n',encoding='utf-8')
        doc=PythonDocument(self.path)
        doc.scope_graph('module');doc.whole_file_graph()
        self.assertFalse(side_effect.exists())

    def test_unknown_scope_and_budget_limit(self):
        doc,g=self.graph('def calc(a):\n    return a + 1\n')
        with self.assertRaises(SourceError):doc.whole_file_graph({'made-up-scope'})
        limited=doc.whole_file_graph(max_nodes=1)
        self.assertTrue(any('capped' in w for w in limited['warnings']))


if __name__ == '__main__':unittest.main()
