import tempfile
import unittest
from pathlib import Path
from studio_native.source_associations import local_python_symbol_candidates
from studio_native.resource_graph import directory_graph
from studio_native.semantic_contract import describe_graph


class SymbolCandidates(unittest.TestCase):
    def test_definition_evidence_on_import_edge(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/'main.py').write_text('from helper import add\n')
            (root/'helper.py').write_text('def add(a, b):\n    return a+b\n')
            candidates=local_python_symbol_candidates(root/'main.py',{root/'main.py',root/'helper.py'})
            self.assertEqual(len(candidates),1)
            self.assertEqual((candidates[0].symbol,candidates[0].declaration_line),('add',1))
            graph=directory_graph(root,show_imports=True)
            self.assertEqual(len(graph['edges']),1)
            evidence=describe_graph(graph,origin='resource').edges[0].evidence
            self.assertEqual(len(evidence),2)
            self.assertEqual(evidence[0].line,1)
            self.assertIn('FunctionDef add',evidence[1].syntax)

    def test_dynamic_or_missing_symbol_is_not_inferred(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/'main.py').write_text('from helper import unknown\n')
            (root/'helper.py').write_text('def known(): pass\n')
            self.assertEqual(local_python_symbol_candidates(root/'main.py',set(root.iterdir())),[])
            (root/'main.py').write_text('import importlib\nimportlib.import_module("helper")\n')
            self.assertEqual(local_python_symbol_candidates(root/'main.py',set(root.iterdir())),[])

    def test_does_not_execute_source(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);marker=root/'executed'
            (root/'main.py').write_text('from helper import fn\n')
            (root/'helper.py').write_text('def fn(): pass\n'+f'open({str(marker)!r},"w").write("bad")\n')
            self.assertTrue(local_python_symbol_candidates(root/'main.py',set(root.iterdir())))
            self.assertFalse(marker.exists())

if __name__=='__main__':unittest.main()
