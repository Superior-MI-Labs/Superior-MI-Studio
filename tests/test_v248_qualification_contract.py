"""Headless release contract checks for native-Qt catalog expansion.

PyQt6 is optional in headless testing; inspect the actual Qt source declaration
rather than shadowing the adapter in a second expected-operation registry.
"""
import ast
from pathlib import Path
import unittest

from studio_native.operation_catalog import qualified_operations

ROOT=Path(__file__).resolve().parents[1]


class QualificationCatalogContractTests(unittest.TestCase):
    def test_gui_builder_map_covers_every_adapter_qualified_operation(self):
        tree=ast.parse((ROOT/'studio_native/gui.py').read_text(encoding='utf-8'))
        maps=[]
        for node in ast.walk(tree):
            if not isinstance(node,ast.Subscript) or not isinstance(node.value,ast.Dict):
                continue
            if not isinstance(node.slice,ast.Attribute) or node.slice.attr!='id':
                continue
            try:
                mapping=ast.literal_eval(node.value)
            except (ValueError,TypeError):
                continue
            if isinstance(mapping,dict) and mapping and all(
                    isinstance(k,str) and k.startswith('python.') for k in mapping):
                maps.append(mapping)
        self.assertEqual(len(maps),1,'Expected one Qt builder mapping for the adapter catalog')
        mapping=maps[0]
        self.assertEqual(set(mapping),{definition.id for definition in qualified_operations('python')})
        self.assertEqual(len(set(mapping.values())),len(mapping),'Qt builder object names must be unique')
        self.assertEqual(mapping['python.assign-source-local.v1'],'QualifiedPythonValueAssignment')

    def test_native_smoke_is_not_pinned_to_old_catalog_size(self):
        tree=ast.parse((ROOT/'studio_native/qt_smoke.py').read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if not isinstance(node,ast.Compare):
                continue
            for side in [node.left,*node.comparators]:
                if not isinstance(side,ast.Call) or not isinstance(side.func,ast.Name) or side.func.id!='len':
                    continue
                if len(side.args)!=1:continue
                target=side.args[0]
                is_catalog=(isinstance(target,ast.Call) and isinstance(target.func,ast.Name)
                            and target.func.id=='qualified_operations')
                is_builder=(isinstance(target,ast.Attribute) and target.attr=='source_builder_buttons')
                if not (is_catalog or is_builder):continue
                self.assertFalse(any(isinstance(arg,ast.Constant) and
                                     type(arg.value) is int for arg in [node.left,*node.comparators]),
                                 'Native smoke must compare builders to actual adapter catalog, not a literal count')


if __name__=='__main__':unittest.main()
