"""Qt-free universal view-route tests; never change program/resource authority."""
import tempfile
import unittest
from pathlib import Path
from studio_native.navigation import Route, Crumb, NavigationHistory, resource_crumbs, source_crumbs
from studio_native.python_graph import PythonDocument


SOURCE = '''\ndef icon_hint(role):\n    if not role:\n        return 'missing'\n    def nested(value):\n        return role + value\n    return nested('ok')\n'''


class NavigationTests(unittest.TestCase):
    def test_resource_trail_roundtrips_absolute_paths(self):
        crumbs=resource_crumbs('/home/emerson/Downloads/SMI-NodeLab-Logs')
        self.assertEqual([c.text for c in crumbs], ['/', 'home', 'emerson', 'Downloads', 'SMI-NodeLab-Logs'])
        self.assertEqual(crumbs[0].route.path,'/')
        self.assertEqual(crumbs[-1].route.path,'/home/emerson/Downloads/SMI-NodeLab-Logs')
        self.assertTrue(all(c.route.kind == 'resource' for c in crumbs))

    def test_source_trail_uses_same_file_ancestry_and_owned_scope_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'sample.py';path.write_text(SOURCE)
            doc=PythonDocument(path)
            parent=next(k for k,s in doc.scopes.items() if s.title=='icon_hint')
            child=next(k for k,s in doc.scopes.items() if s.title=='nested')
            trail=source_crumbs(doc,child,'focus')
            self.assertEqual([c.text for c in trail[-3:]], ['sample.py','icon_hint','nested'])
            self.assertEqual(trail[-1].route.scope,child)
            self.assertEqual(trail[-2].route.scope,parent)
            self.assertEqual(trail[-3].route.mode,'whole')
            self.assertEqual(trail[-4].route.kind,'resource')
            self.assertEqual(source_crumbs(doc,child,'whole')[-1].text,'sample.py')
            with self.assertRaises(ValueError):source_crumbs(doc,'fabricated','focus')
            # A document replacement can leave a stale focus key until the
            # view owner resets it; whole-file breadcrumbs remain canonical.
            self.assertEqual(source_crumbs(doc,'missing/previous:scope','whole')[-1].route.scope,'module')
            with self.assertRaises(ValueError):source_crumbs(doc,'missing/previous:scope','focus')

    def test_history_preserves_back_forward_and_discards_abandoned_branch(self):
        a,b,c,d=(Route('resource', f'/tmp/{x}') for x in 'abcd')
        h=NavigationHistory(a)
        self.assertIsNone(h.peek(-1))
        h.visit(b);h.visit(c)
        self.assertEqual(h.peek(-1),b)
        # A failed navigation does not advance the history pointer.
        self.assertEqual(h.current,c)
        h.move(-1)
        self.assertEqual(h.current,b)
        self.assertEqual(h.peek(1),c)
        h.visit(d)
        self.assertIsNone(h.peek(1))
        self.assertEqual(h.current,d)
        self.assertFalse(h.visit(d))

    def test_history_is_bounded_and_modes_are_not_duplicates(self):
        initial=Route('source','/tmp/file.py')
        h=NavigationHistory(initial,limit=3)
        scoped=Route('source','/tmp/file.py','module/func:one:1:0','focus')
        self.assertTrue(h.visit(scoped))
        self.assertNotEqual(h.current,initial)
        for n in range(5):h.visit(Route('resource',f'/tmp/{n}'))
        self.assertEqual(h.current.path,'/tmp/4')
        self.assertEqual(h.move(-1).path,'/tmp/3')
        self.assertEqual(h.move(-1).path,'/tmp/2')
        self.assertIsNone(h.peek(-1))

    def test_invalid_routes_refused(self):
        with self.assertRaises(ValueError):Route('fake','/tmp')
        with self.assertRaises(ValueError):Route('resource','')
        with self.assertRaises(ValueError):Route('region','/tmp/x.py', region='')
        with self.assertRaises(ValueError):NavigationHistory(Route('resource','/'), limit=1)


if __name__=='__main__':unittest.main()
