"""Protect host-only GUI smoke tests from cross-stage tab/document contamination.

These structural guards intentionally do not claim to run Qt without PyQt6;
actual cleanup and keyboard interactions remain native host acceptance tests.
"""
import ast
import unittest
from pathlib import Path

SMOKE = Path(__file__).resolve().parents[1] / 'studio_native' / 'qt_smoke.py'


def _calls(function):
    return [node for node in ast.walk(function) if isinstance(node, ast.Call)]


def _called_name(call):
    func = call.func
    return func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else None)


class QtStageIsolationContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SMOKE.read_text(encoding='utf-8')
        cls.tree = ast.parse(cls.source)
        cls.functions = {node.name: node for node in cls.tree.body if isinstance(node, ast.FunctionDef)}

    def test_document_lifecycle_stage_runs_in_its_own_window(self):
        fixture = self.functions['exercise_revisioned_source_session']
        main = self.functions['main']
        fixture_calls = {_called_name(call) for call in _calls(fixture)}
        main_calls = {_called_name(call) for call in _calls(main)}
        self.assertIn('NativeLab', fixture_calls)
        self.assertIn('open_source_in_new_tab', fixture_calls)
        self.assertIn('close', fixture_calls)
        self.assertIn('exercise_revisioned_source_session', main_calls)

    def test_navigation_restores_exact_tab_membership(self):
        main = self.functions['main']
        # Compare the registry before and after a view closes; a global literal
        # count cannot distinguish a newly leaked tab from a legitimate tab.
        assigned_names = {target.id for node in ast.walk(main)
                          if isinstance(node, ast.Assign) for target in node.targets
                          if isinstance(target, ast.Name)}
        self.assertIn('source_tab_ids_before', assigned_names)
        self.assertIn('source_tab_ids_before', ast.unparse(main))
        self.assertIn('Document-history fixture leaked source tabs', ast.unparse(main))


if __name__ == '__main__':
    unittest.main()
