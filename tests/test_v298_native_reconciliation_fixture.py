"""Regression for v2.97 Qt failure: no-op fixtures and cross-stage graph leakage.

Pure-model replay of the native Qt sequence. The GUI test must use compiler
line maps to create a real independent-source edit, then restore its graph
before the next linked-source scenario. All production owners are exercised.
"""
import ast
import tempfile
import unittest
from pathlib import Path

from studio_native.program_graph import ProgramGraph
from studio_native.python_lowering import (
    preview_python, LinkedPythonSource, review_independent_source_function,
    import_independent_source_function, review_independent_source_functions,
)
from studio_native.source_editor import SourceDocumentSession

EXAMPLE=Path(__file__).resolve().parents[1]/'examples/qualified-integer-program.smi-graph'


class NativeReconciliationFixtureContract(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.graph=ProgramGraph.open(EXAMPLE)
        self.graph.edit(self.graph.revision,'set_property',node='one',key='value',value=24)
        self.base=preview_python(self.graph.state).source
        self.linked=self.root/'linked.py'
        self.linked.write_text(self.base,encoding='utf-8')
        self.source=SourceDocumentSession.open(self.linked)
        self.link=LinkedPythonSource.attach(self.graph,self.source)

    def test_independent_edit_must_differ_from_current_compiler_source(self):
        preview=preview_python(self.graph.state)
        mapped=dict(preview.node_lines)['one']
        assignment=[node for node in ast.walk(ast.parse(preview.source))
                    if isinstance(node,ast.Assign) and node.lineno==mapped][0]
        self.assertEqual(assignment.value.value,24)
        # v2.97's smoke wrongly tried to replace '25' on this baseline.
        self.assertEqual(preview.source.replace('_smi_value_0 = 25','_smi_value_0 = 31'),
                         preview.source,'The failing fixture was a silent no-op')
        # The source owner has an unrelated module item, which stays opaque.
        altered=preview.source.replace('_smi_value_0 = 24','_smi_value_0 = 31')
        foreign=self.root/'foreign.py';foreign.write_text('import math\n\n'+altered)
        session=SourceDocumentSession.open(foreign)
        receipt=review_independent_source_function(self.graph,session,'increment',
            expected_graph_revision=self.graph.revision)
        self.assertEqual([(c.function,c.node_id,c.before,c.after) for c in receipt.changes],
                         [('increment','one',24,31)])
        self.assertEqual(receipt.change_lines,(('increment','one',10),))
        original=self.graph.state
        self.assertTrue(import_independent_source_function(self.graph,session,'increment',
            expected_graph_revision=receipt.graph_revision,
            expected_source_revision=receipt.source_revision,
            expected_source_sha256=receipt.source_sha256))
        self.assertTrue(self.graph.undo(self.graph.revision))
        self.assertEqual(preview_python(self.graph.state).source,self.base)
        self.assertTrue(self.graph.redo(self.graph.revision))
        self.assertTrue(self.graph.undo(self.graph.revision))
        self.assertEqual(self.graph.state['nodes'],original['nodes'])
        # The next source-linked test is still permitted to import its OWN edit.
        self.source.update(self.base.replace('_smi_value_0 = 24','_smi_value_0 = 25'))
        review=self.link.review_edits()
        self.assertEqual([(c.node_id,c.after) for c in review.changes],[('one',25)])
        self.assertTrue(self.link.import_edits())
        self.assertIn('_smi_value_0 = 25',preview_python(self.graph.state).source)
        self.assertEqual(foreign.read_text(), 'import math\n\n'+altered)

    def test_review_lines_are_source_owner_locations_after_reordering_and_trivia(self):
        source=preview_python(self.graph.state).source
        compose=source.split('def compose(y):',1)[1].split('\ndef increment(x):',1)[0]
        increment=source.split('def increment(x):',1)[1]
        authored=('import os\n\n# unrelated text\ndef helper():\n    pass\n\n'
                  'def increment(x):'+increment.replace('_smi_value_0 = 24','_smi_value_0 = 90')+
                  '\n\n# extra source-only text\ndef compose(y):'+
                  compose.replace('_smi_value_1 * _smi_value_1','_smi_value_1 + _smi_value_1'))
        foreign=self.root/'foreign.py';foreign.write_text(authored)
        receipt=review_independent_source_functions(
            self.graph,SourceDocumentSession.open(foreign),('compose','increment'),
            expected_graph_revision=self.graph.revision)
        lines=authored.splitlines()
        self.assertEqual({(fn,node):lines[line-1].strip() for fn,node,line in receipt.change_lines},
                         {('increment','one'):'_smi_value_0 = 90',
                          ('compose','mul'):'_smi_value_2 = _smi_value_1 + _smi_value_1'})
        self.assertEqual(len(receipt.changes),2)

    def test_empty_reconciliation_is_not_a_compiler_failure(self):
        foreign=self.root/'foreign.py'
        foreign.write_text('import os\n\n'+self.base)
        receipt=review_independent_source_function(self.graph,
            SourceDocumentSession.open(foreign),'increment',
            expected_graph_revision=self.graph.revision)
        self.assertEqual(receipt.changes,())
        self.assertEqual(receipt.change_lines,())


if __name__=='__main__':unittest.main()

class IndependentSignatureConflictDiagnostics(unittest.TestCase):
    def test_signature_mutations_refused_at_actual_source_line(self):
        from studio_native.program_graph import ProgramGraph, ProgramGraphError
        with tempfile.TemporaryDirectory() as tmp:
            graph=ProgramGraph.open(EXAMPLE)
            original=preview_python(graph.state).source
            for changed in (
                'def increment(y):', 'def increment(x=1):',
                'def increment(x: int):', 'def increment(x, y):',
                'def increment(*, x):', 'def increment(x) -> int:',
            ):
                with self.subTest(changed=changed):
                    target=original.replace('def increment(x):',changed,1)
                    self.assertNotEqual(original,target)
                    path=Path(tmp)/'signature.py';path.write_text(target)
                    session=SourceDocumentSession.open(path)
                    with self.assertRaisesRegex(ProgramGraphError,
                                                 r"Function 'increment' \(source line 7\): signature differs"):
                        review_independent_source_function(graph,session,'increment',
                            expected_graph_revision=graph.revision)
                    self.assertFalse(graph.dirty)

class NativeSmokeContractTests(unittest.TestCase):
    def test_qt_smoke_does_not_assert_gui_undo_returns_true(self):
        # ProgramWorkspace.undo() is a void Qt UI command. The boolean return
        # belongs to ProgramGraph.undo(), and the smoke must assert the actual
        # graph state rather than truthiness of a void button handler.
        qa=(Path(__file__).resolve().parents[1]/'studio_native/qt_smoke.py').read_text()
        self.assertNotIn('assert roundtrip.undo()',qa)
        self.assertNotIn('assert roundtrip.redo()',qa)
        self.assertIn("assert roundtrip.document.state['nodes']==before_foreign['nodes']",qa)

    def test_smoke_replacements_use_checked_api_not_stale_noop(self):
        qa=(Path(__file__).resolve().parents[1]/'studio_native/qt_smoke.py').read_text()
        self.assertIn("_alter_compiled_literal(independent_preview,'one',31)",qa)
        self.assertIn('def _replace_once_for_smoke(',qa)
        lines=[line.strip() for line in qa.splitlines()]
        self.assertEqual([line for line in lines if '.replace(' in line],
                         ['changed=source.replace(old,new,1)'])
