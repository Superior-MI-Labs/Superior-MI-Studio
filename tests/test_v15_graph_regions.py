"""v1.5 source-independent surface, layout and region projection regressions."""
import tempfile
import unittest
from pathlib import Path
from studio_native.graph_layout import arrange,node_size
from studio_native.graph_surface import GraphSurfaceState
from studio_native.python_graph import PythonDocument

SAMPLE='''\ndef accumulate(items: list[int]) -> int:
    total = 0
    for item in items:
        if item > 0:
            total += item
    return total

def countdown(n: int) -> int:
    while n > 0:
        n -= 1
    return n

def nested(rows):
    for row in rows:
        for item in row:
            if item > 0:
                break
    return 0
'''

class RegionProjectionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.source=Path(self.temp.name)/'script.py'
        self.source.write_text(SAMPLE)
        self.doc=PythonDocument(self.source)
        self.expanded=set(self.doc.scopes)-{'module'}
        self.graph=self.doc.composite_file_graph(self.expanded)

    def tearDown(self):self.temp.cleanup()

    def test_loop_body_is_nested_without_synthetic_operations(self):
        all_nodes={n['id']:n for n in self.graph['nodes']}
        control=[n for n in all_nodes.values() if n['source_kind'] in ('loop','branch')]
        self.assertTrue(control)
        self.assertTrue(all(not n.get('embedded_region') and not n.get('child_region_key') for n in control))
        self.assertTrue(all(n.get('graph_interface') for n in control))
        self.assertTrue(all(n['containing_scope'] in self.doc.scopes for n in control))
        self.assertFalse(any(' BODY' in n['title'] for n in all_nodes.values()))


    def test_loop_boundary_has_actual_source_line(self):
        loops=[n for n in self.graph['nodes'] if n.get('source_kind')=='loop']
        self.assertTrue(any(n['title']=='WHILE n > 0' for n in loops))
        self.assertTrue(any(n['title']=='FOR item' for n in loops))
        self.assertTrue(all(n['source_span']['line']>0 for n in loops))


    def test_declaration_boundary_has_full_signature(self):
        n=next(n for n in self.graph['nodes'] if n.get('source_scope') and n['title']=='ACCUMULATE')
        self.assertEqual(n['display_title'],'def accumulate(items: list[int]) -> int:')
        self.assertEqual(n['embedded_region']['surface_top'],31.)
        self.assertEqual(n['embedded_region']['width'],n['embedded_region']['viewport_width']+12.)

    def test_formal_parameter_kept_but_not_repeated_in_expanded_view(self):
        parents={n['source_scope']:n for n in self.graph['nodes'] if n.get('source_scope')}
        params=[n for n in self.graph['nodes'] if n.get('source_kind')=='param']
        self.assertGreaterEqual(len(params),3)
        for n in params:
            self.assertTrue(n.get('presentation_hidden'))
            label=n['draft_ports']['outputs'][0]['label']
            self.assertTrue(any(p['label']==label for p in parents[n['containing_scope']]['draft_ports']['inputs']))

    def test_loop_region_is_not_a_python_scope(self):
        loops=[n for n in self.graph['nodes'] if n.get('source_kind')=='loop']
        self.assertTrue(all(n.get('source_scope') is None for n in loops))
        self.assertTrue(all(n.get('containing_scope') in self.doc.scopes for n in loops))


    def test_nested_loops_have_nearest_owning_region(self):
        outer=next(n for n in self.graph['nodes'] if n['title']=='FOR row')
        inner=next(n for n in self.graph['nodes'] if n['title']=='FOR item' and n['containing_scope']==outer['containing_scope'])
        condition=next(n for n in self.graph['nodes'] if n.get('source_kind')=='branch' and n['containing_scope']==outer['containing_scope'])
        self.assertEqual(outer['containing_scope'],inner['containing_scope'])
        self.assertEqual(condition['containing_scope'],inner['containing_scope'])
        self.assertTrue(all('embedded_region' not in n for n in (outer,inner,condition)))


    def test_collapsing_a_loop_is_presentation_only(self):
        loop=next(n for n in self.graph['nodes'] if n['title']=='WHILE n > 0')
        old_key='legacy/region:'+loop['id']
        other=self.doc.composite_file_graph(self.expanded,collapsed_regions={old_key})
        self.assertNotIn('embedded_region',next(n for n in other['nodes'] if n['id']==loop['id']))
        self.assertEqual({n['id'] for n in self.graph['nodes']},{n['id'] for n in other['nodes']})
        self.assertEqual({e['id'] for e in self.graph['edges']},{e['id'] for e in other['edges']})
        self.assertEqual(SAMPLE,self.source.read_text())


    def test_no_semantic_edge_changes_from_full_program(self):
        base=self.doc.whole_file_graph(self.expanded,detail='readable')
        self.assertEqual({n['id'] for n in base['nodes']},{n['id'] for n in self.graph['nodes']})
        self.assertEqual({e['id'] for e in base['edges']},{e['id'] for e in self.graph['edges']})

    def test_initial_viewport_fit_bounds(self):
        regions=[n['embedded_region'] for n in self.graph['nodes'] if n.get('embedded_region')]
        self.assertTrue(regions)
        self.assertTrue(all(n.get('source_scope') for n in self.graph['nodes'] if n.get('embedded_region')))
        for r in regions:
            self.assertTrue(180<=r['viewport_width']<=810)
            self.assertTrue(90<=r['viewport_height']<=425)
            surface=GraphSurfaceState(r['viewport_width'],r['viewport_height'],r['content_width'],r['content_height'])
            surface.fit_contents()
            self.assertLessEqual(surface.zoom*r['content_width'],r['viewport_width']+.01)


    def test_root_definitions_are_in_one_source_order_column(self):
        root=[n for n in self.graph['nodes'] if n.get('source_scope') and n.get('containing_scope','module')=='module']
        self.assertGreaterEqual(len(root),3)
        self.assertEqual(len({n['x'] for n in root}),1)
        self.assertEqual([n['y'] for n in root],sorted(n['y'] for n in root))
        for a,b in zip(root,root[1:]):
            self.assertGreaterEqual(b['y'],a['y']+node_size(a)[1])

class SharedLayoutTests(unittest.TestCase):
    def test_generic_dependency_order_and_no_overlap(self):
        def n(id_,line):return {'id':id_,'source_span':{'line':line},'source_kind':'operation',
                                'draft_ports':{'inputs':[],'outputs':[]}}
        nodes=[n('consumer',5),n('producer',5),n('return',6)]
        edges=[{'source':'producer','target':'consumer','relation':'data'}]
        w,h=arrange(nodes,edges)
        self.assertLess(nodes[1]['x'],nodes[0]['x'])
        self.assertGreater(w,200);self.assertGreater(h,100)
        self.assertGreater(nodes[2]['y'],nodes[0]['y'])

    def test_layout_deterministic_independent_of_language(self):
        def mk():return [{'id':str(i),'draft_ports':{'inputs':[],'outputs':[]},'source_span':{'line':i}}
                         for i in range(5)]
        a=mk();b=mk()
        self.assertEqual(arrange(a,[]),arrange(b,[]))
        self.assertEqual([(n['x'],n['y']) for n in a],[(n['x'],n['y']) for n in b])

    def test_can_pan_into_empty_area_when_contents_already_fit(self):
        surface=GraphSurfaceState(600,300,190,100)
        surface.fit_contents()
        start=(surface.offset_x,surface.offset_y)
        surface.pan(-220,-140)
        self.assertEqual((surface.offset_x,surface.offset_y),(start[0]-220,start[1]-140))

if __name__=='__main__':unittest.main()
