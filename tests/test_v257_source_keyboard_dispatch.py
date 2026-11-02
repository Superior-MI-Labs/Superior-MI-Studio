"""v2.57: focused source-history keyboard dispatch and view restoration contracts.

The event adapter can be exercised with Qt-compatible stubs when PyQt6 is
unavailable. The native qt_smoke test remains the release qualification.
"""
import ast
from enum import IntFlag
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT=Path(__file__).resolve().parents[1]


class _Modifiers(IntFlag):
    NoModifier=0
    ShiftModifier=1
    ControlModifier=2
    AltModifier=4


class _Widget:
    def __init__(self):
        self.unhandled=[]
    def event(self,event):
        self.unhandled.append(('event',event))
        return False
    def keyPressEvent(self,event):
        self.unhandled.append(('key',event))


class _Event:
    def __init__(self, key, mods, event_type=2, repeat=False):
        self._key=key
        self._mods=mods
        self._type=event_type
        self._repeat=repeat
        self.accepted=False
    def key(self):return self._key
    def modifiers(self):return self._mods
    def type(self):return self._type
    def isAutoRepeat(self):return self._repeat
    def accept(self):self.accepted=True


class SourceKeyboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        content=(ROOT/'studio_native/gui.py').read_text()
        tree=ast.parse(content)
        code=next(node for node in tree.body if isinstance(node,ast.ClassDef)
                  and node.name=='PythonSourceTextEdit')
        cls.editor_class_code=ast.get_source_segment(content,code)
        qt=SimpleNamespace(Key=SimpleNamespace(Key_Z=90,Key_A=65),
                           KeyboardModifier=_Modifiers)
        event_type=SimpleNamespace(Type=SimpleNamespace(ShortcutOverride=1))
        ns={'QPlainTextEdit':_Widget,'Qt':qt,'QEvent':event_type}
        exec(compile(ast.Module(body=[code],type_ignores=[]),
                     str(ROOT/'studio_native/gui.py'),'exec'),ns)
        cls.Editor=ns['PythonSourceTextEdit']

    def test_unmodified_key_is_passed_to_default_editor(self):
        editor=self.Editor(undo=lambda:None,redo=lambda:None)
        event=_Event(65,_Modifiers.NoModifier)
        editor.keyPressEvent(event)
        self.assertEqual(editor.unhandled,[('key',event)])
        self.assertFalse(event.accepted)

    def test_undo_and_redo_are_sent_to_session_owner_exactly_once(self):
        actions=[]
        editor=self.Editor(undo=lambda:actions.append('undo'),
                           redo=lambda:actions.append('redo'))
        for mods,expected in ((_Modifiers.ControlModifier,'undo'),
                              (_Modifiers.ControlModifier|_Modifiers.ShiftModifier,'redo')):
            override=_Event(90,mods,event_type=1)
            self.assertTrue(editor.event(override))
            self.assertTrue(override.accepted)
            key=_Event(90,mods)
            editor.keyPressEvent(key)
            self.assertTrue(key.accepted)
            self.assertEqual(actions[-1],expected)
        self.assertEqual(actions,['undo','redo'])
        self.assertEqual(editor.unhandled,[])

    def test_autorepeat_does_not_apply_multiple_history_transactions(self):
        calls=[]
        editor=self.Editor(undo=lambda:calls.append('undo'),redo=lambda:calls.append('redo'))
        for _ in range(3):
            event=_Event(90,_Modifiers.ControlModifier,repeat=True)
            editor.keyPressEvent(event)
            self.assertTrue(event.accepted)
        self.assertEqual(calls,[])

    def test_modified_other_keys_and_alt_z_pass_through(self):
        calls=[]
        editor=self.Editor(undo=lambda:calls.append('undo'),redo=lambda:calls.append('redo'))
        for key,mods in ((90,_Modifiers.ControlModifier|_Modifiers.AltModifier),
                         (65,_Modifiers.ControlModifier)):
            override=_Event(key,mods,event_type=1)
            self.assertFalse(editor.event(override))
            key_event=_Event(key,mods)
            editor.keyPressEvent(key_event)
            self.assertFalse(key_event.accepted)
        self.assertEqual(calls,[])
        self.assertEqual(len(editor.unhandled),4)

    def test_gui_binds_one_document_authority_without_qshortcuts(self):
        content=(ROOT/'studio_native/gui.py').read_text()
        tree=ast.parse(content)
        lab=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='NativeLab')
        methods={x.name:x for x in lab.body if isinstance(x,ast.FunctionDef)}
        build=ast.get_source_segment(content,methods['_build_source_editor'])
        nav=ast.get_source_segment(content,methods['_navigate_draft_history'])
        self.assertIn('PythonSourceTextEdit(undo=self.undo_source_draft, redo=self.redo_source_draft)',build)
        self.assertIn('setUndoRedoEnabled(False)',build)
        self.assertNotIn('QShortcut',build)
        self.assertIn('session.undo_draft',nav)
        self.assertIn('session.redo_draft',nav)
        self.assertIn('characterCount()-1',nav)


if __name__=='__main__':unittest.main()
