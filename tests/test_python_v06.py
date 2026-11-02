"""v0.6 regression: guarded local reads and positional-call source edits.

No code is executed by these tests: all candidates are parsed/compiled only.
"""
import tempfile
import unittest
from pathlib import Path
from studio_native.python_graph import PythonDocument, SourceError
from studio_native.python_edit import rewire_source_operand, apply_proposal


class SourceEditV06Tests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path=Path(self.directory.name)/'test.py'

    def graph(self, source):
        self.path.write_text(source,encoding='utf-8')
        doc=PythonDocument(self.path)
        key=next(k for k,v in doc.scopes.items() if k!='module' and v.kind=='function')
        return doc,key,doc.scope_graph(key)

    @staticmethod
    def choose(graph,kind,subtitle=None):
        return next(n for n in graph['nodes'] if n['source_kind']==kind and
                    (subtitle is None or subtitle in n.get('subtitle','')))

    @staticmethod
    def port(node,side,index=0):
        return node['draft_ports'][side][index]['id']

    def test_copy_literal_to_positional_call_argument(self):
        src='''def demo(x):
    y = max(x, 100)
    z = 9
    return min(3, y)
'''
        doc,key,g=self.graph(src)
        nine=self.choose(g,'literal','9')
        call=self.choose(g,'call','min(3, y)')
        dst=next(p['id'] for p in call['draft_ports']['inputs'] if p['id'].endswith(':arg0'))
        proposal=rewire_source_operand(doc,key,nine['id'],self.port(nine,'outputs'),call['id'],dst)
        self.assertIn('min(9, y)',proposal.candidate.decode())
        self.assertNotIn('min(9, y)',self.path.read_text())
        self.assertEqual(self.path.read_text(),src)
        backup=apply_proposal(proposal)
        self.assertEqual(backup.read_text(),src)
        self.assertIn('min(9, y)',self.path.read_text())

    def test_parameter_to_call_arg_and_invalid_port(self):
        src='''def demo(x):
    return max(1, 2)
'''
        doc,key,g=self.graph(src)
        param=self.choose(g,'param')
        call=self.choose(g,'call')
        dst=next(p['id'] for p in call['draft_ports']['inputs'] if p['id'].endswith(':arg1'))
        result=rewire_source_operand(doc,key,param['id'],self.port(param,'outputs'),call['id'],dst)
        self.assertIn('max(1, x)',result.candidate.decode())
        with self.assertRaises(SourceError):
            rewire_source_operand(doc,key,param['id'],self.port(param,'outputs'),call['id'],dst.replace('arg1','arg7'))
        callee=next((p['id'] for p in call['draft_ports']['inputs'] if p['id'].endswith(':callee')),None)
        if callee:
            with self.assertRaises(SourceError):
                rewire_source_operand(doc,key,param['id'],self.port(param,'outputs'),call['id'],callee)

    def test_local_assignment_to_later_comparison(self):
        src='''def demo(x):
    count = x + 1
    ok = x > 5
    return ok
'''
        doc,key,g=self.graph(src)
        assignment=self.choose(g,'assignment','count')
        compare=self.choose(g,'compare')
        rhs=next(p['id'] for p in compare['draft_ports']['inputs'] if p['id'].endswith(':rhs'))
        proposal=rewire_source_operand(doc,key,assignment['id'],self.port(assignment,'outputs'),compare['id'],rhs)
        self.assertIn('ok = x > count',proposal.candidate.decode())

    def test_refuse_local_assignment_defined_after_use(self):
        src='''def demo(x):
    ok = x > 5
    count = x + 1
    return ok
'''
        doc,key,g=self.graph(src)
        assignment=self.choose(g,'assignment','count')
        compare=self.choose(g,'compare')
        rhs=next(p['id'] for p in compare['draft_ports']['inputs'] if p['id'].endswith(':rhs'))
        with self.assertRaisesRegex(SourceError,'does not precede'):
            rewire_source_operand(doc,key,assignment['id'],self.port(assignment,'outputs'),compare['id'],rhs)

    def test_refuse_cross_branch_local(self):
        src='''def demo(x):
    if x > 1:
        count = 5
    ok = x > 7
    return ok
'''
        doc,key,g=self.graph(src)
        assignment=self.choose(g,'assignment','count')
        compare=next(n for n in g['nodes'] if n['source_kind']=='compare' and 'x > 7' in n['subtitle'])
        rhs=next(p['id'] for p in compare['draft_ports']['inputs'] if p['id'].endswith(':rhs'))
        with self.assertRaises(SourceError):
            rewire_source_operand(doc,key,assignment['id'],self.port(assignment,'outputs'),compare['id'],rhs)

    def test_refuse_local_rebound_before_use(self):
        src='''def demo(x):
    count = 1
    count = 2
    ok = x > 5
    return ok
'''
        doc,key,g=self.graph(src)
        first=next(n for n in g['nodes'] if n['source_kind']=='assignment' and 'count = 1' in n['containers'][0]['rows'][0]['value'])
        compare=self.choose(g,'compare')
        rhs=next(p['id'] for p in compare['draft_ports']['inputs'] if p['id'].endswith(':rhs'))
        with self.assertRaisesRegex(SourceError,'rebound'):
            rewire_source_operand(doc,key,first['id'],self.port(first,'outputs'),compare['id'],rhs)

    def test_refuse_effect_before_local_use(self):
        src='''def demo(x):
    count = 1
    print(x)
    ok = x > 5
    return ok
'''
        doc,key,g=self.graph(src)
        first=self.choose(g,'assignment','count')
        compare=self.choose(g,'compare')
        rhs=next(p['id'] for p in compare['draft_ports']['inputs'] if p['id'].endswith(':rhs'))
        with self.assertRaises(SourceError):
            rewire_source_operand(doc,key,first['id'],self.port(first,'outputs'),compare['id'],rhs)


if __name__=='__main__':
    unittest.main()
