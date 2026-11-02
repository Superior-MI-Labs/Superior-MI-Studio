"""v2.91: one-hop file relationships are view filters, not another index."""
import tempfile
import unittest
from pathlib import Path

from studio_native.graph_routes import resolve_graph
from studio_native.navigation import Route
from studio_native.resource_graph import ResourceError, directory_graph
from studio_native.semantic_contract import describe_graph


class FocusedResourceRelationshipTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.folder=self.root/'assets'
        self.folder.mkdir()
        self.asset=self.folder/'icon.png'
        self.asset.write_bytes(b'PNG')
        self.main=self.root/'main.py'
        self.helper=self.root/'helper.py'
        self.other=self.root/'other.py'
        self.main.write_text('import helper\nopen("assets/icon.png")\n',encoding='utf-8')
        self.helper.write_text('import other\n',encoding='utf-8')
        self.other.write_text('VALUE=1\n',encoding='utf-8')

    def build(self,**kw):
        graph=directory_graph(self.root,show_imports=True,expanded_paths=[self.folder],**kw)
        describe_graph(graph,origin='resource')
        return graph

    def relations(self,graph):
        paths={n['id']:Path(n['resource_path']) for n in graph['nodes'] if n.get('resource_kind')=='file'}
        return {(paths[e['source']].name,paths[e['target']].name,e['relation'])
                for e in graph['edges'] if e.get('relation') in ('imports','reference')}

    def test_unfocused_qualified_baseline(self):
        graph=self.build()
        self.assertEqual(self.relations(graph),{
            ('main.py','helper.py','imports'),('helper.py','other.py','imports'),
            ('main.py','icon.png','reference')})
        self.assertIsNone(graph['relationship_focus'])

    def test_main_both_filters_out_unrelated_helper_import(self):
        graph=self.build(relationship_focus=self.main)
        self.assertEqual(self.relations(graph),{
            ('main.py','helper.py','imports'),('main.py','icon.png','reference')})
        self.assertEqual(graph['relationship_focus'],str(self.main))
        self.assertEqual(graph['relationship_direction'],'both')

    def test_helper_incoming_outgoing_and_both(self):
        assert_rel={
            'incoming':{('main.py','helper.py','imports')},
            'outgoing':{('helper.py','other.py','imports')},
            'both':{('main.py','helper.py','imports'),('helper.py','other.py','imports')},
        }
        for direction,expected in assert_rel.items():
            with self.subTest(direction=direction):
                graph=self.build(relationship_focus=self.helper,relationship_direction=direction)
                self.assertEqual(self.relations(graph),expected)

    def test_non_python_target_inbound_only(self):
        graph=self.build(relationship_focus=self.asset,relationship_direction='incoming')
        self.assertEqual(self.relations(graph),{('main.py','icon.png','reference')})
        self.assertFalse(self.build(relationship_focus=self.asset,
                                    relationship_direction='outgoing')['edges'])

    def test_import_layer_and_focus_intersect(self):
        graph=self.build(relationship_focus=self.main,relationship_kinds={'imports'})
        self.assertEqual(self.relations(graph),{('main.py','helper.py','imports')})
        graph=self.build(relationship_focus=self.main,relationship_kinds={'references'})
        self.assertEqual(self.relations(graph),{('main.py','icon.png','reference')})
        graph=self.build(relationship_focus=self.main,relationship_kinds=set())
        self.assertEqual(self.relations(graph),set())

    def test_focus_on_hidden_child_does_not_expand_it(self):
        with self.assertRaises(ResourceError):
            directory_graph(self.root,show_imports=True,relationship_focus=self.asset)

    def test_focus_on_external_file_is_refused(self):
        with tempfile.TemporaryDirectory() as elsewhere:
            target=Path(elsewhere)/'foreign.py';target.write_text('pass\n')
            with self.assertRaises(ResourceError):self.build(relationship_focus=target)

    def test_focus_on_directory_or_missing_file_refused(self):
        for path in (self.folder,self.root/'missing.py'):
            with self.subTest(path=path), self.assertRaises(ResourceError):
                self.build(relationship_focus=path)

    def test_symlink_focus_refused_even_when_visible(self):
        alias=self.root/'alias.py';alias.symlink_to(self.main)
        with self.assertRaises(ResourceError):self.build(relationship_focus=alias)

    def test_parent_symlink_focus_refused(self):
        alias=self.root/'alias_assets';alias.symlink_to(self.folder,target_is_directory=True)
        with self.assertRaises(ResourceError):self.build(relationship_focus=alias/'icon.png')

    def test_bad_direction_refused_even_without_overlay(self):
        with self.assertRaises(ResourceError):
            directory_graph(self.root,relationship_direction='reverse')

    def test_focus_survives_overlay_visibility_toggle(self):
        graph=directory_graph(self.root,show_imports=False,relationship_focus=self.main)
        self.assertEqual(graph['relationship_focus'],str(self.main))
        self.assertFalse(graph['edges'])
        self.assertEqual(self.relations(self.build(relationship_focus=graph['relationship_focus'])),
                         {('main.py','helper.py','imports'),('main.py','icon.png','reference')})

    def test_no_alternate_owner_or_mutation(self):
        prior=self.main.read_bytes()
        graph=self.build(relationship_focus=self.main)
        self.assertFalse(any(n.get('resource_kind')=='file' and n.get('resource_path')==str(self.root/'unknown')
                             for n in graph['nodes']))
        self.assertEqual(self.main.read_bytes(),prior)

    def test_graph_route_preserves_qualified_focus(self):
        resolved=resolve_graph(Route('resource',str(self.root)),resource_imports=True,
            resource_expanded={str(self.folder)},resource_relationship_focus=self.main,
            resource_relationship_direction='outgoing')
        self.assertEqual(resolved.graph['relationship_focus'],str(self.main))
        self.assertEqual(self.relations(resolved.graph),
                         {('main.py','helper.py','imports'),('main.py','icon.png','reference')})

    def test_live_source_revision_changes_neighborhood(self):
        class Owner:
            text='import other\n'
        graph=self.build(relationship_focus=self.main,source_documents={str(self.main):Owner()})
        self.assertEqual(self.relations(graph),{('main.py','other.py','imports')})

    def test_focus_with_no_matching_edges_keeps_visible_file_cards(self):
        graph=self.build(relationship_focus=self.other,relationship_direction='outgoing')
        self.assertFalse(graph['edges'])
        self.assertTrue(any(n.get('resource_path')==str(self.main) for n in graph['nodes']))

if __name__=='__main__':unittest.main()
