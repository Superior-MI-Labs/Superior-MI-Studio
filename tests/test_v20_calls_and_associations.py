"""Source-derived module call sites and bounded filesystem associations."""
import tempfile
import unittest
from pathlib import Path
from studio_native.python_graph import PythonDocument
from studio_native.resource_graph import directory_graph
from studio_native.semantic_contract import describe_graph
from studio_native.source_associations import local_python_imports


class V20Tests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)

    def write(self,name,content):
        path=self.root/name
        path.write_text(content,encoding='utf-8')
        return path

    def test_module_if_has_distinct_real_call_sites(self):
        source=self.write('main.py',"def combine(a, b):\n    return a + b\n\nif __name__ == '__main__':\n    print(combine(2, 3))\n")
        doc=PythonDocument(source)
        graph=doc.composite_file_graph(set(),detail='readable')
        calls={n['call_direct_name']:n for n in graph['nodes'] if n.get('call_expression')}
        self.assertEqual(set(calls),{'print','combine'})
        self.assertEqual(calls['print']['source_span']['line'],5)
        self.assertEqual(calls['combine']['source_span']['line'],5)
        self.assertNotEqual(calls['print']['id'],calls['combine']['id'])
        self.assertTrue(any(e['source']==calls['combine']['id'] and e['target']==calls['print']['id'] and e['relation']=='data' for e in graph['edges']))
        self.assertEqual(calls['combine']['containing_scope'],calls['print']['containing_scope'])
        self.assertEqual(calls['combine']['containing_scope'],'module')
        self.assertTrue(any(n.get('source_kind')=='branch' and
                            n.get('semantic_role')=='control_operation' for n in graph['nodes']))
        self.assertEqual(len(describe_graph(graph,origin='source').edges),len(graph['edges']))


    def test_module_call_metadata_not_runtime_claim(self):
        source=self.write('example.py','''def foo():\n    return 1\n\nfoo = lambda: 2\nfoo()\n''')
        graph=PythonDocument(source).scope_graph()
        calls=[n for n in graph['nodes'] if n.get('call_expression')]
        self.assertEqual(len(calls),1)
        self.assertEqual(calls[0]['call_direct_name'],'foo')
        # Rebinding can change runtime dispatch: this is a *source reference*,
        # not a claim that the original definition will execute.
        self.assertTrue(any(e['relation']=='call' and e['target']==calls[0]['id']
                            for e in graph['edges']))

    def test_no_extra_call_node_for_unexecuted_function_body(self):
        source=self.write('safe.py','''def not_run():\n    raise RuntimeError('do not run')\n    print('unreachable')\n''')
        graph=PythonDocument(source).scope_graph()
        self.assertFalse(any(n.get('call_expression') for n in graph['nodes']))

    def test_static_local_candidate_edges_opt_in(self):
        self.write('util.py','def add(a, b): return a + b\n')
        self.write('main.py','from util import add\nprint(add(1, 2))\n')
        plain=directory_graph(self.root)
        self.assertEqual(plain['edges'],[])
        annotated=directory_graph(self.root,show_imports=True)
        self.assertEqual(len(annotated['edges']),1)
        link=annotated['edges'][0]
        self.assertEqual(link['certainty'],'local-file-candidate')
        self.assertEqual(link['provenance'][0]['line'],1)
        self.assertEqual(link['provenance'][0]['syntax'],'from util import add')
        descriptor=describe_graph(annotated,origin='resource')
        self.assertEqual(len(descriptor.edges),1)
        self.assertEqual(descriptor.edges[0].certainty,'local-file-candidate')
        self.assertEqual(descriptor.edges[0].evidence[0].line,1)
        self.assertEqual(descriptor.edges[0].evidence[0].syntax,'from util import add')
        self.assertEqual([n['id'] for n in plain['nodes']],
                         [n['id'] for n in annotated['nodes']])

    def test_import_missing_external_and_dynamic_are_not_guessed(self):
        main=self.write('main.py','''import json\nimport missing\n__import__('util')\n''')
        util=self.write('util.py','def test(): pass\n')
        self.assertEqual(local_python_imports(main,{main,util}),[])
        self.assertEqual(directory_graph(self.root,show_imports=True)['edges'],[])

    def test_symlink_candidate_is_not_followed(self):
        main=self.write('main.py','import util\n')
        other=self.write('outside.py','raise Exception()\n')
        symlink=self.root/'util.py';symlink.symlink_to(other)
        self.assertEqual(local_python_imports(main,{main,symlink}),[])

    def test_candidate_parser_never_executes_source(self):
        marker=self.root/'marker.txt'
        self.write('util.py','pass\n')
        main=self.write('main.py',f'''import util\nfrom pathlib import Path\nPath({str(marker)!r}).write_text('EXECUTED')\n''')
        directory_graph(self.root,show_imports=True)
        self.assertFalse(marker.exists())

    def test_invalid_python_is_safe_and_not_opened(self):
        bad=self.write('main.py','import util\ndef x(:\n')
        util=self.write('util.py','pass\n')
        self.assertEqual(local_python_imports(bad,{bad,util}),[])

    def test_candidate_paging_does_not_link_invisible_files(self):
        self.write('main.py','import util\n')
        self.write('util.py','pass\n')
        # 72 entries on the first page are all not necessarily both files.
        for i in range(85):self.write(f'f{i:03}.py','pass\n')
        first=directory_graph(self.root,show_imports=True)
        ids={n['id'] for n in first['nodes']}
        self.assertTrue(all(e['source'] in ids and e['target'] in ids
                            for e in first['edges']))

if __name__=='__main__':unittest.main()

class ModuleAssignmentCallTests(unittest.TestCase):
    def test_module_initializer_call_is_explicit_and_wired(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'m.py'
            p.write_text('''def f(): return 4\n\nresult = f()\n''')
            g=PythonDocument(p).composite_file_graph(set(),detail='readable')
            call=next(n for n in g['nodes'] if n.get('call_expression'))
            var=next(n for n in g['nodes'] if n['source_kind']=='variable' and n['title']=='result')
            self.assertTrue(any(e['source']==call['id'] and e['target']==var['id']
                                and e['relation']=='data' for e in g['edges']))
            self.assertEqual(len(describe_graph(g,origin='source').nodes),len(g['nodes']))
