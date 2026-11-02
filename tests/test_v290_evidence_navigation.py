"""v2.90: exact live-source line qualification without an alternate document owner."""
import tempfile
import unittest
from pathlib import Path

from studio_native.source_associations import verified_evidence_line
from studio_native.resource_graph import directory_graph, inspect_resource_relationship
from studio_native.semantic_contract import describe_graph


class SourceEvidenceNavigationTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        root=self.root=Path(tmp.name)
        (root/'assets').mkdir()
        (root/'assets'/'icon.png').write_bytes(b'PNG')
        (root/'helper.py').write_text('def helper(): return 4\n')
        self.source=root/'main.py'
        self.source.write_text('import helper\nopen("assets/icon.png")\n')
        graph=self.graph=directory_graph(root,show_imports=True,expanded_paths=[root/'assets'])
        self.contract=describe_graph(graph,origin='resource')

    def evidence(self,relation):
        edge=next(e for e in self.contract.edges if e.relation==relation)
        return inspect_resource_relationship(self.contract,self.graph,edge.id).evidence[0]

    def test_import_evidence_is_navigable_in_current_source(self):
        evidence=self.evidence('imports')
        self.assertEqual(verified_evidence_line(self.source.read_text(),evidence.line,evidence.syntax),1)

    def test_literal_asset_evidence_is_navigable(self):
        evidence=self.evidence('reference')
        self.assertEqual(verified_evidence_line(self.source.read_text(),evidence.line,evidence.syntax),2)

    def test_renamed_import_no_longer_qualifies(self):
        evidence=self.evidence('imports')
        self.assertIsNone(verified_evidence_line('import different\n'+self.source.read_text().splitlines()[1]+'\n',
                                                 evidence.line,evidence.syntax))

    def test_shifted_statement_cannot_jump_to_old_line(self):
        evidence=self.evidence('reference')
        self.assertIsNone(verified_evidence_line('\n'+self.source.read_text(),evidence.line,evidence.syntax))

    def test_deleted_statement_is_refused(self):
        evidence=self.evidence('reference')
        self.assertIsNone(verified_evidence_line('import helper\n',evidence.line,evidence.syntax))

    def test_identical_statement_on_different_line_is_refused(self):
        evidence=self.evidence('imports')
        self.assertIsNone(verified_evidence_line('\nimport helper\n',evidence.line,evidence.syntax))

    def test_unrelated_source_change_keeps_exact_evidence(self):
        evidence=self.evidence('imports')
        self.assertEqual(verified_evidence_line('import helper\nvalue=45\n',evidence.line,evidence.syntax),1)

    def test_invalid_unsaved_draft_never_uses_saved_graph(self):
        evidence=self.evidence('imports')
        self.assertIsNone(verified_evidence_line('import helper\ndef broken(:\n',evidence.line,evidence.syntax))

    def test_synthetic_declaration_annotation_never_claims_line(self):
        self.assertIsNone(verified_evidence_line('def helper(): return 4\n',1,
                                                 'FunctionDef helper (syntactic declaration match)'))

    def test_non_ast_text_fragment_is_not_a_statement(self):
        self.assertIsNone(verified_evidence_line('value = "import helper"\n',1,'import helper'))

    def test_multiline_import_exact_source_segment(self):
        text='from helper import (\n    foo,\n    bar,\n)\n'
        self.assertEqual(verified_evidence_line(text,1,'from helper import (\n    foo,\n    bar,\n)'),1)
        self.assertIsNone(verified_evidence_line(text,2,'from helper import (\n    foo,\n    bar,\n)'))

    def test_unicode_before_statement_preserves_line(self):
        self.assertEqual(verified_evidence_line('banner="☃️"\nimport helper\n',2,'import helper'),2)

    def test_refuses_malformed_metadata_and_nontext(self):
        for line,syntax in ((True,'import helper'),(0,'import helper'),(-1,'import helper'),
                            (1,''),(1,None),(1,'import different')):
            self.assertIsNone(verified_evidence_line('import helper\n',line,syntax))

    def test_refuses_oversized_source(self):
        self.assertIsNone(verified_evidence_line(' '*512_001+'\nimport helper\n',2,'import helper'))


if __name__=='__main__':unittest.main()
