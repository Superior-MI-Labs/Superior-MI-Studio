"""Source constructs and nested regions, not extra display-only operations."""
import tempfile
import unittest
from pathlib import Path
from studio_native.python_graph import PythonDocument
from studio_native.python_edit import change_literal
from studio_native.graph_layout import node_size

SOURCE='''def accumulate(items):
    total = 0
    for item in items:
        if item > 0:
            total += item
        else:
            total -= 2
    return total
'''

class ConstructProjectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'source.py'
        self.path.write_text(SOURCE)
        self.doc=PythonDocument(self.path)
        self.key=next(k for k,s in self.doc.scopes.items() if s.title=='accumulate')

    def test_if_is_source_if_not_generic_branch_in_readable(self):
        analysis=self.doc.scope_graph(self.key)
        readable=self.doc.presentation_graph(self.key)
        a=next(n for n in analysis['nodes'] if n['source_kind']=='branch')
        r=next(n for n in readable['nodes'] if n['id']==a['id'])
        self.assertEqual(a['title'],'BRANCH')
        self.assertEqual(r['title'],'IF item > 0')
        self.assertEqual(r['source_construct'],'conditional')
        self.assertEqual(r['semantic_role'],'control_operation')
        self.assertEqual([p['label'] for p in r['draft_ports']['outputs']],['true','false'])
        self.assertEqual({n['id'] for n in analysis['nodes'] if n['source_kind']=='branch'},
                         {n['id'] for n in readable['nodes'] if n['source_kind']=='branch'})

    def test_augmented_assignment_is_operator_not_duplicate_set(self):
        readable=self.doc.presentation_graph(self.key)
        updates=[n for n in readable['nodes'] if n.get('source_construct')=='augmented_assignment']
        self.assertEqual({n['title'] for n in updates},{'+=','-='})
        self.assertEqual({n['binding_name'] for n in updates},{'total'})
        self.assertEqual({n['visual_family'] for n in updates},{'operator_assignment'})
        for node in updates:
            self.assertLessEqual(node_size(node)[0],160)
            previous=next(p for p in node['draft_ports']['inputs'] if p['id'].endswith(':previous'))
            self.assertEqual(previous['label'],'total')
            self.assertEqual(previous['binding_mode'],'current_binding')
            self.assertTrue(any(e['target']==node['id'] and e['targetPort']==previous['id']
                                and e['relation']=='reference' for e in readable['edges']))
        # One real initial variable, no extra SET created for the augmented writes.
        initial=[n for n in readable['nodes'] if n.get('binding_write_mode')=='initial'
                 and n.get('binding_name')=='total']
        self.assertEqual(len(initial),1)

    def test_if_and_loop_are_same_region_mechanism(self):
        graph=self.doc.composite_file_graph(set(self.doc.scopes)-{'module'})
        by={n['id']:n for n in graph['nodes']}
        loop=next(n for n in by.values() if n['source_kind']=='loop')
        branch=next(n for n in by.values() if n['source_kind']=='branch')
        updates=[n for n in by.values() if n.get('source_construct')=='augmented_assignment']
        self.assertTrue(all(n['containing_scope']==self.key for n in (loop,branch,*updates)))
        self.assertTrue(all(n.get('graph_interface') and not n.get('embedded_region') for n in (loop,branch)))
        self.assertEqual(len(by),len(graph['nodes']))
        self.assertTrue(all(e['source'] in by and e['target'] in by for e in graph['edges']))
        self.assertEqual(self.path.read_text(),SOURCE)


    def test_collapse_preserves_source_and_edges(self):
        expanded=set(self.doc.scopes)-{'module'}
        graph=self.doc.composite_file_graph(expanded)
        branch=next(n for n in graph['nodes'] if n.get('source_kind')=='branch')
        collapsed=self.doc.composite_file_graph(expanded,collapsed_regions={'old/region:'+branch['id']})
        self.assertEqual({n['id'] for n in graph['nodes']},{n['id'] for n in collapsed['nodes']})
        self.assertEqual({e['id'] for e in graph['edges']},{e['id'] for e in collapsed['edges']})
        self.assertEqual(next(n for n in graph['nodes'] if n['id']==branch['id'])['graph_interface'],
                         next(n for n in collapsed['nodes'] if n['id']==branch['id'])['graph_interface'])
        self.assertEqual(self.path.read_text(),SOURCE)


    def test_authored_inline_operand_has_editable_source_span(self):
        graph=self.doc.presentation_graph(self.key)
        sub=next(n for n in graph['nodes'] if n.get('source_construct')=='augmented_assignment' and
                 n['title']=='-=')
        rhs=next(p for p in sub['draft_ports']['inputs'] if p['id'].endswith(':operand'))
        self.assertEqual(rhs['default'],2)
        proposal=change_literal(self.doc,rhs['source_literal_span'],'3')
        self.assertIn('total -= 3',proposal.candidate.decode())
        self.assertEqual(self.path.read_text(),SOURCE)

    def test_nested_if_elif_uses_one_conditional_representation(self):
        code='''def f(x):
    if x > 2:
        y = 2
    elif x > 1:
        y = 1
    else:
        y = 0
    return y
'''
        self.path.write_text(code)
        doc=PythonDocument(self.path)
        key=next(k for k,s in doc.scopes.items() if s.title=='f')
        graph=doc.presentation_graph(key)
        self.assertEqual([n['title'] for n in graph['nodes'] if n.get('source_construct')=='conditional'],
                         ['IF x > 2','ELIF x > 1'])
        nested=doc.composite_file_graph(set(doc.scopes)-{'module'})
        conditions=[n for n in nested['nodes'] if n.get('source_construct')=='conditional']
        self.assertEqual(len(conditions),2)
        self.assertTrue(all(not n.get('embedded_region') and n.get('graph_interface') for n in conditions))

if __name__=='__main__':unittest.main()
