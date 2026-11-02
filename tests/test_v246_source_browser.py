"""Read-only Blueprint-like symbol navigation from the existing Python parser."""
from pathlib import Path
import tempfile
import unittest

from studio_native.python_graph import PythonDocument


class PythonSymbolBrowserTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'symbols.py'

    def symbols(self,source):
        self.path.write_text(source,encoding='utf-8')
        doc=PythonDocument(self.path)
        return doc,doc.browse_symbols()

    def test_lexical_hierarchy_and_location_not_duplicate_symbol_registry(self):
        doc,symbols=self.symbols('''threshold = 10

def outer(value, *, name="x"):
    total = value
    def inner(item):
        result = item + total
        return result
    return inner(value)
''')
        self.assertEqual([(s.kind,s.name,s.line) for s in symbols],[
            ('variable','threshold',1),('function','outer',3),
            ('parameter','value',3),('parameter','name',3),
            ('variable','total',4),('function','inner',5),
            ('parameter','item',5),('variable','result',6)])
        inner=next(s for s in symbols if s.name=='inner')
        self.assertEqual(doc.scopes[inner.scope].parent,
                         next(s.scope for s in symbols if s.name=='outer'))
        self.assertEqual(self.path.read_text(),doc.source)

    def test_classes_members_and_nested_methods_are_lexically_distinct(self):
        _,symbols=self.symbols('''class Tool:
    enabled = True
    def compute(self, count: int):
        value = count
        return value
''')
        self.assertEqual([(s.kind,s.name) for s in symbols],[
            ('class','Tool'),('variable','enabled'),('function','compute'),
            ('parameter','self'),('parameter','count'),('variable','value')])
        self.assertNotEqual(symbols[1].scope,symbols[3].scope)

    def test_no_dynamic_import_or_comprehension_false_locals(self):
        _,symbols=self.symbols('''import math
from os.path import join
value = 3

def calculate(sequence):
    numbers = [i for i in sequence]
    nested = lambda x: x + value
    return numbers
''')
        names={s.name for s in symbols}
        self.assertEqual(names,{'value','calculate','sequence','numbers','nested'})
        self.assertNotIn('i',names)
        self.assertNotIn('x',names)

    def test_nonlocals_globals_and_reassignments_not_misowned(self):
        _,symbols=self.symbols('''count = 0

def outer(value):
    total = value
    total += 1
    def inner():
        nonlocal total
        global count
        count += 1
        return total
    return inner()
''')
        self.assertEqual(sum(s.name=='total' for s in symbols),1)
        self.assertEqual(sum(s.name=='count' for s in symbols),1)
        self.assertNotIn('count',{s.name for s in symbols if s.scope!='module'})

    def test_bounded_empty_and_unicode_source(self):
        doc,symbols=self.symbols('def café(naïve):\n    résultat = naïve\n    return résultat\n')
        self.assertEqual([s.name for s in symbols],['café','naïve','résultat'])
        self.assertEqual(len(doc.browse_symbols(limit=2)),2)
        for bad in (0,-1,True,'10'):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                doc.browse_symbols(limit=bad)
        _,blank=self.symbols('# empty file\n')
        self.assertEqual(blank,())

    def test_invalidate_by_reparse_not_stale_index(self):
        self.path.write_text('def old(value):\n    pass\n')
        first=PythonDocument(self.path)
        self.path.write_text('def new(other):\n    pass\n')
        second=PythonDocument(self.path)
        self.assertEqual([s.name for s in first.browse_symbols()],['old','value'])
        self.assertEqual([s.name for s in second.browse_symbols()],['new','other'])

    def test_gui_reuses_existing_source_dock_and_parser(self):
        gui=(Path(__file__).parents[1]/'studio_native/gui.py').read_text()
        self.assertIn("self.source_library_pages.addTab(symbols,'My Python')",gui)
        self.assertIn("self.source_library_pages.addTab(operations,'Operations')",gui)
        self.assertIn('for symbol in self.python_doc.browse_symbols():',gui)
        self.assertIn('self.navigate_source(symbol.scope)',gui)
        self.assertIn('self.source_symbol_entries.itemDoubleClicked.connect(self._navigate_source_symbol)',gui)
        self.assertIn('self._create_qualified_operation(action.id,pin=pin',gui)


if __name__=='__main__':unittest.main()
