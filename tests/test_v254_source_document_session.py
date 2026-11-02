"""Document ownership and failure cases without a native Qt requirement."""
import tempfile
import unittest
from pathlib import Path
from studio_native.python_graph import SourceError
from studio_native.graph_routes import resolve_graph
from studio_native.navigation import Route
from studio_native.source_editor import SourceDocumentSession
from studio_native.python_edit import SourceEditHistory

class RevisionedSourceSessionTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path=Path(tmp.name)/'test.py'
        self.path.write_bytes(b'def calc(value):\n    return value + 1\n')

    def test_valid_live_revision_reuses_same_parser_for_multiple_views_without_disk_write(self):
        session=SourceDocumentSession.open(self.path)
        saved=self.path.read_bytes()
        self.assertTrue(session.graph_ready)
        self.assertTrue(session.update('def calc(value):\n    return value * 3\n'))
        self.assertTrue(session.dirty)
        self.assertEqual(session.revision,1)
        self.assertEqual(self.path.read_bytes(),saved)
        doc=session.parsed
        whole=resolve_graph(Route('source',str(self.path)),document=doc)
        scope=next(k for k,v in doc.scopes.items() if v.title=='calc')
        focused=resolve_graph(Route('source',str(self.path),scope,'focus'),document=doc)
        self.assertIs(whole.document,focused.document)
        self.assertIs(doc,whole.document)
        self.assertEqual(session.revision,1)
        self.assertFalse(session.update(session.text))

    def test_invalid_draft_disables_projection_not_text_and_can_recover(self):
        s=SourceDocumentSession.open(self.path)
        s.update('def calc(value):\n    return (\n')
        self.assertFalse(s.graph_ready)
        self.assertIsNone(s.parsed)
        self.assertIn('analysis failed',s.diagnostic)
        self.assertEqual(self.path.read_bytes(),s.saved_raw)
        s.update('def calc(value):\n    return value - 2\n')
        self.assertTrue(s.graph_ready)
        self.assertIsNone(s.diagnostic)

    def test_invalid_draft_can_be_safely_saved_and_reopened(self):
        s=SourceDocumentSession.open(self.path)
        invalid='def calc(value):\n    return (\n'
        s.update(invalid)
        backup=s.commit(history=SourceEditHistory())
        self.assertEqual(backup.read_bytes(),b'def calc(value):\n    return value + 1\n')
        self.assertEqual(self.path.read_text(),invalid)
        self.assertFalse(s.dirty)
        reopened=SourceDocumentSession.open(self.path)
        self.assertEqual(reopened.text,invalid)
        self.assertFalse(reopened.graph_ready)
        reopened.update('def calc(value):\n    return value + 4\n')
        self.assertTrue(reopened.graph_ready)
        reopened.commit()
        self.assertEqual(self.path.read_text(),'def calc(value):\n    return value + 4\n')

    def test_external_changes_refuse_publish_without_losing_editor_text(self):
        s=SourceDocumentSession.open(self.path)
        s.update('answer=5\n')
        self.path.write_text('other=8\n')
        with self.assertRaisesRegex(SourceError,'changed externally'):
            s.commit()
        self.assertEqual(s.text,'answer=5\n')
        self.assertTrue(s.dirty)
        self.assertEqual(self.path.read_text(),'other=8\n')
        with self.assertRaisesRegex(SourceError,'explicitly discarded'):
            s.discard_and_reload()

    def test_discard_reload_clean_document(self):
        s=SourceDocumentSession.open(self.path)
        self.path.write_text('value=5\n')
        s.discard_and_reload()
        self.assertEqual(s.text,'value=5\n')
        self.assertTrue(s.graph_ready)
        self.assertEqual(s.revision,1)

    def test_bom_crlf_and_nonbmp_round_trip(self):
        self.path.write_bytes(b'\xef\xbb\xbfdef calc():\r\n    return "cat"\r\n')
        s=SourceDocumentSession.open(self.path)
        s.update('def calc():\n    return "\U0001f431"\n')
        self.assertTrue(s.graph_ready)
        s.commit()
        self.assertEqual(self.path.read_bytes(),b'\xef\xbb\xbf'+('def calc():\r\n    return "\U0001f431"\r\n').encode())

    def test_cannot_publish_nonencodable_source(self):
        self.path.write_bytes(b'# coding: latin-1\nname="caf\xe9"\n')
        s=SourceDocumentSession.open(self.path)
        s.update('# coding: latin-1\nname="\U0001f431"\n')
        self.assertFalse(s.graph_ready)
        self.assertIn('encode',s.diagnostic)
        with self.assertRaises(SourceError):s.commit()
        self.assertEqual(self.path.read_bytes(),b'# coding: latin-1\nname="caf\xe9"\n')

    def test_symlink_and_oversized_sources_are_refused(self):
        link=self.path.with_name('link.py')
        link.symlink_to(self.path)
        with self.assertRaisesRegex(SourceError,'Symlink'):
            SourceDocumentSession.open(link)
        s=SourceDocumentSession.open(self.path)
        s.update('x'*1_500_001)
        self.assertFalse(s.graph_ready)
        with self.assertRaises(SourceError):s.commit()

    def test_debounced_qualify_and_revert_to_saved_revision(self):
        s=SourceDocumentSession.open(self.path)
        original=s.text
        s.update('answer=5\n',parse=False)
        self.assertFalse(s.graph_ready)
        self.assertTrue(s.dirty)
        self.assertTrue(s.qualify())
        s.update(original,parse=False)
        self.assertTrue(s.qualify())
        self.assertFalse(s.dirty)
        self.assertTrue(s.graph_ready)
        self.assertIsNone(s.commit())

    def test_committed_history_restores_valid_from_invalid_source(self):
        history=SourceEditHistory()
        session=SourceDocumentSession.open(self.path)
        session.update('def calc(value):\n    return (\n')
        session.commit(history=history)
        self.assertFalse(session.graph_ready)
        self.assertTrue(history.can_undo(self.path))
        history.undo(self.path)
        session.discard_and_reload()
        self.assertTrue(session.graph_ready)
        self.assertEqual(session.text,'def calc(value):\n    return value + 1\n')
        history.redo(self.path)
        session.discard_and_reload()
        self.assertFalse(session.graph_ready)
        self.assertTrue(session.diagnostic)

    def test_separate_files_do_not_share_revision_or_source(self):
        second=self.path.with_name('second.py')
        second.write_text('print(2)\n')
        first=SourceDocumentSession.open(self.path)
        other=SourceDocumentSession.open(second)
        first.update('answer=3\n')
        self.assertEqual(other.revision,0)
        self.assertEqual(other.text,'print(2)\n')
        self.assertIsNot(first.parsed,other.parsed)
        first.commit()
        self.assertEqual(second.read_text(),'print(2)\n')

    def test_mixed_newlines_refuse_publish_but_draft_survives(self):
        self.path.write_bytes(b'a=1\r\nb=2\n')
        s=SourceDocumentSession.open(self.path)
        s.update('a=2\nb=3\n')
        self.assertFalse(s.graph_ready)
        self.assertIsNone(s.parsed)
        self.assertIn('Mixed line endings',s.diagnostic)
        with self.assertRaises(SourceError):s.commit()
        self.assertEqual(s.text,'a=2\nb=3\n')
        self.assertEqual(self.path.read_bytes(),b'a=1\r\nb=2\n')

    def test_parsing_does_not_execute_python_source(self):
        flag=self.path.with_name('executed.flag')
        candidate=f'from pathlib import Path\nPath({str(flag)!r}).write_text("bad")\n'
        s=SourceDocumentSession.open(self.path)
        s.update(candidate)
        self.assertTrue(s.graph_ready)
        self.assertFalse(flag.exists())
        s.commit()
        self.assertFalse(flag.exists())

    def test_unchanged_revision_has_no_backup(self):
        s=SourceDocumentSession.open(self.path)
        self.assertFalse(s.dirty)
        self.assertIsNone(s.commit())
        self.assertEqual(list(self.path.parent.glob('*.smi-backup*')),[])

if __name__=='__main__':unittest.main()
