"""Both cross-provider directions publish to the destination registry.

This regression would have caught the v2.128 GitHub Qt failure: the source view
was incorrectly stored in the resource registry after a successful transition.
"""
import ast
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'studio_native/gui.py').read_text(encoding='utf-8')
cls=next(x for x in ast.parse(source).body if isinstance(x,ast.ClassDef) and x.name=='NativeLab')
method=next(x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name=='_transition_graph_tab')
code=ast.unparse(method)


class DestinationRegistryTests(unittest.TestCase):
    def test_outgoing_kind_only_retires_and_destination_kind_only_registers(self):
        outgoing=code.index("if old_kind == 'source':",code.index('old.canvas._save_root_view()'))
        destination=code.index("if route.kind == 'source':",outgoing)
        between=code[outgoing:destination]
        self.assertIn('del self._source_tabs[old.session_id]',between)
        self.assertIn('del self._resource_tabs[old.session_id]',between)
        self.assertNotIn('self._source_tabs[old.session_id] = view',between)
        self.assertNotIn('self._resource_tabs[old.session_id] = view',between)
        registered=code[destination:code.index('session.activate(resolved.route',destination)]
        self.assertIn('self._source_tabs[old.session_id] = view',registered)
        self.assertIn('self._resource_tabs[old.session_id] = view',registered)
        self.assertLess(code.index('page = self._graph_page(canvas)'),destination)

    def test_qt_smoke_exercises_both_provider_directions_and_owner(self):
        smoke=(ROOT/'studio_native/qt_smoke.py').read_text(encoding='utf-8')
        self.assertIn("assert mixed_id in w._source_tabs and mixed_id not in w._resource_tabs",smoke)
        self.assertIn("assert mixed_id in w._resource_tabs and mixed_id not in w._source_tabs",smoke)
        self.assertIn('assert w._active_source_document() is owner',smoke)
        self.assertIn('QT_STAGE cross-provider-replacement-staging-refusal',smoke)


if __name__=='__main__':unittest.main()
