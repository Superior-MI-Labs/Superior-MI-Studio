"""Regression: adapter call-target tuple vs GUI anchor picker and modal binding."""
import ast
from pathlib import Path
import tempfile
import unittest

from studio_native.authoring_actions import qualified_composition_anchors, available_actions
from studio_native.authoring_contract import OperandReference, CallComposition
from studio_native.python_authoring import (
    eligible_composed_call_targets, eligible_composition_targets,
    eligible_value_assignment_targets, propose_composed_call,
)
from studio_native.python_graph import PythonDocument

ROOT=Path(__file__).resolve().parents[1]

class QualifiedCallBoundaryTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.path=Path(temp.name)/'module.py'
        self.path.write_text('def helper(x):\n    return x + 1\n\ndef caller(value):\n    return value\n')
        self.doc=PythonDocument(self.path)

    def test_call_catalog_has_signatures_and_gui_receives_anchors(self):
        targets=eligible_composed_call_targets(self.doc)
        self.assertTrue(targets)
        self.assertTrue(all(len(target)==4 for target in targets))
        gui=qualified_composition_anchors(self.doc,'python.call-with-values.v1')
        self.assertEqual(gui,tuple(target[:3] for target in targets))
        self.assertTrue(all(len(target)==3 for target in gui))
        self.assertEqual(gui,qualified_composition_anchors(self.doc,'python.call-with-values.v1'))
        self.assertEqual({action.id for action in available_actions(self.doc) if action.id=='python.call-with-values.v1'},
                         {'python.call-with-values.v1'})
        scope,names,anchor=next(target for target in gui if self.doc.scopes[target[0]].title=='caller')
        self.assertIn('value',names)
        self.assertIsInstance(anchor,dict)
        self.assertIn('line',anchor)
        self.assertIn('helper',dict(next(cal for key,_,_,cal in targets if key==scope)))
        proposal=propose_composed_call(self.doc,scope,CallComposition('helper',
                    (OperandReference('name','value'),),'stored',True),anchor)
        self.assertIn(b'stored = helper(value)',proposal.candidate)
        self.assertEqual(self.path.read_bytes(),proposal.original)

    def test_each_composition_operation_uses_one_three_field_picker_contract(self):
        expected={
            'python.call-with-values.v1':tuple(target[:3] for target in eligible_composed_call_targets(self.doc)),
            'python.compose-binary-local.v1':eligible_composition_targets(self.doc),
            'python.assign-source-local.v1':eligible_value_assignment_targets(self.doc),
        }
        for action,anchors in expected.items():
            with self.subTest(action=action):
                self.assertEqual(qualified_composition_anchors(self.doc,action),anchors)
                self.assertTrue(all(len(x)==3 for x in anchors))
        self.assertEqual(qualified_composition_anchors(None,'python.call-with-values.v1'),())
        self.assertEqual(qualified_composition_anchors(self.doc,'python.unknown'),())

    def test_production_and_smoke_use_keyword_only_dialog_contract(self):
        gui=ast.parse((ROOT/'studio_native/gui.py').read_text())
        native=next(node for node in ast.walk(gui) if isinstance(node,ast.ClassDef) and node.name=='NativeLab')
        dialog=next(node for node in native.body if isinstance(node,ast.FunctionDef) and node.name=='_ask_stored_call')
        self.assertEqual([arg.arg for arg in dialog.args.kwonlyargs],
                         ['scope','anchor','names','callees','preselected'])
        self.assertEqual(len(dialog.args.args),1)  # only self may be positional
        for source in (gui,ast.parse((ROOT/'studio_native/qt_smoke.py').read_text())):
            calls=[node for node in ast.walk(source) if isinstance(node,ast.Call) and
                   isinstance(node.func,ast.Attribute) and node.func.attr=='_ask_stored_call']
            self.assertTrue(calls)
            for call in calls:
                self.assertEqual(call.args,[])
                keywords={kw.arg for kw in call.keywords}
                self.assertTrue({'scope','anchor','names','callees'}<=keywords)
                self.assertEqual(len(keywords),len(call.keywords))

    def test_graph_creator_uses_shared_anchor_projection(self):
        source=ast.parse((ROOT/'studio_native/gui.py').read_text())
        handler=next(node for node in ast.walk(source) if isinstance(node,ast.FunctionDef)
                     and node.name=='_create_qualified_operation')
        calls=[node for node in ast.walk(handler) if isinstance(node,ast.Call) and
               isinstance(node.func,ast.Name) and node.func.id=='qualified_composition_anchors']
        self.assertEqual(len(calls),1)
        self.assertEqual(len(calls[0].args),2)

if __name__=='__main__':unittest.main()
