"""Graph-owned, incomplete *program documents*; NOT Python source or a compiler.

This is deliberately independent of ``model.py`` presentation drafts. A graph is
structurally sound when its identities and references are safe to persist; a
structurally sound graph is NOT necessarily semantically executable. The only
mutable owner is ProgramGraph. Qt receives derived GraphDescriptors.
"""
from __future__ import annotations

import copy
import hashlib
import json
import keyword
import math
import os
from pathlib import Path
import stat
import tempfile
import uuid

FORMAT = 'smi.program-graph'
VERSION = 1
MAX_BYTES = 4_000_000
MAX_NODES = 2000
MAX_EDGES = 8000
HISTORY_LIMIT = 48


class ProgramGraphError(ValueError):
    pass


class GraphConflict(ProgramGraphError):
    pass


def _id(prefix: str) -> str:
    return f'{prefix}-{uuid.uuid4().hex}'


def _identifier(value):
    return isinstance(value, str) and 0 < len(value) <= 128 and '\x00' not in value


def _kind(value):
    return _identifier(value) and all(ch.isalnum() or ch in '._:-' for ch in value)


def new_program() -> dict:
    return {'format': FORMAT, 'version': VERSION, 'id': _id('program'),
            'revision': 0, 'functions': [], 'nodes': [], 'edges': [],
            'layout': {}, 'annotations': []}


def encode(state: dict) -> bytes:
    try:
        data = (json.dumps(state, ensure_ascii=False, sort_keys=True,
                           separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise ProgramGraphError('Program graph has invalid JSON content') from exc
    if len(data) > MAX_BYTES:
        raise ProgramGraphError('Program graph exceeds 4 MB limit')
    # JSON encoding must not normalize identity-bearing dict keys or tuples.
    # Otherwise a save/reopen cycle could silently change graph semantics.
    try:
        identical = json.loads(data) == state
    except (ValueError, RecursionError) as exc:
        raise ProgramGraphError('Graph JSON cannot be decoded safely') from exc
    if not identical:
        raise ProgramGraphError('Graph contains JSON values that cannot round-trip exactly')
    return data


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ProgramGraphError('Duplicate JSON object key')
        result[key] = value
    return result


def validate(state: dict) -> None:
    """Structural correctness only. Missing required values remain legal drafts."""
    if not isinstance(state, dict) or set(state) != {
        'format', 'version', 'id', 'revision', 'functions', 'nodes',
        'edges', 'layout', 'annotations'}:
        raise ProgramGraphError('Unknown or malformed program graph format')
    if state['format'] != FORMAT or type(state['version']) is not int or state['version'] != VERSION:
        raise ProgramGraphError('Unsupported program graph version')
    if not _identifier(state['id']) or type(state['revision']) is not int or state['revision'] < 0:
        raise ProgramGraphError('Invalid program identity or revision')
    funcs, nodes, edges = state['functions'], state['nodes'], state['edges']
    if not (isinstance(funcs, list) and isinstance(nodes, list) and isinstance(edges, list) and
            len(funcs) <= 256 and len(nodes) <= MAX_NODES and len(edges) <= MAX_EDGES):
        raise ProgramGraphError('Program graph exceeds structural bounds')
    function_ids = set()
    function_names = set()
    for f in funcs:
        if (not isinstance(f, dict) or set(f) != {'id', 'name', 'parameters', 'return_type'} or
                not _identifier(f['id']) or not isinstance(f['name'], str) or
                not f['name'].isidentifier() or keyword.iskeyword(f['name']) or not _kind(f['return_type']) or
                not isinstance(f['parameters'], list) or len(f['parameters']) > 128):
            raise ProgramGraphError('Malformed function definition')
        if f['id'] in function_ids or f['name'] in function_names:
            raise ProgramGraphError('Duplicate function identity/name')
        function_ids.add(f['id']); function_names.add(f['name'])
        parameters = set()
        for p in f['parameters']:
            if (not isinstance(p, dict) or set(p) != {'id', 'name', 'type'} or
                    not _identifier(p['id']) or not isinstance(p['name'], str) or
                    not p['name'].isidentifier() or keyword.iskeyword(p['name']) or not _kind(p['type']) or
                    p['id'] in parameters):
                raise ProgramGraphError('Invalid or duplicate function parameter')
            parameters.add(p['id'])
        if len({p['name'] for p in f['parameters']}) != len(f['parameters']):
            raise ProgramGraphError('Duplicate parameter name')
    node_ids = set()
    port_lookup = {}
    for n in nodes:
        if (not isinstance(n, dict) or set(n) != {'id', 'function', 'operation', 'operation_version', 'ports', 'properties'} or
                not _identifier(n['id']) or n['id'] in node_ids or
                not _identifier(n['function']) or n['function'] not in function_ids or
                not _kind(n['operation']) or type(n['operation_version']) is not int or
                not 1 <= n['operation_version'] <= 65535 or not isinstance(n['ports'], dict) or
                set(n['ports']) != {'inputs', 'outputs'} or not isinstance(n['properties'], dict)):
            raise ProgramGraphError('Invalid node or function ownership')
        node_ids.add(n['id'])
        local = set()
        for direction in ('inputs', 'outputs'):
            ports = n['ports'][direction]
            if not isinstance(ports, list) or len(ports) > 64:
                raise ProgramGraphError('Invalid port collection')
            for p in ports:
                if (not isinstance(p, dict) or set(p) != {'id', 'name', 'type', 'required'} or
                        not _identifier(p['id']) or not isinstance(p['name'], str) or len(p['name']) > 128 or
                        not _kind(p['type']) or type(p['required']) is not bool or p['id'] in local):
                    raise ProgramGraphError('Invalid/duplicate node port')
                local.add(p['id'])
                port_lookup[n['id'], p['id']] = (direction, p['type'], n['function'])
    edge_ids = set()
    occupied = set()
    for e in edges:
        if (not isinstance(e, dict) or set(e) != {'id', 'source', 'source_port', 'target', 'target_port', 'relation'} or
                not _identifier(e['id']) or e['id'] in edge_ids or
                not all(_identifier(e[k]) for k in ('source', 'source_port', 'target', 'target_port')) or
                e['relation'] not in ('data', 'control')):
            raise ProgramGraphError('Invalid/duplicate edge')
        edge_ids.add(e['id'])
        start = port_lookup.get((e['source'], e['source_port']))
        finish = port_lookup.get((e['target'], e['target_port']))
        if start is None or finish is None or start[0] != 'outputs' or finish[0] != 'inputs':
            raise ProgramGraphError('Edge references missing or reversed port')
        if start[2] != finish[2]:
            raise ProgramGraphError('Cross-function execution/data edge is not allowed')
        if e['relation'] == 'control' and (start[1] != 'execution' or finish[1] != 'execution'):
            raise ProgramGraphError('Control edge requires execution pins')
        if e['relation'] == 'data' and (start[1] == 'execution' or finish[1] == 'execution'):
            raise ProgramGraphError('Data edge cannot carry execution pins')
        target = e['target'], e['target_port']
        if target in occupied:
            raise ProgramGraphError('Input pin already connected')
        occupied.add(target)
    layout = state['layout']
    if not isinstance(layout, dict) or set(layout) != node_ids:
        raise ProgramGraphError('Layout must contain exactly one position per node')
    for item in layout.values():
        if (not isinstance(item, dict) or set(item) != {'x', 'y'} or
                any(type(item[k]) not in (int, float) or not math.isfinite(item[k]) or
                    abs(item[k]) > 100_000 for k in ('x', 'y'))):
            raise ProgramGraphError('Invalid node location')
    annotations = state['annotations']
    if not isinstance(annotations, list) or len(annotations) > 512:
        raise ProgramGraphError('Too many annotations')
    ids = set()
    for a in annotations:
        if (not isinstance(a, dict) or set(a) != {'id', 'text', 'function'} or
                not _identifier(a['id']) or a['id'] in ids or
                not _identifier(a['function']) or a['function'] not in function_ids or
                not isinstance(a['text'], str) or len(a['text']) > 1000):
            raise ProgramGraphError('Invalid annotation')
        ids.add(a['id'])
    encode(state)


def diagnostics(state: dict) -> tuple[str, ...]:
    """Nonfatal, non-executable observations. No schema means no execution claim."""
    validate(state)
    connected = {(e['target'], e['target_port']) for e in state['edges']}
    lookup = {(n['id'], p['id']): p['type'] for n in state['nodes']
              for p in n['ports']['inputs'] + n['ports']['outputs']}
    result = []
    for n in state['nodes']:
        # Keep unsupported operations unchanged and savable, never infer semantics.
        result.append(f'{n["id"]}: operation {n["operation"]}@{n["operation_version"]} is not qualified for Python lowering')
        for p in n['ports']['inputs']:
            if p['required'] and (n['id'], p['id']) not in connected:
                result.append(f'{n["id"]}/{p["id"]}: required input is unconnected')
    for e in state['edges']:
        start = lookup[e['source'], e['source_port']]
        end = lookup[e['target'], e['target_port']]
        if start != end and start != 'py:unknown' and end != 'py:unknown':
            result.append(f'{e["id"]}: unqualified value type conversion {start} -> {end}')
    return tuple(result)


# Only graph-document templates, not a Python code-generation catalog. These
# supply incomplete port structures. They make NO claim about execution or
# lowering; that qualification belongs to a future Python adapter.
NODE_TEMPLATES = {
    # Qualified minimal execution graph: Entry -> Branch -> two Return Flow
    # operations. The Python adapter validates all control edges and returns.
    'python.entry': ((), (('then', 'execution'),)),
    'python.branch': ((('exec', 'execution'), ('condition', 'py:bool')),
                      (('true', 'execution'), ('false', 'execution'))),
    'python.return_flow': ((('exec', 'execution'), ('value', 'py:unknown')), ()),
    # Effectful sequential guard. It fails with ValueError when false, and
    # advances only through its explicit `then` execution connection.
    'python.require': ((('exec', 'execution'), ('condition', 'py:bool')),
                       (('then', 'execution'),)),
    # Structured, counted loop. The body must terminate at Repeat End; the
    # After continuation is a separate path, not a free-form back-edge.
    'python.repeat_int': ((('exec', 'execution'), ('count', 'py:int')),
                          (('body', 'execution'), ('after', 'execution'))),
    'python.repeat_end': ((('exec', 'execution'),), ()),
    # A typed single-assignment capture, NOT a mutable variable or loop state.
    # Data output becomes available only after this node executes.
    'python.bind_int': ((('exec', 'execution'), ('value', 'py:int')),
                        (('then', 'execution'), ('value', 'py:int'))),
    'python.bind_bool': ((('exec', 'execution'), ('value', 'py:bool')),
                         (('then', 'execution'), ('value', 'py:bool'))),
    # Explicit execution-local mutable slots. Read is an execution-ordered
    # value SNAPSHOT; no implicit, time-dependent pure data producer exists.
    'python.local_int': ((('exec', 'execution'), ('value', 'py:int')),
                         (('then', 'execution'),)),
    'python.local_bool': ((('exec', 'execution'), ('value', 'py:bool')),
                          (('then', 'execution'),)),
    'python.assign_int': ((('exec', 'execution'), ('value', 'py:int')),
                          (('then', 'execution'),)),
    'python.assign_bool': ((('exec', 'execution'), ('value', 'py:bool')),
                           (('then', 'execution'),)),
    'python.read_int': ((('exec', 'execution'),),
                        (('then', 'execution'), ('value', 'py:int'))),
    'python.read_bool': ((('exec', 'execution'),),
                         (('then', 'execution'), ('value', 'py:bool'))),
    'python.literal': ((), (('value', 'py:unknown'),)),
    'python.add': ((('left', 'py:unknown'), ('right', 'py:unknown')),
                   (('result', 'py:unknown'),)),
    'python.subtract': ((('left', 'py:unknown'), ('right', 'py:unknown')),
                        (('result', 'py:unknown'),)),
    # Integer comparisons share one interface. The Python adapter alone
    # determines which typed AST expression is executable; ProgramGraph owns
    # only the canonical ports and stable operation identities.
    **{operation: ((('left', 'py:int'), ('right', 'py:int')),
                   (('result', 'py:bool'),)) for operation in (
        'python.less_than', 'python.equal_int', 'python.greater_than',
        'python.less_or_equal', 'python.greater_or_equal', 'python.not_equal_int')},
    'python.not': ((('value', 'py:bool'),), (('result', 'py:bool'),)),
    # Data selection is eager: both producer subgraphs evaluate before selection.
    # This is NOT a Blueprint control-flow Branch or an effectful conditional.
    'python.select_int': ((('condition', 'py:bool'), ('true_value', 'py:int'), ('false_value', 'py:int')),
                          (('result', 'py:int'),)),
    'python.select_bool': ((('condition', 'py:bool'), ('true_value', 'py:bool'), ('false_value', 'py:bool')),
                           (('result', 'py:bool'),)),
    'python.multiply': ((('left', 'py:unknown'), ('right', 'py:unknown')),
                        (('result', 'py:unknown'),)),
    # Same existing integer-compatible wiring contract as add/subtract/multiply.
    # Actual Python numeric eligibility is established by python_lowering.
    'python.floor_divide': ((('left', 'py:unknown'), ('right', 'py:unknown')),
                            (('result', 'py:unknown'),)),
    'python.modulo': ((('left', 'py:unknown'), ('right', 'py:unknown')),
                      (('result', 'py:unknown'),)),
    'python.return': ((('value', 'py:unknown'),), ()),
    'python.parameter': ((), (('value', 'py:unknown'),)),
    'python.call': ((), (('result', 'py:unknown'),)),  # inputs depend on callee
    'python.call_exec': ((('exec', 'execution'),), (('then', 'execution'), ('result', 'py:unknown'))),  # callee-specific arguments
}


# One graph vocabulary; the Python lowering adapter decides eligibility.
BIND_OPERATIONS = frozenset({'python.bind_int', 'python.bind_bool'})
LOCAL_OPERATIONS = frozenset({'python.local_int', 'python.local_bool'})
ASSIGN_OPERATIONS = frozenset({'python.assign_int', 'python.assign_bool'})
READ_OPERATIONS = frozenset({'python.read_int', 'python.read_bool'})
STATE_OPERATIONS = LOCAL_OPERATIONS | ASSIGN_OPERATIONS | READ_OPERATIONS
EFFECT_OPERATIONS = BIND_OPERATIONS | STATE_OPERATIONS | {'python.require', 'python.repeat_int', 'python.repeat_end', 'python.call_exec'}


def template_ports(operation: str) -> dict:
    """Provide one canonical initial port contract for a graph-owned draft."""
    if operation not in NODE_TEMPLATES:
        raise ProgramGraphError('Unknown visual authoring template')
    if operation in ('python.call', 'python.call_exec'):
        raise ProgramGraphError('A function call requires a qualified callee signature')
    inputs, outputs = NODE_TEMPLATES[operation]
    return {
        'inputs': [{'name': label, 'type': type_id} for label, type_id in inputs],
        'outputs': [{'name': label, 'type': type_id, 'required': False}
                    for label, type_id in outputs],
    }


def view_graph(state: dict, function_id: str) -> dict:
    """Derived renderer payload. Never mutate or persist this presentation."""
    validate(state)
    if function_id not in {f['id'] for f in state['functions']}:
        raise ProgramGraphError('Unknown function graph')
    nodes = []
    selected = {n['id'] for n in state['nodes'] if n['function'] == function_id}
    for n in state['nodes']:
        if n['id'] not in selected:
            continue
        pos = state['layout'][n['id']]
        title = n['operation']
        if n['operation'] == 'python.literal':
            raw = json.dumps(n['properties'].get('value'), ensure_ascii=False, allow_nan=False)
            title += ' · ' + (raw[:35] + '…' if len(raw) > 35 else raw)
        if n['operation'] in ASSIGN_OPERATIONS | READ_OPERATIONS:
            target = n['properties'].get('local_id')
            label = next((candidate['id'] for candidate in state['nodes']
                          if candidate['id'] == target and candidate['function'] == function_id
                          and candidate['operation'] in LOCAL_OPERATIONS), None)
            if label:
                title += ' · ' + label
        nodes.append({'id': n['id'], 'kind': n['operation'], 'title': title,
                      'x': pos['x'], 'y': pos['y'], 'source_kind': 'operation',
                      'visual_family': 'program', 'containing_scope': function_id,
                      'draft_ports': {side: [{'id': p['id'], 'label': p['name'],
                                             'type': p['type']} for p in n['ports'][side]]
                                      for side in ('inputs', 'outputs')}})
    edges = [{'id': e['id'], 'source': e['source'], 'sourcePort': e['source_port'],
              'target': e['target'], 'targetPort': e['target_port'], 'relation': e['relation']}
             for e in state['edges'] if e['source'] in selected]
    return {'scope': f'{state["id"]}/{function_id}', 'nodes': nodes, 'edges': edges}


def descriptor(state: dict, function_id: str):
    """Read-only projection through the existing renderer-neutral contract."""
    from .semantic_contract import describe_graph
    return describe_graph(view_graph(state, function_id), origin='program')


class ProgramGraph:
    """One state owner: atomic commands with revision-aware undo/redo."""
    def __init__(self, state: dict | None = None, *, history_limit: int = HISTORY_LIMIT):
        if type(history_limit) is not int or not 1 <= history_limit <= 128:
            raise ValueError('Invalid graph history bound')
        self._state = copy.deepcopy(new_program() if state is None else state)
        validate(self._state)
        self._undo: list[dict] = []
        self._redo: list[dict] = []
        self._limit = history_limit
        self._path: Path | None = None
        self._base: bytes | None = None
        # Saved-state fingerprint is only a dirty marker, never a second
        # writable program or a substitute for the exact disk preimage.
        self._saved_digest: bytes | None = None

    @property
    def state(self) -> dict:
        return copy.deepcopy(self._state)

    @property
    def revision(self) -> int:
        return self._state['revision']

    @property
    def path(self) -> Path | None:
        return self._path

    @property
    def dirty(self) -> bool:
        return self._saved_digest is None or hashlib.sha256(encode(self._state)).digest() != self._saved_digest

    def _replace(self, candidate: dict, expected_revision: int):
        if type(expected_revision) is not int or expected_revision != self.revision:
            raise GraphConflict('Stale graph revision')
        candidate['revision'] = self.revision + 1
        validate(candidate)
        # Python equality aliases values such as 1 and True, even though the
        # persisted graph and typed authoring semantics distinguish them.
        # Compare canonical JSON without the monotonic revision field instead.
        if encode({k: v for k, v in candidate.items() if k != 'revision'}) == encode({
                k: v for k, v in self._state.items() if k != 'revision'}):
            return False
        self._undo.append(self._state)
        self._undo = self._undo[-self._limit:]
        self._redo.clear()
        self._state = candidate
        return True

    def edit_many(self, expected_revision: int, commands):
        """Commit bounded existing graph commands as one all-or-nothing undo step.

        Delegate each command to the established validated edit owner on an
        isolated candidate. Do not create a second mutation dispatch table.
        Failed commands cannot change the original graph or history.
        """
        if type(expected_revision) is not int or expected_revision != self.revision:
            raise GraphConflict('Stale graph revision')
        if (not isinstance(commands, (tuple, list)) or
                not 1 <= len(commands) <= 32):
            raise ProgramGraphError('Compound graph edit requires 1 to 32 commands')
        trial=ProgramGraph(self.state,history_limit=self._limit)
        for command in commands:
            if (not isinstance(command,tuple) or len(command)!=2 or
                    not isinstance(command[0],str) or not isinstance(command[1],dict)):
                raise ProgramGraphError('Compound graph command must be (action, options)')
            action,options=command
            trial.edit(trial.revision,action,**options)
        candidate=trial.state
        candidate['revision']=self.revision
        return self._replace(candidate,expected_revision)

    def edit(self, expected_revision: int, action: str, **options):
        """A bounded command API, not unrestricted mutation of the internal state."""
        if type(expected_revision) is not int or expected_revision != self.revision:
            raise GraphConflict('Stale graph revision')
        state = self.state
        def find_node(ident):
            return next((n for n in state['nodes'] if n['id'] == ident), None)
        if action == 'add_function':
            ident = options.get('id') or _id('function')
            state['functions'].append({'id': ident, 'name': options['name'],
                'parameters': [], 'return_type': 'py:unknown'})
        elif action == 'rename_function':
            function = next((f for f in state['functions'] if f['id'] == options['function']), None)
            if function is None:
                raise ProgramGraphError('Missing function')
            function['name'] = options['name']
        elif action == 'set_return_type':
            function = next((f for f in state['functions'] if f['id'] == options['function']), None)
            if function is None:
                raise ProgramGraphError('Missing function')
            function['return_type'] = options['type']
        elif action == 'remove_function':
            ident = options['function']
            if not any(f['id'] == ident for f in state['functions']):
                raise ProgramGraphError('Missing function')
            removed = {n['id'] for n in state['nodes'] if n['function'] == ident}
            state['functions'] = [f for f in state['functions'] if f['id'] != ident]
            state['nodes'] = [n for n in state['nodes'] if n['id'] not in removed]
            state['edges'] = [e for e in state['edges'] if e['source'] not in removed and e['target'] not in removed]
            state['annotations'] = [a for a in state['annotations'] if a['function'] != ident]
            state['layout'] = {k: v for k, v in state['layout'].items() if k not in removed}
        elif action == 'add_parameter':
            function = next((f for f in state['functions'] if f['id'] == options['function']), None)
            if function is None:
                raise ProgramGraphError('Missing function')
            function['parameters'].append({'id': options.get('id') or _id('parameter'),
                                           'name': options['name'], 'type': options.get('type', 'py:unknown')})
        elif action in ('rename_parameter', 'remove_parameter', 'set_parameter_type'):
            function = next((f for f in state['functions'] if f['id'] == options['function']), None)
            if function is None:
                raise ProgramGraphError('Missing function')
            parameter = next((p for p in function['parameters'] if p['id'] == options['parameter']), None)
            if parameter is None:
                raise ProgramGraphError('Missing parameter')
            if action == 'rename_parameter':
                parameter['name'] = options['name']
            elif action == 'set_parameter_type':
                parameter['type'] = options['type']
            else:
                function['parameters'] = [p for p in function['parameters'] if p['id'] != options['parameter']]
        elif action == 'add_node':
            ident = options.get('id') or _id('node')
            def ports(which):
                return [{'id': p.get('id') or _id('port'), 'name': p.get('name', ''),
                         'type': p.get('type', 'py:unknown'), 'required': p.get('required', True)}
                        for p in options.get(which, [])]
            state['nodes'].append({'id': ident, 'function': options['function'],
                                   'operation': options['operation'],
                                   'operation_version': options.get('operation_version', 1),
                                   'ports': {'inputs': ports('inputs'), 'outputs': ports('outputs')},
                                   'properties': copy.deepcopy(options.get('properties', {}))})
            state['layout'][ident] = {'x': options.get('x', 0), 'y': options.get('y', 0)}
        elif action == 'move_node':
            ident = options['node']
            if find_node(ident) is None:
                raise ProgramGraphError('Missing node')
            state['layout'][ident] = {'x': options['x'], 'y': options['y']}
        elif action == 'set_property':
            node = find_node(options['node'])
            if node is None:
                raise ProgramGraphError('Missing node')
            node['properties'][options['key']] = copy.deepcopy(options['value'])
        elif action == 'replace_node_operation':
            # A structural replacement preserves the existing port identities
            # only when both versioned templates have the *same* interface.
            # Python lowering independently qualifies the replacement; the
            # graph model must not become a second compiler.
            node = find_node(options['node'])
            new_operation = options['operation']
            if node is None or node['properties'] or node['operation_version'] != 1:
                raise ProgramGraphError('Operation replacement requires a simple known node')
            old_template = NODE_TEMPLATES.get(node['operation'])
            new_template = NODE_TEMPLATES.get(new_operation)
            if old_template is None or old_template != new_template:
                raise ProgramGraphError('Operation replacement requires compatible template ports')
            for direction, shape in (('inputs', old_template[0]), ('outputs', old_template[1])):
                ports = node['ports'][direction]
                if [(p['name'], p['type']) for p in ports] != list(shape):
                    # Dynamic or specialized ports require the owner adapter to
                    # prove a mapping; do not infer or silently reorder pins.
                    raise ProgramGraphError('Operation replacement has noncanonical ports')
            node['operation'] = new_operation
        elif action == 'connect':
            state['edges'].append({'id': options.get('id') or _id('edge'),
                'source': options['source'], 'source_port': options['source_port'],
                'target': options['target'], 'target_port': options['target_port'],
                'relation': options.get('relation', 'data')})
        elif action == 'replace_input':
            # A pin drop on an occupied target replaces exactly one wire. A
            # single edit keeps undo/redo atomic and preserves the existing
            # target wire identity; structural validation owns type/scope rules.
            target = (options['target'], options['target_port'])
            existing = next((e for e in state['edges'] if
                             (e['target'], e['target_port']) == target), None)
            if existing is None:
                raise ProgramGraphError('No existing input connection to replace')
            existing['source'] = options['source']
            existing['source_port'] = options['source_port']
            existing['relation'] = options.get('relation', existing['relation'])
        elif action == 'reconnect':
            edge = next((e for e in state['edges'] if e['id'] == options['edge']), None)
            if edge is None:
                raise ProgramGraphError('Missing edge')
            for field in ('source', 'source_port', 'target', 'target_port', 'relation'):
                if field in options:
                    edge[field] = options[field]
        elif action == 'disconnect':
            before = len(state['edges'])
            state['edges'] = [e for e in state['edges'] if e['id'] != options['edge']]
            if len(state['edges']) == before:
                raise ProgramGraphError('Missing edge')
        elif action == 'remove_selection':
            removed_nodes = set(options.get('nodes', ()))
            removed_edges = set(options.get('edges', ()))
            if (not removed_nodes and not removed_edges or
                    removed_nodes - {n['id'] for n in state['nodes']} or
                    removed_edges - {e['id'] for e in state['edges']}):
                raise ProgramGraphError('Invalid graph selection')
            state['nodes'] = [n for n in state['nodes'] if n['id'] not in removed_nodes]
            state['edges'] = [e for e in state['edges'] if e['id'] not in removed_edges
                              and e['source'] not in removed_nodes and e['target'] not in removed_nodes]
            state['layout'] = {k: v for k, v in state['layout'].items() if k not in removed_nodes}
        elif action == 'remove_node':
            ident = options['node']
            if find_node(ident) is None:
                raise ProgramGraphError('Missing node')
            state['nodes'] = [n for n in state['nodes'] if n['id'] != ident]
            state['edges'] = [e for e in state['edges'] if e['source'] != ident and e['target'] != ident]
            del state['layout'][ident]
        elif action == 'annotate':
            state['annotations'].append({'id': options.get('id') or _id('annotation'),
                                         'function': options['function'], 'text': options['text']})
        else:
            raise ProgramGraphError('Unsupported graph edit')
        return self._replace(state, expected_revision)

    def _travel(self, from_stack: list[dict], to_stack: list[dict], expected_revision: int):
        if type(expected_revision) is not int or expected_revision != self.revision:
            raise GraphConflict('Stale graph revision')
        if not from_stack:
            return False
        previous = copy.deepcopy(from_stack[-1]); previous['revision'] = self.revision + 1
        validate(previous)
        to_stack.append(self._state)
        del to_stack[:-self._limit]
        from_stack.pop()
        self._state = previous
        return True

    def undo(self, expected_revision: int):
        return self._travel(self._undo, self._redo, expected_revision)

    def redo(self, expected_revision: int):
        return self._travel(self._redo, self._undo, expected_revision)

    def saved_snapshot_for_publication(self) -> tuple[dict, bytes]:
        """Return exact saved graph bytes and state; refuse dirty/stale inputs.

        Code publishing is an independent artifact operation, not a graph
        document save. The graph must already have a stable on-disk revision.
        """
        if self._path is None or self._base is None or self.dirty:
            raise GraphConflict('Save the visual program before publishing Python')
        if self._path.is_symlink() or not self._path.is_file():
            raise GraphConflict('Saved graph is missing or was replaced')
        try:
            current=self._path.read_bytes()
        except OSError as exc:
            raise GraphConflict('Cannot verify saved graph revision') from exc
        if current != self._base:
            raise GraphConflict('Saved graph changed externally; reload before publishing')
        return self.state, self._base

    def save_as(self, path: str | Path) -> 'ProgramGraph':
        """Fork into a new graph document without rebinding/clobbering original.

        A fresh root identity avoids making two independent files claim the
        same program identity. Existing function, node and port identities
        remain stable *within* the fork. Caller adopts the returned document
        only after its independent atomic save succeeds.
        """
        candidate = self.state
        candidate['id'] = _id('program')
        candidate['revision'] = 0
        fork = ProgramGraph(candidate, history_limit=self._limit)
        fork.save(path)  # refuses existing file and symlink; original untouched
        return fork

    @classmethod
    def open(cls, path: str | Path) -> 'ProgramGraph':
        path = Path(path).expanduser().absolute()
        if path.is_symlink():
            raise ProgramGraphError('Refusing symlink graph document')
        path = path.parent.resolve(strict=True) / path.name
        if not path.is_file() or path.stat().st_size > MAX_BYTES:
            raise ProgramGraphError('Unsafe or oversized graph document')
        raw = path.read_bytes()
        try:
            state = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_pairs)
        except ProgramGraphError:
            raise
        except (UnicodeError, ValueError, RecursionError) as exc:
            raise ProgramGraphError('Invalid JSON graph document') from exc
        instance = cls(state)
        instance._path = path
        instance._base = raw
        instance._saved_digest = hashlib.sha256(encode(state)).digest()
        return instance

    def save(self, path: str | Path) -> None:
        """Atomic publication with an exact preimage inside a stable advisory lock.

        Editing remains in memory upon conflict. Never clobber an unrelated
        file or a symlink. Non-cooperating external writers are still advisory.
        """
        import fcntl  # Linux host qualification target
        data = encode(self._state)
        path = Path(path).expanduser().absolute()
        if path.is_symlink():
            raise GraphConflict('Refusing symlink graph destination')
        if not path.parent.is_dir():
            raise ProgramGraphError('Graph directory is missing')
        path = path.parent.resolve(strict=True) / path.name
        if self._path is not None and path != self._path:
            raise GraphConflict('Save As requires an explicit separate document transaction')
        if path.is_symlink():
            raise GraphConflict('Refusing symlink graph destination')
        if self._path is None and path.exists():
            raise GraphConflict('Refusing to replace existing graph document')
        directory = path.parent
        if not directory.is_dir():
            raise ProgramGraphError('Graph directory is missing')
        lock_path = directory / ('.' + path.name + '.smi-lock')
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        temp = None
        backup_temp = None
        try:
            mode = os.fstat(fd)
            if (not stat.S_ISREG(mode.st_mode) or mode.st_nlink != 1 or
                    mode.st_uid != os.getuid() or stat.S_IMODE(mode.st_mode) & 0o077):
                raise ProgramGraphError('Unsafe graph lock file')
            fcntl.flock(fd, fcntl.LOCK_EX)
            if path.is_symlink() or (path.exists() and not path.is_file()):
                raise GraphConflict('Graph document is not a regular file')
            current = path.read_bytes() if path.exists() else None
            if current != self._base:
                raise GraphConflict('Graph document changed externally')
            handle, temp = tempfile.mkstemp(prefix='.smi-program-', dir=directory)
            with os.fdopen(handle, 'wb') as stream:
                stream.write(data); stream.flush(); os.fsync(stream.fileno())
            os.chmod(temp, 0o600)
            if path.is_symlink() or (path.read_bytes() if path.exists() else None) != current:
                raise GraphConflict('Graph document changed before publication')
            # One bounded last-good backup, not an unbounded stream of
            # hidden files. It is recovery evidence, never a graph authority.
            if current is not None:
                backup_fd, backup_temp = tempfile.mkstemp(prefix='.smi-previous-', dir=directory)
                with os.fdopen(backup_fd, 'wb') as stream:
                    stream.write(current); stream.flush(); os.fsync(stream.fileno())
                os.chmod(backup_temp, 0o600)
                os.replace(backup_temp, directory / ('.' + path.name + '.smi-previous'))
                backup_temp = None
            os.replace(temp, path); temp = None
            dir_fd = os.open(directory, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
            self._path, self._base = path, data
            self._saved_digest = hashlib.sha256(data).digest()
        finally:
            os.close(fd)
            if temp is not None:
                os.unlink(temp)
            if backup_temp is not None:
                os.unlink(backup_temp)
