"""Per-tab graph routes do not duplicate or mutate program semantics."""
import unittest
from pathlib import Path
from studio_native.navigation import Route, GraphViewSession, GraphViewSessions
from studio_native.python_graph import PythonDocument

DEMO=Path(__file__).resolve().parents[1]/'examples'/'python-scope-demo.py'


class SessionTests(unittest.TestCase):
    def test_independent_resource_and_source_history(self):
        sessions=GraphViewSessions()
        files=sessions.open('files',Route('resource','/tmp'))
        source=sessions.open('source',Route('source',str(DEMO)))
        files.visit(Route('resource','/tmp/demo'))
        key=next(k for k,v in PythonDocument(DEMO).scopes.items() if v.title=='outer')
        source.visit(Route('source',str(DEMO),key,'focus'))
        self.assertEqual(files.route.path,'/tmp/demo')
        self.assertEqual(source.route.scope,key)
        self.assertEqual(source.peek(-1).mode,'whole')
        self.assertEqual(files.peek(-1).kind,'resource')
        self.assertEqual(len(sessions),2)

    def test_single_tab_can_transition_resource_to_source_without_duplicate_semantics(self):
        session=GraphViewSession('workspace-1',Route('resource',str(DEMO.parent)))
        doc=PythonDocument(DEMO)
        route=Route('source',str(doc.path))
        session.visit(route)
        key=next(k for k,v in doc.scopes.items() if v.title=='outer')
        session.visit(Route('source',str(doc.path),key,'focus'))
        self.assertFalse(session.commit_history_move(-1,Route('resource','/wrong')))
        self.assertEqual(session.route.scope,key)
        self.assertTrue(session.commit_history_move(-1,route))
        self.assertEqual(session.route,route)
        self.assertTrue(session.commit_history_move(-1,Route('resource',str(DEMO.parent))))
        self.assertEqual(session.route.kind,'resource')
        self.assertEqual(doc.path,DEMO)
        self.assertTrue(doc.path.exists())

    def test_open_close_replace_respect_session_identity(self):
        sessions=GraphViewSessions()
        one=sessions.open('left',Route('resource','/tmp'))
        with self.assertRaises(ValueError):sessions.open('left',Route('resource','/'))
        self.assertIs(one,sessions.get('left'))
        sessions.replace('left',Route('resource','/new'))
        self.assertIsNone(sessions.get('other'))
        self.assertEqual(sessions.get('left').route.path,'/new')
        self.assertIsNone(sessions.get('left').peek(-1))
        self.assertTrue(sessions.close('left'))
        self.assertFalse(sessions.close('left'))
        self.assertEqual(len(sessions),0)
        with self.assertRaises(ValueError):sessions.replace('missing',Route('resource','/'))

    def test_invalid_session_identity_or_destination_refused(self):
        for identifier in ('',None,0,'  '):
            with self.subTest(identifier=identifier),self.assertRaises(ValueError):
                GraphViewSession(identifier,Route('resource','/'))
        session=GraphViewSession('s',Route('resource','/'))
        with self.assertRaises(TypeError):session.visit('/tmp')
        for invalid in ('wrong',2,0):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):session.peek(invalid)

    def test_same_scope_source_ids_in_two_sessions_are_not_copied_or_rewritten(self):
        doc=PythonDocument(DEMO)
        key=next(k for k,v in doc.scopes.items() if v.title=='outer')
        graph=doc.presentation_graph(key)
        source_ids=tuple(n['id'] for n in graph['nodes'])
        sessions=GraphViewSessions()
        a=sessions.open('a',Route('source',str(doc.path),key,'focus'))
        b=sessions.open('b',Route('source',str(doc.path),key,'focus'))
        b.visit(Route('source',str(doc.path)))
        self.assertEqual(a.route.scope,key)
        self.assertEqual(b.route.mode,'whole')
        self.assertEqual(source_ids,tuple(n['id'] for n in doc.presentation_graph(key)['nodes']))
        self.assertEqual(doc.raw,doc.path.read_bytes())


if __name__=='__main__': unittest.main()
