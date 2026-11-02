"""v2.85: static file association evidence follows the visible resource and live source owner."""
import tempfile
import unittest
from pathlib import Path
from studio_native.resource_graph import directory_graph
from studio_native.source_editor import SourceDocumentSession
from studio_native.semantic_contract import describe_graph
from studio_native.source_associations import local_python_imports,local_python_literal_files

class VisibleEvidence(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.nested=self.root/'nested';self.nested.mkdir()
        self.src=self.nested/'main.py'
        self.target=self.nested/'sibling.py'
        self.asset=self.nested/'icon.png'
        self.src.write_text("import sibling\nopen('icon.png')\n",encoding='utf-8')
        self.target.write_text('def run():pass\n',encoding='utf-8')
        self.asset.write_bytes(b'pixel')

    def test_unexpanded_children_are_never_scanned(self):
        graph=directory_graph(self.root,show_imports=True)
        self.assertEqual(graph['edges'],[])
        self.assertEqual(len(graph['nodes']),1)

    def test_explicit_expanded_children_get_sibling_evidence_without_new_index(self):
        graph=directory_graph(self.root,expanded_paths=(self.nested,),show_imports=True)
        self.assertEqual(len(graph['edges']),2)
        self.assertEqual({edge['relation'] for edge in graph['edges']},{'imports','reference'})
        self.assertTrue(all(edge['certainty'].endswith('candidate') for edge in graph['edges']))
        self.assertTrue(all(edge['provenance'][0]['source']==str(self.src) for edge in graph['edges']))
        self.assertEqual(len(describe_graph(graph,origin='resource').edges),2)
        self.assertEqual(self.src.read_text(),"import sibling\nopen('icon.png')\n")

    def test_live_valid_unsaved_revision_overrides_saved_evidence(self):
        session=SourceDocumentSession.open(self.src)
        session.update("open('icon.png')\n")
        self.assertTrue(session.graph_ready and session.dirty)
        graph=directory_graph(self.root,expanded_paths=(self.nested,),show_imports=True,
                              source_documents={str(self.src):session})
        self.assertEqual([edge['relation'] for edge in graph['edges']],['reference'])
        self.assertIn('import sibling',self.src.read_text())
        self.assertEqual(len(local_python_imports(self.src,{self.src,self.target})),1)
        # Returning to saved-only mode restores only the saved evidence.
        self.assertEqual(len(directory_graph(self.root,expanded_paths=(self.nested,),show_imports=True)['edges']),2)

    def test_invalid_live_draft_never_restores_saved_candidate(self):
        session=SourceDocumentSession.open(self.src)
        session.update('def broken(:\n')
        self.assertFalse(session.graph_ready)
        graph=directory_graph(self.root,expanded_paths=(self.nested,),show_imports=True,
                              source_documents={str(self.src):session})
        self.assertEqual(graph['edges'],[])
        self.assertEqual(self.src.read_text(),"import sibling\nopen('icon.png')\n")

    def test_live_target_declaration_tracks_source_revision(self):
        self.src.write_text('from sibling import run\n')
        session=SourceDocumentSession.open(self.target)
        session.update('def changed():pass\n')
        graph=directory_graph(self.root,expanded_paths=(self.nested,),show_imports=True,
                              source_documents={str(self.target):session})
        links=[edge for edge in graph['edges'] if edge['relation']=='imports']
        self.assertEqual(len(links),1)
        self.assertFalse(any('syntactic declaration match' in item['syntax']
                             for edge in links for item in edge['provenance']))
        session.update('def run():pass\n')
        graph=directory_graph(self.root,expanded_paths=(self.nested,),show_imports=True,
                              source_documents={str(self.target):session})
        links=[edge for edge in graph['edges'] if edge['relation']=='imports']
        self.assertTrue(any('syntactic declaration match' in item['syntax']
                            for edge in links for item in edge['provenance']))

    def test_unrelated_parent_files_cannot_create_cross_directory_associations(self):
        self.src.write_text("open('../outside.png')\n")
        outside=self.root/'outside.png';outside.write_bytes(b'pixel')
        self.assertEqual(local_python_literal_files(self.src,{self.src,outside}),[])
        graph=directory_graph(self.root,expanded_paths=(self.nested,),show_imports=True)
        self.assertEqual(graph['edges'],[])

if __name__=='__main__':unittest.main()
