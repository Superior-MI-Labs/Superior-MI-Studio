"""v2.40: Python-first visual program assembly, signature migration and round trips."""
import ast
from pathlib import Path
import tempfile
import unittest

from studio_native.python_graph import PythonDocument, SourceError
from studio_native.python_authoring import (
    definitions, propose_create_function, propose_create_main_entry,
    propose_add_optional_parameter, propose_return_from_pass,
    eligible_pass_targets, eligible_entry_functions, eligible_signature_functions)
from studio_native.authoring_actions import available_actions, search_actions
from studio_native.python_edit import apply_proposal


class ProgramConstructionTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path=Path(tmp.name)/'program.py'
        self.path.write_bytes(b'')

    def doc(self):return PythonDocument(self.path)

    def apply(self,proposal):
        before=self.path.read_bytes()
        self.assertEqual(proposal.original,before)
        self.assertNotEqual(proposal.candidate,before)
        self.assertEqual(self.path.read_bytes(),before,'proposal must not auto-write')
        apply_proposal(proposal)
        return self.doc()

    def test_unloaded_python_source_has_no_authorized_creations(self):
        self.assertEqual(available_actions(None),())
        self.assertEqual(available_actions(None,pin=('any','port')),())

    def test_empty_source_advertises_function_creator(self):
        doc=self.doc();actions=available_actions(doc)
        self.assertEqual([a.id for a in actions],['python.create-function.v1'])
        self.assertEqual(search_actions(actions,'function definition'),actions)
        self.assertEqual(available_actions(doc,pin=('fake','pin')),())

    def test_full_program_visually_constructed_matches_handwritten_source(self):
        doc=self.apply(propose_create_function(self.doc(),'start',''))
        scope,anchor=next((k,a) for k,a in eligible_pass_targets(doc)
                          if doc.scopes[k].title=='start')
        doc=self.apply(propose_return_from_pass(doc,scope,'42',anchor))
        doc=self.apply(propose_create_main_entry(doc,'start'))
        source=self.path.read_text()
        handwritten='def start():\n    return 42\n\nif __name__ == "__main__":\n    print(start())\n'
        self.assertEqual(ast.dump(ast.parse(source)),ast.dump(ast.parse(handwritten)))
        self.assertIn('start', [s.title for s in doc.scopes.values()])
        module=doc.scope_graph('module')
        self.assertTrue(any(n.get('source_kind')=='branch' for n in module['nodes']))
        self.assertTrue(any(n.get('source_kind')=='call' for n in module['nodes']))
        self.assertFalse(eligible_entry_functions(doc))
        self.assertTrue(any(n.get('source_kind')=='return' for n in
                            doc.scope_graph(next(k for k,s in doc.scopes.items() if s.title=='start'))['nodes']))

    def test_creation_preserves_existing_comments_and_ast(self):
        original=b'# header\r\nvalue = 5\r\n'
        self.path.write_bytes(original)
        doc=self.doc();proposal=propose_create_function(doc,'compute','item, factor')
        self.assertTrue(proposal.candidate.startswith(original))
        self.assertNotIn(b'\n',proposal.candidate.replace(b'\r\n',b''))
        doc=self.apply(proposal)
        new=next(n for n in doc.tree.body if isinstance(n,ast.FunctionDef))
        self.assertEqual([a.arg for a in new.args.args],['item','factor'])

    def test_duplicate_and_shadowed_names_rejected(self):
        self.path.write_text('existing = 5\ndef other():\n    return future\n')
        for name in ('existing','future','print','1bad','for','__hidden'):
            with self.subTest(name=name),self.assertRaises(SourceError):
                propose_create_function(self.doc(),name)
        for names in ('a,a','a,,b',','.join(f'p{i}' for i in range(13)),'bad-name'):
            with self.subTest(names=names),self.assertRaises(SourceError):
                propose_create_function(self.doc(),'fresh',names)

    def test_new_main_guard_checks_target_uniqueness_and_existing_main(self):
        self.path.write_text('def run():\n    return 5\n')
        self.assertEqual(eligible_entry_functions(self.doc()),('run',))
        self.path.write_text('def run(x):\n    return x\n')
        self.assertEqual(eligible_entry_functions(self.doc()),())
        with self.assertRaises(SourceError):propose_create_main_entry(self.doc(),'run')
        self.path.write_text('def run():\n    return 5\nif __name__ == "__main__":\n    run()\n')
        self.assertEqual(eligible_entry_functions(self.doc()),())

    def test_optional_parameter_and_call_sites_atomic_migration(self):
        self.path.write_text('def transform(value):\n    return value\n\n'
                             'def dispatch(x):\n    return transform(x)\n\n'
                             'result = transform(2)\n')
        doc=self.doc();proposal=propose_add_optional_parameter(doc,'transform','enabled','True')
        self.assertIn(b'def transform(value, *, enabled=True)',proposal.candidate)
        self.assertEqual(proposal.candidate.count(b'enabled=True'),3)
        self.assertNotIn(b'enabled=',self.path.read_bytes())
        doc=self.apply(proposal)
        function=next(n for n in doc.tree.body if isinstance(n,ast.FunctionDef) and n.name=='transform')
        self.assertEqual(function.args.kwonlyargs[0].arg,'enabled')
        self.assertEqual(len([n for n in ast.walk(doc.tree) if isinstance(n,ast.Call) and
                         isinstance(n.func,ast.Name) and n.func.id=='transform']),2)

    def test_optional_parameter_makes_existing_external_calls_backward_compatible(self):
        self.path.write_text('def run(value):\n    return value\n')
        proposal=propose_add_optional_parameter(self.doc(),'run','mode','0',update_local_calls=False)
        self.assertIn(b'def run(value, *, mode=0):',proposal.candidate)
        # No local caller signature is changed; new input has a default.
        self.assertIn(b'    return value',proposal.candidate)

    def test_optional_existing_kwonly_parameters(self):
        self.path.write_text('def run(x, *, flag=True):\n    return x\n\ndef caller():\n    return run(4, flag=False)\n')
        proposal=propose_add_optional_parameter(self.doc(),'run','mode','"fast"')
        self.assertIn(b'flag=True, mode=',proposal.candidate)
        self.assertIn(b'flag=False, mode=',proposal.candidate)

    def test_signatures_reject_rebinding_and_unqualified_calls(self):
        samples=(
            'def run(x):\n    return x\ndef outer(run):\n    return run(4)\n',
            'def run(x):\n    return x\ndef caller():\n    return run(*(1,))\n',
            'def run(x):\n    return x\ndef caller():\n    return run(**{"x": 3})\n',
            'def run(x):\n    return x\ndef caller():\n    run = print\n    return run(5)\n',
        )
        for sample in samples:
            with self.subTest(sample=sample):
                self.path.write_text(sample)
                with self.assertRaises(SourceError):
                    propose_add_optional_parameter(self.doc(),'run','extra','0')

    def test_signature_rejects_binding_capture_and_unqualified_header(self):
        self.path.write_text('def run():\n    return extra\n')
        with self.assertRaises(SourceError):
            propose_add_optional_parameter(self.doc(),'run','extra','0')
        self.path.write_text('def run(\n    value\n):\n    return value\n')
        self.assertEqual(eligible_signature_functions(self.doc()),())
        self.path.write_text('@decorator\ndef run():\n    pass\n')
        self.assertEqual(eligible_signature_functions(self.doc()),())

    def test_signature_refuses_stale_external_file(self):
        self.path.write_text('def run(x):\n    return x\n')
        proposal=propose_add_optional_parameter(self.doc(),'run','extra','1')
        self.path.write_text('def run(x):\n    return x\n# external edit\n')
        with self.assertRaisesRegex(ValueError,'externally'):
            apply_proposal(proposal)

    def test_program_source_never_executes_on_parse_or_proposal(self):
        self.path.write_text('raise RuntimeError("never execute")\n')
        proposal=propose_create_function(self.doc(),'new_function','x')
        self.assertIn(b'raise RuntimeError',proposal.candidate)
        self.assertNotIn(b'new_function',self.path.read_bytes())

    def test_catalog_contract_single_authority(self):
        ids=[d.id for d in definitions()]
        self.assertEqual(len(ids),len(set(ids)))
        for name in ('python.create-function.v1','python.create-main-entry.v1',
                     'python.add-optional-keyword-parameter.v1'):
            self.assertIn(name,ids)
        self.path.write_text('def start():\n    pass\n')
        names=[a.id for a in available_actions(self.doc())]
        self.assertIn('python.create-function.v1',names)
        self.assertIn('python.create-main-entry.v1',names)
        self.assertIn('python.add-optional-keyword-parameter.v1',names)

    def test_unicode_identifiers_and_crlf_round_trip(self):
        self.path.write_bytes('def éclair(x):\r\n    return x\r\n'.encode())
        proposal=propose_add_optional_parameter(self.doc(),'éclair','étiquette','"ok"')
        self.assertIn('étiquette'.encode(),proposal.candidate)
        self.assertNotIn(b'\n',proposal.candidate.replace(b'\r\n',b''))
        self.apply(proposal)
        self.assertIsNotNone(self.doc())


if __name__=='__main__':unittest.main()

class AdditionalAdversarialContracts(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.path=Path(temporary.name)/'program.py'

    def test_nested_local_function_shadow_blocks_call_site_rewrite(self):
        self.path.write_text('def target(x):\n    return x\n'
                             'def caller():\n    def target(x):\n        return x+1\n'
                             '    return target(4)\n')
        with self.assertRaisesRegex(SourceError,'shadows'):
            propose_add_optional_parameter(PythonDocument(self.path),'target','extra','0')

    def test_name_collision_with_existing_argument_and_local(self):
        for src in ('def run(extra):\n    return extra\n',
                    'def run():\n    extra = 2\n    return extra\n',
                    'def run():\n    return extra\n'):
            with self.subTest(src=src):
                self.path.write_text(src)
                with self.assertRaises(SourceError):
                    propose_add_optional_parameter(PythonDocument(self.path),'run','extra','2')

    def test_main_guard_uses_source_backed_branch_ports(self):
        self.path.write_text('def start():\n    return 5\n'
                             'if __name__ == "__main__":\n    print(start())\n')
        graph=PythonDocument(self.path).scope_graph('module')
        branch=next(n for n in graph['nodes'] if n['source_kind']=='branch')
        output_ids={p['id'] for p in branch['draft_ports']['outputs']}
        self.assertTrue(any(p.endswith(':true') for p in output_ids))
        self.assertTrue(any(p.endswith(':false') for p in output_ids))
        self.assertTrue(any(e['source']==branch['id'] and e['relation']=='control'
                            for e in graph['edges']))

    def test_nonqualified_if_still_opaque_and_unwired(self):
        self.path.write_text('if flag:\n    do_something()\nelse:\n    do_other()\n')
        graph=PythonDocument(self.path).scope_graph('module')
        self.assertFalse(any(n['source_kind']=='branch' for n in graph['nodes']))
        self.assertTrue(any(n['source_kind']=='opaque' for n in graph['nodes']))
