"""Graph-owned Python publication and semantic types, including adversarial refusals."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from studio_native.program_graph import ProgramGraph, GraphConflict, template_ports
from studio_native.python_graph import SourceError
from studio_native.python_lowering import preview_python, publish_python


class PublicationTests(unittest.TestCase):
    def setUp(self):
        from tests.test_v266_python_lowering import PreviewTests
        self.builder = PreviewTests('test_full_function_matches_explicit_reference')

    def graph(self):
        return self.builder.graph()

    def test_publish_new_exact_source_separate_from_graph(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            graph=self.graph()
            graph.save(path/'graph.smi-graph')
            original=(path/'graph.smi-graph').read_bytes()
            output=path/'created.py'
            result=publish_python(graph,output,expected_revision=graph.revision)
            expected=preview_python(graph.state)
            self.assertEqual(output.read_text(),expected.source)
            self.assertEqual(result.source_sha256,hashlib.sha256(output.read_bytes()).hexdigest())
            self.assertEqual(result.graph_sha256,hashlib.sha256(original).hexdigest())
            self.assertEqual(result.node_lines,expected.node_lines)
            self.assertEqual(graph.path.read_bytes(),original)
            self.assertFalse(graph.dirty)
            self.assertEqual(output.stat().st_mode & 0o777,0o600)
            with self.assertRaises(SourceError):
                publish_python(graph,output,expected_revision=graph.revision)
            self.assertEqual(output.read_text(),expected.source)

    def test_publication_rejects_unsaved_dirty_and_stale_graph(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            graph=self.graph()
            with self.assertRaises(GraphConflict):
                publish_python(graph,root/'missing.py',expected_revision=graph.revision)
            self.assertFalse((root/'missing.py').exists())
            graph.save(root/'program.smi-graph')
            revision=graph.revision
            graph.edit(revision,'move_node',node='one',x=12,y=25)
            with self.assertRaises(GraphConflict):
                publish_python(graph,root/'dirty.py',expected_revision=revision)
            with self.assertRaises(GraphConflict):
                publish_python(graph,root/'dirty.py',expected_revision=graph.revision)
            self.assertFalse((root/'dirty.py').exists())
            graph.save(graph.path)
            graph.path.write_bytes(graph.path.read_bytes()+b' ')
            with self.assertRaises(GraphConflict):
                publish_python(graph,root/'changed.py',expected_revision=graph.revision)
            self.assertFalse((root/'changed.py').exists())

    def test_incomplete_and_unqualified_never_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            graph=self.graph()
            graph.edit(graph.revision,'disconnect',edge=graph.state['edges'][0]['id'])
            graph.save(root/'invalid.smi-graph')
            with self.assertRaises(GraphConflict):
                publish_python(graph,root/'output.py',expected_revision=graph.revision)
            self.assertFalse((root/'output.py').exists())

    def test_existing_source_preimage_requires_exact_explicit_digest_and_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            graph=self.graph();graph.save(root/'valid.smi-graph')
            output=root/'existing.py'
            before=b'# user data\n';output.write_bytes(before)
            with self.assertRaises(SourceError):
                publish_python(graph,output,expected_revision=graph.revision)
            with self.assertRaises(SourceError):
                publish_python(graph,output,expected_revision=graph.revision,
                               expected_target_sha256='0'*64)
            self.assertEqual(output.read_bytes(),before)
            result=publish_python(graph,output,expected_revision=graph.revision,
                     expected_target_sha256=hashlib.sha256(before).hexdigest())
            self.assertEqual(output.read_text(),preview_python(graph.state).source)
            self.assertEqual((root/'existing.py.smi-backup').read_bytes(),before)
            self.assertEqual(result.source_sha256,hashlib.sha256(output.read_bytes()).hexdigest())
            with self.assertRaises(SourceError):
                publish_python(graph,output,expected_revision=graph.revision,
                     expected_target_sha256=hashlib.sha256(before).hexdigest())

    def test_symlink_destination_refused_and_target_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            graph=self.graph();graph.save(root/'valid.smi-graph')
            target=root/'target.py';target.write_text('secret=1\n')
            link=root/'alias.py';link.symlink_to(target)
            with self.assertRaises(SourceError):
                publish_python(graph,link,expected_revision=graph.revision)
            self.assertEqual(target.read_text(),'secret=1\n')
            with self.assertRaises(SourceError):
                publish_python(graph,root/'not_python.txt',expected_revision=graph.revision)

    def test_competing_publishers_only_one_wins(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            graph=self.graph();graph.save(root/'program.smi-graph')
            output=root/'race.py'
            code='''from studio_native.python_lowering import publish_python
from studio_native.program_graph import ProgramGraph
import sys
p=ProgramGraph.open(sys.argv[1]);publish_python(p,sys.argv[2],expected_revision=p.revision)
'''
            env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1])}
            children=[subprocess.Popen([sys.executable,'-c',code,str(graph.path),str(output)],
                     env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE) for _ in range(2)]
            results=[p.communicate(timeout=15) for p in children]
            self.assertEqual(sorted(p.returncode for p in children),[0,1],results)
            self.assertEqual(output.read_text(),preview_python(graph.state).source)

    def test_boolean_comparison_and_function_call_roundtrip(self):
        p=self.builder
        graph=self.graph()
        p.edit(graph,'add_function',id='fn-check',name='is_small')
        p.edit(graph,'add_parameter',function='fn-check',id='param-val',name='value',type='py:int')
        p.edit(graph,'set_return_type',function='fn-check',type='py:bool')
        p.node(graph,'fn-check','arg','python.parameter',props={'parameter_id':'param-val'})
        p.node(graph,'fn-check','limit','python.literal',props={'value':10})
        p.node(graph,'fn-check','compare','python.less_than')
        p.node(graph,'fn-check','check_return','python.return')
        p.wire(graph,'arg','value','compare','left')
        p.wire(graph,'limit','value','compare','right')
        p.wire(graph,'compare','result','check_return','value')
        result=preview_python(graph.state)
        self.assertFalse(result.issues,result.issues)
        namespace={};exec(result.source,namespace)
        self.assertIs(namespace['is_small'](9),True)
        self.assertIs(namespace['is_small'](11),False)
        # A bool value cannot be passed to an integer return, even though bool is int in Python.
        p.node(graph,'fn-increment','boolcall','python.call',props={'callee_id':'fn-check'},
                 inputs=[{'name':'value','type':'py:int'}],outputs=[{'name':'result','type':'py:bool'}])
        p.wire(graph,'parameter','value','boolcall','value')
        p.edit(graph,'replace_input',source='boolcall',source_port='boolcall-result',
               target='sum',target_port='sum-left')
        self.assertIn('py:bool',str(preview_python(graph.state).issues))

    def test_subtraction_and_explicit_port_type_contract(self):
        p=self.builder;graph=self.graph()
        p.edit(graph,'remove_node',node='sum')
        p.node(graph,'fn-increment','difference','python.subtract')
        p.wire(graph,'parameter','value','difference','left')
        p.wire(graph,'one','value','difference','right')
        p.wire(graph,'difference','result','return','value')
        result=preview_python(graph.state)
        self.assertFalse(result.issues,result.issues)
        namespace={};exec(result.source,namespace)
        self.assertEqual(namespace['increment'](10),9)
        state=graph.state
        node=next(n for n in state['nodes'] if n['id']=='difference')
        node['ports']['outputs'][0]['type']='py:bool'
        self.assertIn('require',str(preview_python(state).issues))

    def test_cli_publication_does_not_run_program(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);graph=self.graph();graph.save(root/'g.smi-graph')
            output=root/'new.py'
            run=subprocess.run([sys.executable,'-m','studio_native.python_lowering',
                 str(graph.path),'--publish',str(output)],capture_output=True,text=True,timeout=10)
            self.assertEqual(run.returncode,0,run.stderr)
            self.assertIn('PYTHON_PUBLICATION_PASS',run.stdout)
            self.assertTrue(output.exists())
            rerun=subprocess.run([sys.executable,'-m','studio_native.python_lowering',
                 str(graph.path),'--publish',str(output)],capture_output=True,text=True,timeout=10)
            self.assertEqual(rerun.returncode,2)
            self.assertIn('refused',rerun.stderr.lower())

if __name__=='__main__':unittest.main()
