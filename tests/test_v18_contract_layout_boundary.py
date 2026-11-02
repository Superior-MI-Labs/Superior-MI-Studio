"""v1.8 contract, source-first layout and genuine boundary rewire tests."""
import copy
import tempfile
import unittest
from pathlib import Path

from studio_native.model import new_state
from studio_native.semantic_contract import describe_graph, ContractError, CONTRACT_VERSION
from studio_native.python_graph import PythonDocument
from studio_native.python_edit import rewire_source_operand, apply_proposal
from studio_native.boundary_edit import (parameter_source, terminal_return_target,
                                          BoundaryEditError)
from studio_native.graph_layout import arrange, node_size


class V18ContractTests(unittest.TestCase):
    def test_draft_and_source_share_the_same_read_only_descriptor(self):
        draft=new_state()
        untouched=copy.deepcopy(draft)
        d=describe_graph(draft,origin='draft')
        self.assertEqual(d.version,CONTRACT_VERSION)
        self.assertEqual(d.origin,'draft')
        self.assertEqual(len(d.nodes),len(draft['nodes']))
        self.assertEqual(draft,untouched)
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'a.py'
            path.write_text('def f(a):\n    return a + 2\n')
            doc=PythonDocument(path)
            g=doc.composite_file_graph(set(doc.scopes)-{'module'})
            before=copy.deepcopy(g)
            source=describe_graph(g,origin='source')
            self.assertEqual(source.origin,'source')
            self.assertEqual({n.id for n in source.nodes},{n['id'] for n in g['nodes']})
            self.assertEqual({e.id for e in source.edges},{e['id'] for e in g['edges']})
            self.assertTrue(any(n.child_graph for n in source.nodes))
            self.assertEqual(g,before)

    def test_no_mutation_or_fabricated_semantics_for_drafts(self):
        draft=new_state()
        d=describe_graph(draft,origin='draft')
        self.assertTrue(all(n.origin=='draft' and n.source is None for n in d.nodes))
        self.assertTrue(all(e.relation in {'data','control','call','reference','effect'} for e in d.edges))

    def test_reject_duplicate_ports_and_nonexistent_edges(self):
        draft=new_state()
        copy1=copy.deepcopy(draft)
        node=copy1['nodes'][0]
        node['draft_ports']['inputs'].append(copy.deepcopy(node['draft_ports']['inputs'][0]))
        with self.assertRaisesRegex(ContractError,'Duplicate'):
            describe_graph(copy1,origin='draft')
        copy2=copy.deepcopy(draft)
        copy2['edges'][0]['targetPort']='no-such-port'
        with self.assertRaisesRegex(ContractError,'unknown or reversed'):
            describe_graph(copy2,origin='draft')
        copy3=copy.deepcopy(draft)
        copy3['edges'][0]['relation']='made-up-control-flow'
        with self.assertRaisesRegex(ContractError,'Unknown relationship'):
            describe_graph(copy3,origin='draft')


class V18BoundaryEditTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'source.py'

    def load(self,code):
        self.path.write_text(code)
        doc=PythonDocument(self.path)
        graph=doc.composite_file_graph(set(doc.scopes)-{'module'})
        return doc,graph

    def test_inner_parameter_to_terminal_return_is_validated_real_edit(self):
        original='def f(a, b):\n    return a\n'
        doc,g=self.load(original)
        owner=next(n for n in g['nodes'] if n.get('source_kind')=='function')
        parameter=next(p for p in owner['draft_ports']['inputs'] if p['label']=='b')
        return_port=next(p for p in owner['draft_ports']['outputs'] if p['label']=='return')
        source=parameter_source(g,owner['id'],parameter['id'])
        target=terminal_return_target(g,owner['id'],return_port['id'])
        scope=owner['source_scope']
        proposal=rewire_source_operand(doc,scope,*source,*target)
        self.assertIn('return b',proposal.candidate.decode())
        self.assertEqual(self.path.read_text(),original)
        backup=apply_proposal(proposal)
        self.assertEqual(backup.read_text(),original)
        self.assertEqual(self.path.read_text(),'def f(a, b):\n    return b\n')
        self.assertIn('return b',PythonDocument(self.path).source)

    def test_multiple_returns_have_no_ambiguous_return_boundary_edit(self):
        doc,g=self.load('def f(a):\n    if a:\n        return 1\n    return 2\n')
        owner=next(n for n in g['nodes'] if n.get('source_kind')=='function')
        port=next(p for p in owner['draft_ports']['outputs'] if p['label']=='return')
        with self.assertRaisesRegex(BoundaryEditError,'Multiple/early'):
            terminal_return_target(g,owner['id'],port['id'])

    def test_no_edit_for_loop_region_or_callable_output(self):
        doc,g=self.load('def f(items):\n    for item in items:\n        pass\n    return items\n')
        owner=next(n for n in g['nodes'] if n.get('source_kind')=='function')
        for p in owner['draft_ports']['outputs']:
            if p['label']=='callable':
                with self.assertRaises(BoundaryEditError):
                    terminal_return_target(g,owner['id'],p['id'])
        loop=next(n for n in g['nodes'] if n.get('source_kind')=='loop')
        for p in loop['draft_ports']['inputs']:
            with self.assertRaises(BoundaryEditError):
                parameter_source(g,loop['id'],p['id'])


class V18LayoutTests(unittest.TestCase):
    @staticmethod
    def node(id_,line,*,width=155):
        return {'id':id_,'title':id_,'source_kind':'operation',
                'source_span':dict(line=line,col=0,end_line=line,end_col=1),
                'draft_ports':{'inputs':[],'outputs':[]}}

    def test_chained_expressions_follow_actual_producer_order(self):
        # Deliberately reversed parser order, with equal source lines.
        nodes=[self.node('final',3),self.node('middle',3),self.node('initial',3)]
        edges=[{'source':'initial','target':'middle'},
               {'source':'middle','target':'final'}]
        arrange(nodes,edges)
        xs={n['id']:n['x'] for n in nodes}
        self.assertLess(xs['initial'],xs['middle'])
        self.assertLess(xs['middle'],xs['final'])

    def test_long_expression_wraps_and_is_stable(self):
        nodes=[self.node('n'+str(i),2) for i in reversed(range(10))]
        edges=[{'source':'n'+str(i),'target':'n'+str(i+1)} for i in range(9)]
        original=copy.deepcopy(nodes)
        width,height=arrange(nodes,edges)
        self.assertLess(width,1100)
        self.assertGreater(height,100)
        self.assertGreater(len({n['y'] for n in nodes}),1)
        once=[(n['id'],n['x'],n['y']) for n in nodes]
        arrange(nodes,edges)
        self.assertEqual([(n['id'],n['x'],n['y']) for n in nodes],once)
        self.assertEqual([n['id'] for n in nodes],[n['id'] for n in original])

if __name__=='__main__':
    unittest.main()

class V18CorpusContractTests(unittest.TestCase):
    def test_every_shipped_python_source_has_valid_readable_analysis_and_composite_contracts(self):
        from pathlib import Path
        root=Path(__file__).resolve().parents[1]/'examples'
        samples=list(root.glob('*.py'))
        self.assertGreaterEqual(len(samples),10)
        for path in samples:
            with self.subTest(file=path.name):
                doc=PythonDocument(path)
                for scope in doc.scopes:
                    for detail in ('readable','analysis'):
                        described=describe_graph(doc.presentation_graph(scope,detail=detail),origin='source')
                        self.assertEqual(len(described.nodes),len(doc.presentation_graph(scope,detail=detail)['nodes']))
                composite=doc.composite_file_graph(set(doc.scopes)-{'module'})
                describe_graph(composite,origin='source')
                # Reading and normalizing must not touch the actual source.
                self.assertEqual(path.read_bytes(),doc.raw)
