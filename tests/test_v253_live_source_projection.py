"""Phase 1 characterization: disk-owned Python and unsaved analysis snapshots.

This does not create a second mutable source buffer. The Qt/document-session
handoff is a separate migration gate, requiring a real Linux Qt qualification.
"""
import hashlib
import tempfile
import unittest
from pathlib import Path

from studio_native.graph_routes import resolve_graph
from studio_native.navigation import Route
from studio_native.python_edit import apply_proposal
from studio_native.python_graph import MAX_SOURCE, PythonDocument, SourceError
from studio_native.source_editor import prepare_source_change, preview_source_change


class LiveSourceProjectionBoundary(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'example.py'
        self.original=b'def compute(value):\n    return value + 1\n'
        self.path.write_bytes(self.original)

    def test_disk_snapshot_and_equal_memory_snapshot_have_identical_projection(self):
        disk=PythonDocument(self.path)
        memory=PythonDocument.from_bytes(self.path,self.original)
        for mode in ('whole','focus'):
            scope=next((k for k,v in disk.scopes.items() if v.title=='compute'),'module')
            route=Route('source',str(self.path),scope,'focus') if mode=='focus' else Route('source',str(self.path))
            a=resolve_graph(route,document=disk).descriptor
            b=resolve_graph(route,document=memory).descriptor
            self.assertEqual(a,b)
        self.assertEqual(disk.sha256,memory.sha256)
        self.assertEqual(disk.raw,memory.raw)

    def test_unsaved_valid_edit_has_its_own_graph_without_writing_disk(self):
        disk=PythonDocument(self.path)
        edited='def compute(value):\n    return value * 7\n'
        memory=preview_source_change(disk,edited)
        self.assertEqual(memory.source,edited)
        self.assertEqual(memory.sha256,hashlib.sha256(edited.encode()).hexdigest())
        self.assertNotEqual(memory.sha256,disk.sha256)
        self.assertEqual(self.path.read_bytes(),self.original)
        route=Route('source',str(self.path))
        disk_graph=resolve_graph(route,document=disk)
        memory_graph=resolve_graph(route,document=memory)
        self.assertIs(memory_graph.document,memory)
        # Whole-file function nodes expose the signature, not every body
        # expression; compare the focused function semantics instead.
        scope=next(k for k,v in disk.scopes.items() if v.title=='compute')
        focused_route=Route('source',str(self.path),scope,'focus')
        self.assertNotEqual(resolve_graph(focused_route,document=disk).graph,
                            resolve_graph(focused_route,document=memory).graph)
        self.assertEqual(memory_graph.route.path,str(self.path))

    def test_two_views_of_same_unsaved_revision_share_parser_but_not_view(self):
        doc=preview_source_change(PythonDocument(self.path),
                                  'def compute(value):\n    new = value + 2\n    return new\n')
        whole=resolve_graph(Route('source',str(self.path)),document=doc)
        scope=next(k for k,v in doc.scopes.items() if v.title=='compute')
        focused=resolve_graph(Route('source',str(self.path),scope,'focus'),document=doc)
        self.assertIs(whole.document,focused.document)
        self.assertIsNot(whole.graph,focused.graph)
        self.assertEqual(self.path.read_bytes(),self.original)

    def test_invalid_source_cannot_be_projected_and_disk_is_preserved(self):
        disk=PythonDocument(self.path)
        with self.assertRaisesRegex(SourceError,'analysis failed'):
            preview_source_change(disk,'def compute(value):\n    return (\n')
        self.assertEqual(self.path.read_bytes(),self.original)
        self.assertEqual(disk.raw,self.original)

    def test_strict_save_behavior_is_characterized_not_silently_changed(self):
        doc=PythonDocument(self.path)
        with self.assertRaisesRegex(SourceError,'syntax'):
            prepare_source_change(doc,'def compute(value):\n    return (\n')
        self.assertEqual(self.path.read_bytes(),self.original)

    def test_source_preview_reuses_original_crlf_encoding(self):
        self.path.write_bytes(b'def compute(value):\r\n    return value + 1\r\n')
        disk=PythonDocument(self.path)
        memory=preview_source_change(disk,'def compute(value):\n    return value + 3\n')
        self.assertEqual(memory.raw,b'def compute(value):\r\n    return value + 3\r\n')
        self.assertEqual(self.path.read_bytes(),disk.raw)

    def test_unicode_and_pep263_source_from_memory(self):
        initial=b'# coding: latin-1\nname = "caf\xe9"\n'
        self.path.write_bytes(initial)
        disk=PythonDocument(self.path)
        snapshot=preview_source_change(disk,'# coding: latin-1\nname = "caf\u00e9"\nanswer = 2\n')
        self.assertEqual(snapshot.encoding,'iso-8859-1')
        self.assertEqual(snapshot.raw,initial+b'answer = 2\n')
        self.assertEqual(self.path.read_bytes(),initial)

    def test_bom_and_non_bmp_source(self):
        source='def f():\n    return "\U0001f3af"\n'
        raw=b'\xef\xbb\xbf'+source.encode('utf-8')
        self.path.write_bytes(raw)
        snapshot=preview_source_change(PythonDocument(self.path),source.replace('return','return'))
        self.assertEqual(snapshot.raw,raw)
        self.assertEqual(snapshot.source,source)

    def test_mixed_line_endings_are_not_normalized_silently(self):
        self.path.write_bytes(b'a=1\r\nb=2\n')
        with self.assertRaisesRegex(SourceError,'Mixed line endings'):
            preview_source_change(PythonDocument(self.path),'a=2\nb=3\n')

    def test_bounded_and_typed_input(self):
        with self.assertRaisesRegex(SourceError,'Expected Python source bytes'):
            PythonDocument.from_bytes(self.path,'not bytes')
        with self.assertRaisesRegex(SourceError,'exceeds'):
            PythonDocument.from_bytes(self.path,b' '*(MAX_SOURCE+1))
        with self.assertRaisesRegex(SourceError,'analysis failed'):
            PythonDocument.from_bytes(self.path,b'\xff\xfe\x00')

    def test_external_write_blocks_stale_edit_even_after_preview(self):
        disk=PythonDocument(self.path)
        preview=preview_source_change(disk,'def compute(value):\n    return value + 6\n')
        proposal=prepare_source_change(disk,preview.source)
        self.path.write_bytes(b'# external edit\n')
        with self.assertRaisesRegex(SourceError,'changed externally'):
            apply_proposal(proposal)
        self.assertEqual(self.path.read_bytes(),b'# external edit\n')

    def test_import_side_effects_not_triggered_by_parsing(self):
        flag=Path(self.tmp.name)/'executed.flag'
        candidate=f'from pathlib import Path\nPath({str(flag)!r}).write_text("oops")\n'
        _=preview_source_change(PythonDocument(self.path),candidate)
        self.assertFalse(flag.exists())
        self.assertEqual(self.path.read_bytes(),self.original)

    def test_wrong_route_identity_refused_even_with_in_memory_snapshot(self):
        snap=PythonDocument.from_bytes(self.path,self.original)
        other=Path(self.tmp.name)/'other.py'
        other.write_text('pass\n')
        with self.assertRaisesRegex(ValueError,'identity'):
            resolve_graph(Route('source',str(other)),document=snap)

    def test_symlink_identity_rejected(self):
        link=Path(self.tmp.name)/'link.py'
        link.symlink_to(self.path)
        with self.assertRaisesRegex(SourceError,'Symlink'):
            PythonDocument.from_bytes(link,self.original)


if __name__=='__main__':unittest.main()
