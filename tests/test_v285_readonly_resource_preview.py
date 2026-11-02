"""v2.85: bounded text capability and explicit read-only resource policy."""
import unittest
import tempfile
from pathlib import Path
from studio_native.resource_graph import (directory_graph, expanded_file_preview, preview_kind,
    MAX_TEXT_PREVIEW_BYTES, MAX_TEXT_PREVIEW_LINES, MAX_TEXT_PREVIEW_COLUMNS)
from studio_native.semantic_contract import describe_graph

class TextResourceProjection(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)

    def put(self,name,data):
        path=self.root/name
        path.write_bytes(data if isinstance(data,bytes) else data.encode('utf-8'))
        return path

    def entry(self,graph,name):
        return next(item for item in graph['nodes'] if item.get('resource_path')==str(self.root/name))

    def test_default_collapsed_explicit_expand_no_write_or_second_owner(self):
        doc=self.put('notes.md','# Header\nHello, Studio!\n')
        original=doc.read_bytes()
        assert preview_kind(doc,'file')=='text'
        collapsed=directory_graph(self.root)
        self.assertIsNone(self.entry(collapsed,'notes.md')['resource_preview'])
        expanded=directory_graph(self.root,expanded_paths=(doc,))
        item=self.entry(expanded,'notes.md')
        self.assertEqual(item['resource_preview']['kind'],'text')
        self.assertIn('# Header',item['resource_preview']['text'])
        self.assertIsNone(item.get('embedded_region'))
        self.assertEqual(describe_graph(expanded,origin='resource').origin,'resource')
        self.assertEqual(doc.read_bytes(),original)
        self.assertEqual(item['id'],self.entry(collapsed,'notes.md')['id'])

    def test_common_text_types_share_existing_projection(self):
        for ext in ('txt','md','rst','json','toml','yaml','yml','ini','cfg','csv',
                    'tsv','xml','html','css','js','ts','sh','jsonl'):
            with self.subTest(ext=ext):
                path=self.put('document.'+ext,'example\n')
                self.assertEqual(preview_kind(path,'file'),'text')
                self.assertEqual(expanded_file_preview(path,'text')['text'],'example')
        self.assertEqual(preview_kind(self.put('private.env','TOKEN=secret'),'file'),'none')
        self.assertEqual(preview_kind(self.put('.secrets.json','{"key":1}'),'file'),'none')

    def test_only_bounded_prefix_visible_and_no_control_sequences(self):
        line='A'*100+'\x1b[31m\x00'
        path=self.put('long.txt','\n'.join(['line\t'+str(i)+' '+('c'*100) for i in range(30)]))
        preview=expanded_file_preview(path,'text')
        self.assertEqual(preview['kind'],'text')
        self.assertEqual(len(preview['text'].splitlines()),MAX_TEXT_PREVIEW_LINES)
        self.assertTrue(all(len(s)<=MAX_TEXT_PREVIEW_COLUMNS+1 for s in preview['text'].splitlines()))
        self.assertIn('more content',preview['status'])
        self.assertNotIn('\t',preview['text'])
        raw=self.put('control.md','one\x1b[31mred\x1b[0m\ntwo\n')
        clean=expanded_file_preview(raw,'text')
        self.assertNotIn('\x1b',clean['text'])
        self.assertTrue(clean['text'].startswith('one'))
        invalid=self.put('bad.txt',b'\xff\xfe')
        self.assertEqual(expanded_file_preview(invalid,'text')['status'],'Not valid UTF-8')
        binary=self.put('binary.csv',b'a,b\x00c')
        self.assertIn('Binary content',expanded_file_preview(binary,'text')['status'])

    def test_prefix_split_multibyte_refuses_bad_bytes_but_not_split_codepoint(self):
        path=self.put('unicode.md',b'A'*(MAX_TEXT_PREVIEW_BYTES-1)+b'\xe2\x82\xac\n')
        preview=expanded_file_preview(path,'text')
        self.assertTrue(preview['text'].startswith('AAAA'))
        self.assertIn('more content',preview['status'])
        self.assertEqual(path.read_bytes()[-4:],b'\xe2\x82\xac\n')

    def test_symlink_and_oversize_fail_closed(self):
        real=self.put('image.txt','good')
        link=self.root/'linked.txt';link.symlink_to(real)
        self.assertEqual(preview_kind(link,'symlink'),'none')
        self.assertEqual(self.entry(directory_graph(self.root,expanded_paths=(link,)),'linked.txt')['resource_preview'],None)
        large=self.put('huge.json',b'z'*8_000_001)
        self.assertIn('8 MB',expanded_file_preview(large,'text')['status'])

if __name__=='__main__': unittest.main()
