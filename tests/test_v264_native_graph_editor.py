"""Graph-owned editor boundary: same authority, shared renderer, safe draft lifecycle."""
from __future__ import annotations

import ast
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from studio_native.program_graph import (
    NODE_TEMPLATES, GraphConflict, ProgramGraph, ProgramGraphError,
    descriptor, diagnostics, template_ports, view_graph,
)
from studio_native.semantic_contract import describe_graph

ROOT = Path(__file__).resolve().parents[1]


class NativeGraphBoundaryTests(unittest.TestCase):
    def make(self):
        graph = ProgramGraph()
        graph.edit(graph.revision, 'add_function', name='build', id='function-build')
        return graph

    def add(self, graph, name, **more):
        options = template_ports(name)
        graph.edit(graph.revision, 'add_node', function='function-build',
                   operation=name, **options, **more)
        return graph.state['nodes'][-1]

    def test_templates_are_incomplete_drafts_not_compiler_opcodes(self):
        self.assertTrue({'python.literal', 'python.add', 'python.multiply',
                         'python.return', 'python.parameter', 'python.call'}
                        <= set(NODE_TEMPLATES))
        with self.assertRaises(ProgramGraphError):
            template_ports('python.arbitrary_execute')
        with self.assertRaises(ProgramGraphError):
            template_ports('python.call')
        ports = template_ports('python.add')
        self.assertEqual([p['name'] for p in ports['inputs']], ['left', 'right'])
        self.assertTrue(all(p['type'] == 'py:unknown' for p in ports['inputs']))

    def test_template_caller_cannot_mutate_canonical_definitions(self):
        ports = template_ports('python.add')
        ports['inputs'][0]['name'] = 'corrupted'
        self.assertEqual(template_ports('python.add')['inputs'][0]['name'], 'left')

    def test_graph_projection_is_shared_descriptor_and_never_a_draft_fallback(self):
        graph = self.make()
        self.add(graph, 'python.literal', id='value', x=100, y=80)
        self.add(graph, 'python.return', id='return', x=280, y=80)
        raw = view_graph(graph.state, 'function-build')
        self.assertEqual(descriptor(graph.state, 'function-build'),
                         describe_graph(raw, origin='program'))
        self.assertEqual(descriptor(graph.state, 'function-build').origin, 'program')
        self.assertEqual([n['id'] for n in raw['nodes']], ['value', 'return'])
        self.assertTrue(all('source_span' not in node for node in raw['nodes']))
        raw['nodes'][0]['x'] = -900
        self.assertEqual(graph.state['layout']['value']['x'], 100)

    def test_incomplete_visual_program_can_save_reopen_and_continue(self):
        graph = self.make()
        self.add(graph, 'python.add', id='addition', x=300, y=130)
        self.assertTrue(graph.dirty)
        self.assertTrue(any('unconnected' in d for d in diagnostics(graph.state)))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'incomplete.smi-graph'
            graph.save(path)
            self.assertFalse(graph.dirty)
            opened = ProgramGraph.open(path)
            self.assertFalse(opened.dirty)
            self.assertEqual(graph.state, opened.state)
            opened.edit(opened.revision, 'add_node',
                        function='function-build',operation='python.return',
                        **template_ports('python.return'))
            self.assertEqual(len(opened.state['nodes']), 2)
            self.assertEqual(len(ProgramGraph.open(path).state['nodes']), 1)
            self.assertTrue(opened.dirty)

    def test_connect_undo_redo_disconnection_and_single_revision(self):
        graph = self.make()
        value = self.add(graph, 'python.literal', id='value')
        result = self.add(graph, 'python.return', id='result')
        graph.edit(graph.revision, 'connect', id='wire', source=value['id'],
                   source_port=value['ports']['outputs'][0]['id'],
                   target=result['id'], target_port=result['ports']['inputs'][0]['id'])
        self.assertEqual(len(descriptor(graph.state, 'function-build').edges), 1)
        graph.undo(graph.revision)
        self.assertFalse(graph.state['edges'])
        graph.redo(graph.revision)
        self.assertEqual(graph.state['edges'][0]['id'], 'wire')

    def test_bulk_delete_is_atomic_and_restores_all_wires(self):
        graph = self.make()
        value = self.add(graph, 'python.literal', id='value')
        result = self.add(graph, 'python.return', id='result')
        graph.edit(graph.revision, 'connect', id='wire', source='value',
                   source_port=value['ports']['outputs'][0]['id'],
                   target='result', target_port=result['ports']['inputs'][0]['id'])
        before = graph.state
        graph.edit(graph.revision, 'remove_selection', nodes=['value'], edges=['wire'])
        self.assertEqual(graph.state['nodes'][0]['id'], 'result')
        self.assertFalse(graph.state['edges'])
        self.assertNotIn('value', graph.state['layout'])
        graph.undo(graph.revision)
        self.assertEqual(graph.state['nodes'], before['nodes'])
        self.assertEqual(graph.state['edges'], before['edges'])

    def test_bulk_delete_rejects_unknown_identity_without_partial_mutation(self):
        graph = self.make()
        self.add(graph, 'python.literal', id='value')
        before = graph.state
        with self.assertRaises(ProgramGraphError):
            graph.edit(graph.revision, 'remove_selection', nodes=['value', 'absent'], edges=[])
        self.assertEqual(graph.state, before)
        with self.assertRaises(ProgramGraphError):
            graph.edit(graph.revision, 'remove_selection', nodes=[], edges=[])
        self.assertEqual(graph.state, before)

    def test_opening_noncanonical_json_not_falsely_dirty(self):
        graph = self.make()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'noncanonical.smi-graph'
            path.write_text(json.dumps(graph.state, ensure_ascii=False, indent=2), encoding='utf-8')
            reopened = ProgramGraph.open(path)
            self.assertFalse(reopened.dirty)
            reopened.edit(reopened.revision, 'add_node', function='function-build',
                          operation='python.literal', **template_ports('python.literal'))
            self.assertTrue(reopened.dirty)
            reopened.undo(reopened.revision)
            # The monotonic revision itself is an actual stored change.
            self.assertTrue(reopened.dirty)

    def test_file_conflict_keeps_in_memory_graph_owned_draft(self):
        graph = self.make()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'graph.smi-graph'
            graph.save(path)
            another = ProgramGraph.open(path)
            self.add(graph, 'python.literal')
            another.edit(another.revision, 'add_node',function='function-build',
                         operation='python.return',**template_ports('python.return'))
            another.save(path)
            with self.assertRaises(GraphConflict):
                graph.save(path)
            self.assertTrue(graph.dirty)
            self.assertEqual(graph.state['nodes'][0]['operation'], 'python.literal')
            self.assertEqual(ProgramGraph.open(path).state['nodes'][0]['operation'], 'python.return')

    def test_visual_editor_has_one_renderer_and_no_source_writer(self):
        source = (ROOT/'studio_native'/'gui.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        program = next(c for c in tree.body if isinstance(c,ast.ClassDef) and c.name=='ProgramWorkspace')
        body = ast.get_source_segment(source,program)
        self.assertIn('GraphCanvas(window,program_view=True)',body)
        self.assertIn('self.document.edit(self.document.revision',body)
        self.assertIn('self.document.save(path)',body)
        self.assertNotIn('apply_proposal(',body)
        self.assertNotIn('PythonDocument(',body)
        self.assertNotIn('QGraphicsScene(',body)

    def test_gui_graph_history_and_qt_subprocess_have_native_acceptance_gates(self):
        source=(ROOT/'studio_native'/'gui.py').read_text()
        smoke=(ROOT/'studio_native'/'qt_smoke.py').read_text()
        shell=(ROOT/'test-qt-offscreen.sh').read_text()
        self.assertIn('self.program_workspace.connect(src,out',source)
        self.assertIn("self.edit('remove_selection'",source)
        self.assertIn('SMI_QT_PROGRAM_ONLY',smoke)
        self.assertIn('NATIVE_QT_PROGRAM_PASS',smoke)
        self.assertIn("QTest.mousePress(program.canvas.viewport()",smoke)
        self.assertIn('program-subprocess NATIVE_QT_PROGRAM_PASS',shell)


if __name__ == '__main__':
    unittest.main()
