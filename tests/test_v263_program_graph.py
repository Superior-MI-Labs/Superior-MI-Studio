"""ProgramGraph v1: incomplete drafts, transactions, identity, persistence and safety."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from studio_native.program_graph import (
    FORMAT, GraphConflict, ProgramGraph, ProgramGraphError, descriptor,
    diagnostics, encode, new_program, validate,
)
from studio_native.semantic_contract import describe_graph, ContractError


class ProgramGraphTests(unittest.TestCase):
    def make(self):
        g = ProgramGraph()
        self.assertTrue(g.edit(g.revision, 'add_function', id='fn-a', name='compute'))
        g.edit(g.revision, 'add_parameter', function='fn-a', id='arg-a', name='value')
        g.edit(g.revision, 'add_node', id='node-add', function='fn-a',
               operation='python.add', inputs=[{'id': 'left', 'name': 'left', 'type': 'py:int'},
                                               {'id': 'right', 'name': 'right', 'type': 'py:int'}],
               outputs=[{'id': 'result', 'name': 'result', 'type': 'py:int'}], x=130, y=55)
        g.edit(g.revision, 'add_node', id='node-return', function='fn-a',
               operation='python.return', inputs=[{'id': 'value', 'name': 'value', 'type': 'py:int'}],
               outputs=[], x=300, y=55)
        return g

    def test_incomplete_is_valid_document_not_executable(self):
        g = self.make()
        validate(g.state)
        messages = diagnostics(g.state)
        self.assertTrue(any('unconnected' in m for m in messages))
        self.assertTrue(any('not qualified' in m for m in messages))
        self.assertEqual(descriptor(g.state, 'fn-a').origin, 'program')
        self.assertEqual(len(descriptor(g.state, 'fn-a').nodes), 2)

    def test_connect_disconnect_undo_redo_preserves_ids(self):
        g = self.make()
        base = g.revision
        self.assertTrue(g.edit(base, 'connect', id='edge-1', source='node-add', source_port='result',
                               target='node-return', target_port='value'))
        self.assertEqual(descriptor(g.state, 'fn-a').edges[0].id, 'edge-1')
        self.assertTrue(g.undo(g.revision))
        self.assertEqual(g.state['edges'], [])
        self.assertTrue(g.redo(g.revision))
        self.assertEqual(g.state['edges'][0]['id'], 'edge-1')
        self.assertTrue(g.edit(g.revision, 'disconnect', edge='edge-1'))
        self.assertEqual(g.state['edges'], [])

    def test_remove_node_cascades_to_edges_and_layout(self):
        g = self.make()
        g.edit(g.revision, 'connect', source='node-add', source_port='result', target='node-return', target_port='value')
        g.edit(g.revision, 'remove_node', node='node-add')
        self.assertEqual(g.state['edges'], [])
        self.assertNotIn('node-add', g.state['layout'])
        self.assertTrue(g.undo(g.revision))
        self.assertIn('node-add', g.state['layout'])
        self.assertEqual(len(g.state['edges']), 1)

    def test_move_changes_layout_not_semantic_operation(self):
        g = self.make()
        before = {k: v for k, v in g.state.items() if k not in ('revision', 'layout')}
        g.edit(g.revision, 'move_node', node='node-add', x=501, y=-67)
        self.assertEqual(before, {k: v for k, v in g.state.items() if k not in ('revision', 'layout')})
        self.assertEqual(g.state['layout']['node-add']['x'], 501)

    def test_revisions_monotonic_and_stale_edits_refused(self):
        g = self.make()
        old = g.revision
        g.edit(old, 'annotate', function='fn-a', text='unfinished operation')
        with self.assertRaises(GraphConflict):
            g.edit(old, 'annotate', function='fn-a', text='stale')
        g.undo(g.revision)
        self.assertGreater(g.revision, old + 1)
        with self.assertRaises(GraphConflict):
            g.redo(old)

    def test_noop_does_not_change_revision_or_kill_redo(self):
        g = self.make()
        rev = g.revision
        self.assertFalse(g.edit(rev, 'move_node', node='node-add', x=130, y=55))
        self.assertEqual(rev, g.revision)
        self.assertTrue(g.undo(rev))
        self.assertTrue(g.redo(g.revision))

    def test_invalid_mutations_are_transactional(self):
        g = self.make()
        original = g.state
        with self.assertRaises(ProgramGraphError):
            g.edit(g.revision, 'connect', id='edge-1', source='node-add', source_port='left',
                   target='node-return', target_port='value')
        self.assertEqual(g.state, original)
        with self.assertRaises(ProgramGraphError):
            g.edit(g.revision, 'add_node', id='node-add', function='fn-a', operation='python.foo')
        self.assertEqual(g.state, original)

    def test_same_input_cannot_have_two_edges(self):
        g = self.make()
        g.edit(g.revision, 'connect', source='node-add', source_port='result',
               target='node-return', target_port='value')
        before = g.state
        with self.assertRaises(ProgramGraphError):
            g.edit(g.revision, 'connect', source='node-add', source_port='result',
                   target='node-return', target_port='value')
        self.assertEqual(before, g.state)

    def test_reconnect_is_atomic_and_retains_edge_id(self):
        g = self.make()
        g.edit(g.revision, 'connect', id='edge-1', source='node-add', source_port='result',
               target='node-return', target_port='value')
        g.edit(g.revision, 'add_node', id='other', function='fn-a', operation='python.multiply',
               inputs=[{'id': 'input', 'name': 'a', 'type': 'py:int'}])
        g.edit(g.revision, 'reconnect', edge='edge-1', target='other', target_port='input')
        self.assertEqual(g.state['edges'][0]['id'], 'edge-1')
        self.assertEqual(g.state['edges'][0]['target'], 'other')
        before = g.state
        with self.assertRaises(ProgramGraphError):
            g.edit(g.revision, 'reconnect', edge='edge-1', target='missing')
        self.assertEqual(g.state, before)

    def test_remove_function_cascades_and_is_reversible(self):
        g = self.make()
        g.edit(g.revision, 'remove_function', function='fn-a')
        self.assertEqual(g.state['nodes'], [])
        self.assertEqual(g.state['layout'], {})
        self.assertEqual(g.state['functions'], [])
        g.undo(g.revision)
        self.assertEqual(len(g.state['nodes']), 2)
        self.assertEqual(g.state['functions'][0]['id'], 'fn-a')

    def test_invalid_function_boundary_cannot_be_connected(self):
        g = self.make()
        g.edit(g.revision, 'add_function', id='fn-b', name='other')
        g.edit(g.revision, 'add_node', id='node-b', function='fn-b', operation='python.return',
               inputs=[{'id':'in', 'name':'value', 'type':'py:int'}])
        with self.assertRaisesRegex(ProgramGraphError, 'Cross-function'):
            g.edit(g.revision, 'connect', source='node-add', source_port='result', target='node-b', target_port='in')

    def test_schema_rejects_unknown_fields_versions_and_broken_identity(self):
        state = self.make().state
        for change in ({'extra': 12}, {'version': 2}, {'format': 'smi.dynamic-node-lab'}):
            with self.subTest(change=change):
                candidate = copy.deepcopy(state); candidate.update(change)
                with self.assertRaises(ProgramGraphError):
                    validate(candidate)
        state['nodes'][0]['id'] = 'node-return'
        with self.assertRaises(ProgramGraphError):
            validate(state)

    def test_program_origin_rejects_fictitious_source_spans(self):
        raw = {'scope': 'p/f', 'nodes': [{'id': 'n', 'kind': 'python.add', 'source_span':
                {'line': 1, 'col': 0, 'end_line': 1, 'end_col': 2},
                'draft_ports': {'inputs': [], 'outputs': []}}], 'edges': []}
        with self.assertRaises(ContractError):
            describe_graph(raw, origin='program')

    def test_incomplete_gold_example_roundtrips_without_python(self):
        example = Path(__file__).resolve().parent.parent / 'examples' / 'incomplete-program.smi-graph'
        graph = ProgramGraph.open(example)
        self.assertEqual(graph.state['id'], 'example-incomplete-program')
        self.assertEqual(len(graph.state['nodes']), 3)
        self.assertEqual(len(graph.state['edges']), 1)
        self.assertEqual(descriptor(graph.state, 'fn-demo').origin, 'program')
        self.assertTrue(diagnostics(graph.state))
        self.assertEqual(example.read_bytes(), encode(graph.state))

    def test_type_mismatch_is_nonfatal_semantic_diagnostic(self):
        graph = self.make()
        graph.edit(graph.revision, 'add_node', id='text-consumer', function='fn-a',
                   operation='python.unknown', inputs=[{'id': 's', 'name': 'text', 'type': 'py:str'}])
        graph.edit(graph.revision, 'connect', source='node-add', source_port='result',
                   target='text-consumer', target_port='s')
        self.assertTrue(any('unqualified value type conversion' in issue
                            for issue in diagnostics(graph.state)))
        self.assertEqual(len(descriptor(graph.state, 'fn-a').edges), 1)

    def test_prototype_draft_format_unchanged_and_not_program(self):
        from studio_native import model
        legacy = model.new_state()
        self.assertEqual(model.validate(legacy), [])
        with self.assertRaises(ProgramGraphError):
            ProgramGraph(legacy)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'legacy.json'
            model.write_state(path, legacy)
            self.assertEqual(model.read_state(path)['format'], model.FORMAT)
            with self.assertRaises(ProgramGraphError):
                ProgramGraph.open(path)

    def test_unknown_operation_and_property_survive_serialization(self):
        g = self.make()
        g.edit(g.revision, 'add_node', id='unknown-1', function='fn-a', operation='python.future_op',
               operation_version=92, properties={'arbitrary': {'nested': ['☀', 19, None]}})
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'demo.smi-graph'
            g.save(p)
            restored = ProgramGraph.open(p)
            self.assertEqual(restored.state, g.state)
            self.assertEqual(restored.state['nodes'][-1]['operation_version'], 92)
            self.assertIn('unknown-1', {n.id for n in descriptor(restored.state, 'fn-a').nodes})
            self.assertEqual(p.read_bytes(), encode(restored.state))

    def test_stale_disk_revision_fails_without_losing_draft(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'demo.smi-graph'
            g = self.make(); g.save(p)
            other = ProgramGraph.open(p)
            g.edit(g.revision, 'annotate', function='fn-a', text='writer A')
            g.save(p)
            other.edit(other.revision, 'annotate', function='fn-a', text='writer B')
            with self.assertRaises(GraphConflict):
                other.save(p)
            self.assertEqual(other.state['annotations'][0]['text'], 'writer B')
            self.assertEqual(ProgramGraph.open(p).state['annotations'][0]['text'], 'writer A')

    def test_new_graph_will_not_overwrite_existing_file_or_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'demo.smi-graph'; p.write_text('leave alone')
            with self.assertRaises(GraphConflict): ProgramGraph().save(p)
            self.assertEqual(p.read_text(), 'leave alone')
            link = Path(d) / 'link.smi-graph'; link.symlink_to(p)
            with self.assertRaises(GraphConflict): ProgramGraph().save(link)

    def test_no_silent_property_reencoding_or_duplicate_json_keys(self):
        g = self.make()
        with self.assertRaises(ProgramGraphError):
            g.edit(g.revision, 'set_property', node='node-add', key='odd', value={1: 'value'})
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'duplicate.smi-graph'
            raw = encode(self.make().state).decode('utf-8')
            raw = raw.replace('"version":1', '"version":1,"version":1')
            p.write_text(raw)
            with self.assertRaisesRegex(ProgramGraphError, 'Duplicate JSON'):
                ProgramGraph.open(p)

    def test_broken_and_truncated_json_does_not_modify_source(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'broken.smi-graph'; p.write_bytes(b'{"format": "smi.program-graph",')
            with self.assertRaises(ProgramGraphError): ProgramGraph.open(p)
            self.assertEqual(p.read_bytes(), b'{"format": "smi.program-graph",')

    def test_retrieved_state_does_not_mutate_authority(self):
        g = self.make()
        snapshot = g.state
        snapshot['nodes'][0]['operation'] = 'python.exec'
        self.assertEqual(g.state['nodes'][0]['operation'], 'python.add')

    def test_literal_or_real_calls_not_executed_during_read(self):
        with tempfile.TemporaryDirectory() as d:
            sentinel = Path(d) / 'should-not-exist'
            g = self.make()
            g.edit(g.revision, 'set_property', node='node-add', key='expression',
                   value=f'__import__("pathlib").Path({str(sentinel)!r}).touch()')
            p = Path(d) / 'draft.smi-graph'; g.save(p)
            self.assertEqual(ProgramGraph.open(p).state, g.state)
            self.assertFalse(sentinel.exists())


if __name__ == '__main__':
    unittest.main()

# Shared processes use the same advisory writer lock, not only a test mock.
def _competing_save(path, ready, go, results, label):
    try:
        doc = ProgramGraph.open(path)
        doc.edit(doc.revision, 'annotate', function='fn-a', text=label)
        ready.put(label)
        if not go.wait(4):
            raise RuntimeError('test gate timeout')
        doc.save(path)
        results.put((label, 'saved'))
    except GraphConflict:
        results.put((label, 'conflict'))
    except BaseException as exc:
        results.put((label, type(exc).__name__ + ': ' + str(exc)))


class ProgramGraphConcurrencyTests(unittest.TestCase):
    make = ProgramGraphTests.make
    """Reuses fixture; validates multiprocessing and backup invariants."""
    def test_competing_processes_cannot_both_publish_same_preimage(self):
        import multiprocessing
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'simultaneous.smi-graph'
            self.make().save(path)
            ctx = multiprocessing.get_context('spawn')
            ready, results, go = ctx.Queue(), ctx.Queue(), ctx.Event()
            workers = [ctx.Process(target=_competing_save, args=(path, ready, go, results, n))
                       for n in ('a', 'b')]
            for p in workers: p.start()
            try:
                self.assertEqual({ready.get(timeout=6), ready.get(timeout=6)}, {'a', 'b'})
                go.set()
                outcomes = [results.get(timeout=6), results.get(timeout=6)]
                self.assertEqual({result for name, result in outcomes}, {'saved', 'conflict'})
                self.assertIn(ProgramGraph.open(path).state['annotations'][0]['text'], ('a', 'b'))
            finally:
                go.set()
                for p in workers:
                    p.join(timeout=4)
                    if p.is_alive():p.kill();p.join()

    def test_last_good_backup_matches_previous_revision(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'saved.smi-graph'
            graph = self.make(); graph.save(path)
            original = path.read_bytes()
            graph.edit(graph.revision, 'annotate', function='fn-a', text='changed')
            graph.save(path)
            backup = path.with_name('.' + path.name + '.smi-previous')
            self.assertEqual(backup.read_bytes(), original)
            self.assertNotEqual(path.read_bytes(), original)
            self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
