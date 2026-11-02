"""v2.86: opt-in workspace relationships use visible, bounded child paths only."""
import tempfile
import unittest
from pathlib import Path
from studio_native.resource_graph import directory_graph
from studio_native.source_associations import local_python_literal_files
from studio_native.source_editor import SourceDocumentSession
from studio_native.semantic_contract import describe_graph

class WorkspaceLiteralEdges(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.assets=self.root/'assets';self.assets.mkdir()
        self.app=self.root/'main.py';self.app.write_text("open('assets/icon.png')\n")
        self.icon=self.assets/'icon.png';self.icon.write_bytes(b'png')

    def graph(self,**kwargs):
        return directory_graph(self.root,show_imports=True,**kwargs)

    def test_child_reference_only_after_explicit_folder_expand(self):
        self.assertFalse(self.graph()['edges'])
        shown=self.graph(expanded_paths=(self.assets,))
        self.assertEqual(len(shown['edges']),1)
        edge=shown['edges'][0]
        self.assertEqual(edge['relation'],'reference')
        self.assertEqual(edge['certainty'],'literal-path-candidate')
        self.assertIn("open('assets/icon.png')",edge['provenance'][0]['syntax'])
        self.assertEqual(len(describe_graph(shown,origin='resource').edges),1)
        self.assertEqual(self.app.read_text(),"open('assets/icon.png')\n")

    def test_default_standalone_provider_retains_sibling_only_policy(self):
        visible={self.app,self.icon}
        self.assertEqual(local_python_literal_files(self.app,visible),[])
        self.assertEqual(len(local_python_literal_files(
            self.app,visible,workspace_root=self.root)),1)

    def test_parent_traversal_is_refused_even_when_target_visible(self):
        folder=self.root/'module';folder.mkdir()
        src=folder/'nested.py';src.write_text("open('../assets/icon.png')\n")
        self.app.write_text('pass\n')
        graph=self.graph(expanded_paths=(folder,self.assets))
        self.assertFalse(graph['edges'])
        self.assertFalse(local_python_literal_files(src,{src,self.icon},workspace_root=self.root))

    def test_unexpanded_target_is_not_discovered_by_disk_scan(self):
        missing=self.assets/'other.png';missing.write_bytes(b'png')
        # Only the root file is visible; the child directory is not.
        self.assertFalse(self.graph()['edges'])

    def test_dynamically_composed_filename_is_not_evidence(self):
        self.app.write_text("open('assets/' + name)\n")
        self.assertFalse(self.graph(expanded_paths=(self.assets,))['edges'])

    def test_unsaved_revision_replaces_saved_child_reference(self):
        owner=SourceDocumentSession.open(self.app)
        owner.update("open('assets/missing.png')\n")
        self.assertFalse(self.graph(expanded_paths=(self.assets,),
                                    source_documents={str(self.app):owner})['edges'])
        owner.update("open('assets/icon.png')\n")
        self.assertEqual(len(self.graph(expanded_paths=(self.assets,),
                                        source_documents={str(self.app):owner})['edges']),1)
        self.assertEqual(self.app.read_text(),"open('assets/icon.png')\n")
        owner.update('def broken(:\n')
        self.assertFalse(self.graph(expanded_paths=(self.assets,),
                                    source_documents={str(self.app):owner})['edges'])

    def test_symlinked_intermediate_directory_is_refused(self):
        link=self.root/'alias';link.symlink_to(self.assets,target_is_directory=True)
        self.app.write_text("open('alias/icon.png')\n")
        self.assertFalse(local_python_literal_files(
            self.app,{self.app,link/'icon.png'},workspace_root=self.root))

    def test_absolute_dots_and_backslash_are_not_valid_child_paths(self):
        for path in ('/assets/icon.png','./assets/icon.png','assets/../assets/icon.png',
                     'assets\\icon.png','../assets/icon.png','assets//icon.png'):
            with self.subTest(path=path):
                self.app.write_text(f'open({path!r})\n')
                self.assertEqual(self.graph(expanded_paths=(self.assets,))['edges'],[])

    def test_nested_visible_child_directory_is_supported_with_explicit_expansion(self):
        sub=self.assets/'sprites';sub.mkdir()
        sprite=sub/'hero.png';sprite.write_bytes(b'sprite')
        self.app.write_text("open('assets/sprites/hero.png')\n")
        self.assertFalse(self.graph(expanded_paths=(self.assets,))['edges'])
        shown=self.graph(expanded_paths=(self.assets,sub))
        self.assertEqual(len(shown['edges']),1)
        self.assertEqual(shown['edges'][0]['relation'],'reference')

if __name__=='__main__':unittest.main()
