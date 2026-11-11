"""Explicit, non-executing Python preview of qualified graph-owned programs.

ProgramGraph remains the only document authority. This module does not read/write
source files, execute generated code, inspect Qt state, or broaden unknown nodes.
Only pure integer/Boolean expressions, direct non-recursive *pure* graph calls,
and bounded structured execution with Branch, Require, ordered bindings,
explicit local declaration/assignment/read snapshots, and Return Flow are qualified, with a bounded counted Repeat body.
Arbitrary CFGs, back-edges, nested loops, execution joins and unqualified effects are not supported. Incomplete graphs remain valid documents but do not lower.
"""
from __future__ import annotations

import ast
import copy
from dataclasses import dataclass
import heapq

from .program_graph import (NODE_TEMPLATES, validate, BIND_OPERATIONS, LOCAL_OPERATIONS,
                            ASSIGN_OPERATIONS, READ_OPERATIONS, STATE_OPERATIONS, EFFECT_OPERATIONS)

MAX_FUNCTION_NODES = 256
MAX_PREVIEW_BYTES = 200_000
MAX_REPEAT_COUNT = 10_000  # Explicit runtime limit, not a compile-time guess
# Independent-source syntax normalization is a proof adapter, not Python execution.
MAX_INDEPENDENT_AST_NODES = 4096

# One compiler vocabulary for all integer comparison operations. The graph's
# canonical port shape is owned by NODE_TEMPLATES; this table owns Python
# syntax only. Import and lowering both use it, so a comparison cannot become
# source-editable without also being executable through the same adapter.
INTEGER_COMPARISON_AST = {
    'python.less_than': ast.Lt,
    'python.equal_int': ast.Eq,
    'python.greater_than': ast.Gt,
    'python.less_or_equal': ast.LtE,
    'python.greater_or_equal': ast.GtE,
    'python.not_equal_int': ast.NotEq,
}
INTEGER_COMPARISON_BY_AST = {syntax: operation for operation, syntax in INTEGER_COMPARISON_AST.items()}
# Keep arithmetic construction and source reconciliation in one vocabulary,
# just like integer comparisons. Python's // and % retain their signed integer
# semantics, including ZeroDivisionError when the right operand is zero.
INTEGER_ARITHMETIC_AST = {
    'python.add': ast.Add,
    'python.subtract': ast.Sub,
    'python.multiply': ast.Mult,
    'python.floor_divide': ast.FloorDiv,
    'python.modulo': ast.Mod,
}
INTEGER_ARITHMETIC_BY_AST = {syntax: operation for operation, syntax in INTEGER_ARITHMETIC_AST.items()}
SOURCE_EDITABLE_OPERATIONS = frozenset(INTEGER_ARITHMETIC_AST) | INTEGER_COMPARISON_AST.keys()
# Source-to-graph input reconciliation only changes wires already owned by
# ProgramGraph. These non-arithmetic nodes have existing canonical input ports;
# no AST nodes, program operations or graph identities are synthesized.
SOURCE_REWIRE_OPERATIONS = SOURCE_EDITABLE_OPERATIONS | {
    'python.not', 'python.select_int', 'python.select_bool',
    'python.return', 'python.return_flow', 'python.call', 'python.call_exec',
    'python.branch', 'python.require', 'python.repeat_int',
} | BIND_OPERATIONS | LOCAL_OPERATIONS | ASSIGN_OPERATIONS

@dataclass(frozen=True)
class PythonPreview:
    source: str | None
    issues: tuple[str, ...]
    # Stable graph identity mapped to the generated source's line number.
    node_lines: tuple[tuple[str, int], ...] = ()


class _Unqualified(ValueError):
    pass


def _fail(scope: str, message: str) -> None:
    raise _Unqualified(f'{scope}: {message}')


def _port_shape(node, expected_in, expected_out, scope):
    """Validate a versioned operation interface without treating unknown as a type.

    Graph drafts may use py:unknown, but explicit port declarations cannot
    contradict the qualified producer/consumer contract. This validation is
    independent from the actual data-edge type checks below.
    """
    if node['operation_version'] != 1:
        _fail(scope, 'unsupported operation version')
    for side, shape in (('inputs', expected_in), ('outputs', expected_out)):
        ports = node['ports'][side]
        if [p['name'] for p in ports] != [name for name, _ in shape]:
            _fail(scope, f'{side} do not match the qualified operation signature')
        for port, (_, qualified_type) in zip(ports, shape):
            if port['type'] not in (qualified_type, 'py:unknown'):
                _fail(scope, f'{side} require integer-compatible {qualified_type} ports' if qualified_type == 'py:int' else f'{side} require {qualified_type} ports')
            if side == 'inputs' and not port['required']:
                _fail(scope, 'qualified expression inputs must be required')


def _preview(state):
    functions = {f['id']: f for f in state['functions']}
    if not functions:
        _fail('program', 'add a function before generating Python')
    by_function = {fid: [] for fid in functions}
    for n in state['nodes']:
        by_function[n['function']].append(n)
    edges = {fid: [] for fid in functions}
    node_owner = {n['id']: n['function'] for n in state['nodes']}
    for e in state['edges']:
        function_id = node_owner[e['source']]
        edges[function_id].append(e)

    # Calls form a separate graph; refuse recursion until control/effects have
    # defined behavior. This also catches forward/back references correctly.
    calls = {fid: set() for fid in functions}
    for fid, members in by_function.items():
        if len(members) > MAX_FUNCTION_NODES:
            _fail(functions[fid]['name'], 'function exceeds lowering node bound')
        for n in members:
            if n['operation'] in ('python.call', 'python.call_exec'):
                callee = n['properties'].get('callee_id')
                if not isinstance(callee, str) or callee not in functions:
                    _fail(n['id'], 'called function does not exist')
                calls[fid].add(callee)
    visiting = set()
    visited = set()

    def inspect_calls(fid):
        if fid in visiting:
            _fail(functions[fid]['name'], 'recursive graph calls are not qualified')
        if fid in visited:
            return
        visiting.add(fid)
        for callee in sorted(calls[fid]):
            inspect_calls(callee)
        visiting.remove(fid)
        visited.add(fid)

    for fid in sorted(functions):
        inspect_calls(fid)

    # An execution guard raises on failure. Such a function must not be
    # lowered as a pure data producer in another graph: the call could move
    # before the intended execution point or be speculatively evaluated.
    effectful = {fid for fid, members in by_function.items()
                 if any(n['operation'] in EFFECT_OPERATIONS for n in members)}
    # Only a pure data call must refuse effects. A call on an explicit
    # execution edge may invoke effectful callees in source order.
    for fid in sorted(functions):
        pending = [n['properties'].get('callee_id') for n in by_function[fid]
                   if n['operation'] == 'python.call']
        seen = set()
        while pending:
            callee = pending.pop()
            if callee in seen:
                continue
            seen.add(callee)
            if callee in effectful:
                _fail(functions[fid]['name'], 'effectful function calls require explicit execution semantics')
            pending.extend(calls[callee])

    module = ast.Module(body=[], type_ignores=[])
    source_nodes = {}  # (function, generated name) -> ordered origin node IDs
    return_nodes = {}  # function name -> ordered graph Return IDs
    control_nodes = {}  # function name -> (Entry ID, ordered Branch IDs), if present
    guard_nodes = {}  # function name -> ordered effectful Require IDs
    loop_nodes_by_scope = {}  # function name -> Repeat IDs in source order
    loop_end_nodes_by_scope = {}  # function name -> matching body terminators
    loop_count_names_by_scope = {}  # generated bookkeeping assignments, not separate nodes
    for func in sorted(functions.values(), key=lambda f: f['name']):
        fid = func['id']
        scope = func['name']
        if func['return_type'] not in ('py:int', 'py:bool'):
            _fail(scope, 'qualified functions must declare py:int or py:bool return type')
        if any(p['type'] not in ('py:int', 'py:bool') for p in func['parameters']):
            _fail(scope, 'every parameter must declare py:int or py:bool')
        members = {n['id']: n for n in by_function[fid]}
        if not members:
            _fail(scope, 'function has no operations')
        flow_mode = any(n['operation'] in EFFECT_OPERATIONS or
                        n['operation'] in ('python.entry', 'python.branch', 'python.return_flow')
                        for n in members.values())
        returns = [n for n in members.values() if n['operation'] == 'python.return']
        if not flow_mode and len(returns) != 1:
            _fail(scope, 'exactly one Return is required')
        if flow_mode and returns:
            _fail(scope, 'structured control functions cannot mix Return node kinds')
        return_nodes[scope] = []
        inputs = {}
        successors = {node_id: set() for node_id in members}
        indegree = {node_id: 0 for node_id in members}
        control_edges = [e for e in edges[fid] if e['relation'] == 'control']
        if control_edges and not flow_mode:
            _fail(control_edges[0]['id'], 'control flow requires a qualified Entry and Branch')
        for edge in edges[fid]:
            if edge['relation'] != 'data':
                continue
            target = members[edge['target']]
            target_port = next(p for p in target['ports']['inputs'] if p['id'] == edge['target_port'])
            inputs[target['id'], target_port['name']] = edge['source']
            if target['id'] not in successors[edge['source']]:
                successors[edge['source']].add(target['id'])
                indegree[target['id']] += 1
        queue = [key for key, count in indegree.items() if count == 0]
        heapq.heapify(queue)
        order = []
        while queue:
            current = heapq.heappop(queue)
            order.append(current)
            for neighbor in sorted(successors[current]):
                indegree[neighbor] -= 1
                if indegree[neighbor] == 0:
                    heapq.heappush(queue, neighbor)
        if len(order) != len(members):
            _fail(scope, 'cyclic data dependency')
        # Report the actionable missing pin before an orphan that it may cause.
        for node in members.values():
            for port in node['ports']['inputs']:
                if port['required'] and port['type'] != 'execution' and (node['id'], port['name']) not in inputs:
                    _fail(node['id'], f'missing input {port["name"]}')
        if not flow_mode:
            reachable = set()
            stack = [returns[0]['id']]
            predecessors = {key: set() for key in members}
            for edge in edges[fid]:
                predecessors[edge['target']].add(edge['source'])
            while stack:
                current = stack.pop()
                if current in reachable:
                    continue
                reachable.add(current)
                stack.extend(predecessors[current])
            if reachable != set(members):
                _fail(scope, 'orphan operations would be silently discarded')
        body = []
        temp_index = 0
        parameters = {p['id']: p for p in func['parameters']}
        reserved = {p['name'] for p in func['parameters']} | {f['name'] for f in functions.values()}

        def emit_nodes(node_ids, target_body, values, value_types):
            nonlocal temp_index
            body = target_body
            def operand(node_id, name, expected_type):
                source = inputs.get((node_id, name))
                if source is None:
                    _fail(node_id, f'missing input {name}')
                if value_types[source] != expected_type:
                    _fail(node_id, f'{name} expects integer py:int, got {value_types[source]}' if expected_type == 'py:int' else f'{name} expects {expected_type}, got {value_types[source]}')
                return values[source]

            for node_id in node_ids:
                node = members[node_id]
                op = node['operation']
                props = node['properties']
                if op == 'python.literal':
                    if set(props) != {'value'} or type(props['value']) not in (int, bool):
                        _fail(node_id, 'literal must be a real integer or boolean')
                    value_type = 'py:bool' if type(props['value']) is bool else 'py:int'
                    _port_shape(node, (), (('value', value_type),), node_id)
                    if len(str(props['value'])) > 1000:
                        _fail(node_id, 'integer literal is too large')
                    value = ast.Constant(value=props['value'])
                elif op == 'python.parameter':
                    if set(props) != {'parameter_id'} or not isinstance(props['parameter_id'], str) or props['parameter_id'] not in parameters:
                        _fail(node_id, 'parameter reference is missing or stale')
                    parameter = parameters[props['parameter_id']]
                    value_type = parameter['type']
                    _port_shape(node, (), (('value', value_type),), node_id)
                    value = ast.Name(id=parameter['name'], ctx=ast.Load())
                elif op in INTEGER_ARITHMETIC_AST:
                    value_type = 'py:int'
                    _port_shape(node, (('left', 'py:int'), ('right', 'py:int')),
                                (('result', 'py:int'),), node_id)
                    if props:
                        _fail(node_id, 'unknown arithmetic properties')
                    value = ast.BinOp(left=operand(node_id, 'left', 'py:int'),
                        op=INTEGER_ARITHMETIC_AST[op](),
                        right=operand(node_id, 'right', 'py:int'))
                elif op in INTEGER_COMPARISON_AST:
                    value_type = 'py:bool'
                    _port_shape(node, (('left', 'py:int'), ('right', 'py:int')),
                                (('result', 'py:bool'),), node_id)
                    if props:
                        _fail(node_id, 'unknown comparison properties')
                    value = ast.Compare(left=operand(node_id, 'left', 'py:int'),
                                        ops=[INTEGER_COMPARISON_AST[op]()],
                                        comparators=[operand(node_id, 'right', 'py:int')])
                elif op == 'python.not':
                    value_type = 'py:bool'
                    _port_shape(node, (('value', 'py:bool'),), (('result', 'py:bool'),), node_id)
                    if props:
                        _fail(node_id, 'unknown Boolean Not properties')
                    value = ast.UnaryOp(op=ast.Not(), operand=operand(node_id, 'value', 'py:bool'))
                elif op in ('python.select_int', 'python.select_bool'):
                    # A value multiplexer, not an execution Branch. All inputs
                    # are already bound in the pure DAG. Never claim laziness or
                    # admit effects until the execution-flow contract exists.
                    value_type = 'py:int' if op == 'python.select_int' else 'py:bool'
                    _port_shape(node, (('condition', 'py:bool'), ('true_value', value_type),
                                       ('false_value', value_type)), (('result', value_type),), node_id)
                    if props:
                        _fail(node_id, 'unknown value-selection properties')
                    value = ast.IfExp(test=operand(node_id, 'condition', 'py:bool'),
                                      body=operand(node_id, 'true_value', value_type),
                                      orelse=operand(node_id, 'false_value', value_type))
                elif op == 'python.call':
                    if set(props) != {'callee_id'} or props['callee_id'] not in functions:
                        _fail(node_id, 'unqualified call target')
                    callee = functions[props['callee_id']]
                    value_type = callee['return_type']
                    _port_shape(node, [(p['name'], p['type']) for p in callee['parameters']],
                                (('result', value_type),), node_id)
                    value = ast.Call(func=ast.Name(id=callee['name'], ctx=ast.Load()),
                                     args=[operand(node_id, p['name'], p['type']) for p in callee['parameters']], keywords=[])
                elif op == 'python.return':
                    _port_shape(node, (('value', func['return_type']),), (), node_id)
                    if props:
                        _fail(node_id, 'unknown Return properties')
                    body.append(ast.Return(value=operand(node_id, 'value', func['return_type'])))
                    return_nodes[scope].append(node_id)
                    continue
                else:
                    _fail(node_id, f'{op}@{node["operation_version"]} is not qualified')
                # Emit one binding per operation, so fan-out computes a call exactly
                # once and shared expression DAGs do not expand exponentially.
                temp = f'_smi_value_{temp_index}'
                while temp in reserved:
                    temp_index += 1
                    temp = f'_smi_value_{temp_index}'
                reserved.add(temp)
                temp_index += 1
                body.append(ast.Assign(targets=[ast.Name(id=temp, ctx=ast.Store())], value=value))
                values[node_id] = ast.Name(id=temp, ctx=ast.Load())
                value_types[node_id] = value_type
                source_nodes.setdefault((scope, temp), []).append(node_id)

        if not flow_mode:
            emit_nodes(order, body, {}, {})
        else:
            entries = [n for n in members.values() if n['operation'] == 'python.entry']
            branches = [n for n in members.values() if n['operation'] == 'python.branch']
            terminal = [n for n in members.values() if n['operation'] == 'python.return_flow']
            repeats = [n for n in members.values() if n['operation'] == 'python.repeat_int']
            repeat_ends = [n for n in members.values() if n['operation'] == 'python.repeat_end']
            guards = [n for n in members.values() if n['operation'] == 'python.require']
            bindings = [n for n in members.values()
                        if n['operation'] in BIND_OPERATIONS]
            state_nodes = [n for n in members.values() if n['operation'] in STATE_OPERATIONS]
            if (len(entries) != 1 or not terminal or len(terminal) != len(branches) + 1
                    or len(repeats) != len(repeat_ends)):
                _fail(scope, 'structured execution requires one Entry and a Return Flow on every leaf')
            entry = entries[0]
            execution_calls = [n for n in members.values() if n['operation'] == 'python.call_exec']
            execution_nodes = {n['id']: n for n in entries + branches + guards + bindings + state_nodes + repeats + repeat_ends + execution_calls + terminal}
            for node in execution_nodes.values():
                op = node['operation']
                if op == 'python.entry':
                    expected_in, expected_out = (), (('then', 'execution'),)
                elif op == 'python.branch':
                    expected_in = (('exec', 'execution'), ('condition', 'py:bool'))
                    expected_out = (('true', 'execution'), ('false', 'execution'))
                elif op == 'python.require':
                    expected_in = (('exec', 'execution'), ('condition', 'py:bool'))
                    expected_out = (('then', 'execution'),)
                elif op == 'python.repeat_int':
                    expected_in = (('exec', 'execution'), ('count', 'py:int'))
                    expected_out = (('body', 'execution'), ('after', 'execution'))
                elif op == 'python.repeat_end':
                    expected_in, expected_out = (('exec', 'execution'),), ()
                elif op == 'python.call_exec':
                    callee_id = node['properties'].get('callee_id')
                    if set(node['properties']) != {'callee_id'} or callee_id not in functions:
                        _fail(node['id'], 'unqualified execution call target')
                    callee = functions[callee_id]
                    if any(p['name'] == 'exec' for p in callee['parameters']):
                        _fail(node['id'], 'execution call parameter conflicts with exec pin')
                    expected_in = (('exec', 'execution'),) + tuple(
                        (p['name'], p['type']) for p in callee['parameters'])
                    expected_out = (('then', 'execution'), ('result', callee['return_type']))
                elif op in BIND_OPERATIONS:
                    typ = 'py:int' if op == 'python.bind_int' else 'py:bool'
                    expected_in = (('exec', 'execution'), ('value', typ))
                    expected_out = (('then', 'execution'), ('value', typ))
                elif op in LOCAL_OPERATIONS | ASSIGN_OPERATIONS:
                    typ = 'py:int' if op.endswith('_int') else 'py:bool'
                    expected_in = (('exec', 'execution'), ('value', typ))
                    expected_out = (('then', 'execution'),)
                elif op in READ_OPERATIONS:
                    typ = 'py:int' if op.endswith('_int') else 'py:bool'
                    expected_in = (('exec', 'execution'),)
                    expected_out = (('then', 'execution'), ('value', typ))
                else:
                    expected_in, expected_out = (('exec', 'execution'), ('value', func['return_type'])), ()
                _port_shape(node, expected_in, expected_out, node['id'])
                if op in ASSIGN_OPERATIONS | READ_OPERATIONS:
                    props = node['properties']
                    if set(props) != {'local_id'} or not isinstance(props['local_id'], str):
                        _fail(node['id'], 'state operation requires exactly one local_id')
                    declaration = members.get(props['local_id'])
                    expected_local = 'python.local_int' if op.endswith('_int') else 'python.local_bool'
                    if declaration is None or declaration['operation'] != expected_local:
                        _fail(node['id'], 'state operation references an absent or incompatible local declaration')
                elif op != 'python.call_exec' and node['properties']:
                    _fail(node['id'], 'execution nodes cannot have properties')

            def port_name(node_id, port_id, side):
                return next(p['name'] for p in members[node_id]['ports'][side]
                            if p['id'] == port_id)

            successors_control = {node_id: {} for node_id in execution_nodes}
            predecessors_control = {node_id: 0 for node_id in execution_nodes}
            for edge in control_edges:
                source = edge['source']
                target = edge['target']
                if source not in execution_nodes or target not in execution_nodes:
                    _fail(edge['id'], 'execution path contains unsupported operation')
                source_op = execution_nodes[source]['operation']
                target_op = execution_nodes[target]['operation']
                if source_op in ('python.return_flow', 'python.repeat_end') or target_op == 'python.entry':
                    _fail(edge['id'], 'unqualified execution direction')
                source_port = port_name(source, edge['source_port'], 'outputs')
                target_port = port_name(target, edge['target_port'], 'inputs')
                if target_port != 'exec' or source_port in successors_control[source]:
                    _fail(edge['id'], 'unqualified execution port or duplicated path')
                successors_control[source][source_port] = target
                predecessors_control[target] += 1
            for node_id, node in execution_nodes.items():
                op = node['operation']
                expected = ({'then'} if op == 'python.entry' or op in EFFECT_OPERATIONS - {'python.repeat_int', 'python.repeat_end'} else
                            {'true', 'false'} if op == 'python.branch' else
                            {'body', 'after'} if op == 'python.repeat_int' else set())
                if set(successors_control[node_id]) != expected:
                    _fail(node_id, 'Entry/Branch outputs and Require continuation must connect to qualified execution paths')
                if predecessors_control[node_id] != (0 if op == 'python.entry' else 1):
                    _fail(node_id, 'execution paths must have one parent; joins and cycles are not qualified')
            if len(control_edges) != len(execution_nodes) - 1:
                _fail(scope, 'unqualified execution path count')
            reachable_control = set()
            def traverse(node_id):
                if node_id in reachable_control:
                    _fail(node_id, 'cyclic or joined execution path')
                reachable_control.add(node_id)
                for output in ('then', 'true', 'false', 'body', 'after'):
                    child = successors_control[node_id].get(output)
                    if child is not None:
                        traverse(child)
            traverse(entry['id'])
            if reachable_control != set(execution_nodes):
                _fail(scope, 'disconnected execution path or cycle')
            control_nodes[scope] = (entry['id'], [])
            guard_nodes[scope] = []
            loop_nodes = []
            loop_end_ids = []
            loop_count_names = set()

            def closure(start):
                found = set()
                stack = [start]
                while stack:
                    node_id = stack.pop()
                    if node_id in found:
                        continue
                    if node_id in execution_nodes:
                        if members[node_id]['operation'] in BIND_OPERATIONS | READ_OPERATIONS | {'python.call_exec'}:
                            # A binding is an exec-qualified value boundary.
                            # Its producer may not be evaluated before exec.
                            found.add(node_id)
                            continue
                        _fail(node_id, 'execution node cannot produce a data value')
                    if members[node_id]['operation'] == 'python.return':
                        _fail(node_id, 'Return cannot produce a data value')
                    found.add(node_id)
                    stack.extend(source for (target, _), source in inputs.items() if target == node_id)
                return found

            used = set(execution_nodes)
            def emit_needed(root, target_body, values, types):
                required = closure(root)
                for dependency in required:
                    if members[dependency]['operation'] in BIND_OPERATIONS | READ_OPERATIONS | {'python.call_exec'} and dependency not in values:
                        _fail(dependency, 'bound value is used before its execution path')
                used.update(required)
                emit_nodes([node_id for node_id in order if node_id in required and node_id not in values],
                           target_body, values, types)

            def emit_control(node_id, target_body, values, types, slots, *, in_loop=False):
                nonlocal temp_index
                node = execution_nodes[node_id]
                if node['operation'] == 'python.repeat_end':
                    if not in_loop:
                        _fail(node_id, 'Repeat End is only qualified inside a Repeat body')
                    loop_end_ids.append(node_id)
                    return
                if node['operation'] == 'python.return_flow':
                    if in_loop:
                        _fail(node_id, 'Return Flow inside Repeat body is not qualified')
                    root = inputs[(node_id, 'value')]
                    emit_needed(root, target_body, values, types)
                    if types[root] != func['return_type']:
                        _fail(node_id, 'Return Flow value type differs from function return type')
                    target_body.append(ast.Return(value=values[root]))
                    return_nodes[scope].append(node_id)
                    return
                if node['operation'] in ('python.bind_int', 'python.bind_bool'):
                    source = inputs[(node_id, 'value')]
                    emit_needed(source, target_body, values, types)
                    wanted = 'py:int' if node['operation'] == 'python.bind_int' else 'py:bool'
                    if types[source] != wanted:
                        _fail(node_id, f'binding expects {wanted}, got {types[source]}')
                    # This single-assignment value cannot be hoisted before
                    # execution; a use in another branch or before this node
                    # has no binding in that path and is refused above.
                    name = f'_smi_value_{temp_index}'
                    while name in reserved:
                        temp_index += 1
                        name = f'_smi_value_{temp_index}'
                    reserved.add(name)
                    temp_index += 1
                    target_body.append(ast.Assign(
                        targets=[ast.Name(id=name, ctx=ast.Store())],
                        value=values[source]))
                    values[node_id] = ast.Name(id=name, ctx=ast.Load())
                    types[node_id] = wanted
                    source_nodes.setdefault((scope, name), []).append(node_id)
                    emit_control(successors_control[node_id]['then'], target_body, values, types, slots, in_loop=in_loop)
                    return
                if node['operation'] == 'python.repeat_int':
                    if in_loop:
                        _fail(node_id, 'nested Repeat is not qualified')
                    source = inputs[(node_id, 'count')]
                    emit_needed(source, target_body, values, types)
                    if types[source] != 'py:int':
                        _fail(node_id, 'Repeat count expects py:int')
                    if 'range' in reserved or 'ValueError' in reserved:
                        _fail(scope, 'range or ValueError name is shadowed; cannot lower Repeat')
                    # The count is evaluated exactly once and bounded at runtime.
                    # A fixed upper limit prevents runaway generated loops, even
                    # when the count originates from a function parameter.
                    count_name = f'_smi_repeat_count_{len(loop_nodes)}'
                    while count_name in reserved:
                        count_name += '_'
                    reserved.add(count_name)
                    target_body.append(ast.Assign(targets=[ast.Name(id=count_name, ctx=ast.Store())],
                                                  value=values[source]))
                    loop_count_names.add(count_name)
                    invalid_count = ast.BoolOp(op=ast.Or(), values=[
                        ast.Compare(left=ast.Name(id=count_name, ctx=ast.Load()),
                                    ops=[ast.Lt()], comparators=[ast.Constant(value=0)]),
                        ast.Compare(left=ast.Name(id=count_name, ctx=ast.Load()),
                                    ops=[ast.Gt()], comparators=[ast.Constant(value=MAX_REPEAT_COUNT)])])
                    target_body.append(ast.If(test=invalid_count, body=[ast.Raise(
                        exc=ast.Call(func=ast.Name(id='ValueError', ctx=ast.Load()),
                                     args=[ast.Constant(value='Superior MI graph Repeat count outside 0..10000')],
                                     keywords=[]), cause=None)], orelse=[]))
                    # Body values are per-iteration; typed local storage is shared.
                    # Copies here prevent a value captured in one iteration from
                    # being treated as already available on the After path.
                    body_stmts = []
                    emit_control(successors_control[node_id]['body'], body_stmts,
                                 values.copy(), types.copy(), slots.copy(), in_loop=True)
                    counter_name = f'_smi_repeat_index_{len(loop_nodes)}'
                    while counter_name in reserved:
                        counter_name += '_'
                    reserved.add(counter_name)
                    loop_nodes.append(node_id)
                    target_body.append(ast.For(
                        target=ast.Name(id=counter_name, ctx=ast.Store()),
                        iter=ast.Call(func=ast.Name(id='range', ctx=ast.Load()),
                                      args=[ast.Name(id=count_name, ctx=ast.Load())], keywords=[]),
                        body=body_stmts or [ast.Pass()], orelse=[], type_comment=None))
                    emit_control(successors_control[node_id]['after'], target_body,
                                 values, types, slots, in_loop=False)
                    return
                if node['operation'] == 'python.call_exec':
                    callee = functions[node['properties']['callee_id']]
                    arguments = []
                    for parameter in callee['parameters']:
                        source = inputs[(node_id, parameter['name'])]
                        emit_needed(source, target_body, values, types)
                        if types[source] != parameter['type']:
                            _fail(node_id, 'execution call argument ' + parameter['name'] +
                                  ' expects ' + parameter['type'])
                        arguments.append(values[source])
                    name = f'_smi_value_{temp_index}'
                    while name in reserved:
                        temp_index += 1
                        name = f'_smi_value_{temp_index}'
                    temp_index += 1
                    reserved.add(name)
                    target_body.append(ast.Assign(
                        targets=[ast.Name(id=name, ctx=ast.Store())],
                        value=ast.Call(func=ast.Name(id=callee['name'], ctx=ast.Load()),
                                       args=arguments, keywords=[])))
                    values[node_id] = ast.Name(id=name, ctx=ast.Load())
                    types[node_id] = callee['return_type']
                    source_nodes.setdefault((scope, name), []).append(node_id)
                    emit_control(successors_control[node_id]['then'], target_body,
                                 values, types, slots, in_loop=in_loop)
                    return
                if node['operation'] in STATE_OPERATIONS:
                    operation = node['operation']
                    wanted = 'py:int' if operation.endswith('_int') else 'py:bool'
                    if operation in READ_OPERATIONS:
                        declaration_id = node['properties']['local_id']
                        if declaration_id not in slots:
                            _fail(node_id, 'local read before declaration or outside its execution path')
                        slot_name = slots[declaration_id]
                        # Capture an immutable value at this exact execution
                        # instant. Later assignments must not retroactively
                        # change an earlier output pin's meaning.
                        name = f'_smi_value_{temp_index}'
                        while name in reserved:
                            temp_index += 1
                            name = f'_smi_value_{temp_index}'
                        reserved.add(name)
                        temp_index += 1
                        target_body.append(ast.Assign(
                            targets=[ast.Name(id=name, ctx=ast.Store())],
                            value=ast.Name(id=slot_name, ctx=ast.Load())))
                        values[node_id] = ast.Name(id=name, ctx=ast.Load())
                        types[node_id] = wanted
                        source_nodes.setdefault((scope, name), []).append(node_id)
                    else:
                        source = inputs[(node_id, 'value')]
                        emit_needed(source, target_body, values, types)
                        if types[source] != wanted:
                            _fail(node_id, f'local assignment expects {wanted}, got {types[source]}')
                        if operation in LOCAL_OPERATIONS:
                            slot_name = f'_smi_slot_{temp_index}'
                            while slot_name in reserved:
                                temp_index += 1
                                slot_name = f'_smi_slot_{temp_index}'
                            temp_index += 1
                            reserved.add(slot_name)
                            slots[node_id] = slot_name
                        else:
                            declaration_id = node['properties']['local_id']
                            if declaration_id not in slots:
                                _fail(node_id, 'local assignment before declaration or outside its execution path')
                            slot_name = slots[declaration_id]
                        target_body.append(ast.Assign(
                            targets=[ast.Name(id=slot_name, ctx=ast.Store())], value=values[source]))
                        source_nodes.setdefault((scope, slot_name), []).append(node_id)
                    emit_control(successors_control[node_id]['then'], target_body, values, types, slots, in_loop=in_loop)
                    return
                if node['operation'] == 'python.require':
                    condition = inputs[(node_id, 'condition')]
                    emit_needed(condition, target_body, values, types)
                    if types[condition] != 'py:bool':
                        _fail(node_id, 'Require condition expects py:bool')
                    # Assert is removed by python -O; explicit Raise retains
                    # the effect in all runtime optimization modes.
                    if 'ValueError' in reserved:
                        _fail(scope, 'ValueError name is shadowed; cannot lower Require')
                    guard_nodes[scope].append(node_id)
                    failure = ast.Raise(exc=ast.Call(
                        func=ast.Name(id='ValueError', ctx=ast.Load()),
                        args=[ast.Constant(value='Superior MI graph Require failed')],
                        keywords=[]), cause=None)
                    target_body.append(ast.If(test=ast.UnaryOp(
                        op=ast.Not(), operand=values[condition]),
                        body=[failure], orelse=[]))
                    emit_control(successors_control[node_id]['then'], target_body, values, types, slots, in_loop=in_loop)
                    return
                if in_loop:
                    _fail(node_id, 'Branch inside Repeat body is not qualified')
                if node['operation'] != 'python.branch':
                    _fail(node_id, 'invalid execution node in Branch tree')
                condition = inputs[(node_id, 'condition')]
                emit_needed(condition, target_body, values, types)
                if types[condition] != 'py:bool':
                    _fail(node_id, 'condition expects py:bool')
                control_nodes[scope][1].append(node_id)
                branches_body = []
                for choice in ('true', 'false'):
                    statements = []
                    emit_control(successors_control[node_id][choice], statements,
                                 values.copy(), types.copy(), slots.copy(), in_loop=in_loop)
                    branches_body.append(statements)
                target_body.append(ast.If(test=values[condition], body=branches_body[0],
                                          orelse=branches_body[1]))

            emit_control(successors_control[entry['id']]['then'], body, {}, {}, {})
            loop_nodes_by_scope[scope] = loop_nodes
            loop_end_nodes_by_scope[scope] = loop_end_ids
            loop_count_names_by_scope[scope] = loop_count_names
            if used != set(members):
                _fail(scope, 'orphan operations would be silently discarded')
        if not body or not isinstance(body[-1], (ast.Return, ast.If)):
            _fail(scope, 'Return must terminate the qualified function')
        args = ast.arguments(posonlyargs=[], args=[ast.arg(arg=p['name'], annotation=None)
                    for p in func['parameters']], vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[])
        module.body.append(ast.FunctionDef(name=scope, args=args, body=body, decorator_list=[],
                                            returns=None, type_comment=None))
    ast.fix_missing_locations(module)
    source = ast.unparse(module) + '\n'
    if len(source.encode('utf-8')) > MAX_PREVIEW_BYTES:
        _fail('program', 'generated preview exceeds size bound')
    parsed = ast.parse(source)
    compile(parsed, '<Superior-MI-ProgramGraph-preview>', 'exec')  # NEVER execute
    lines = []
    for definition in parsed.body:
        returns = iter(return_nodes[definition.name])
        branch_ids = iter(control_nodes[definition.name][1]) if definition.name in control_nodes else iter(())
        require_ids = iter(guard_nodes.get(definition.name, ()))
        loops = iter(loop_nodes_by_scope.get(definition.name, ()))
        loop_ends = iter(loop_end_nodes_by_scope.get(definition.name, ()))
        count_names = loop_count_names_by_scope.get(definition.name, set())
        if definition.name in control_nodes:
            lines.append((control_nodes[definition.name][0], definition.lineno))

        assignment_counts = {}
        def map_statements(statements):
            # AST source order is depth-first; ast.walk is breadth-first and
            # would misattribute nested Branch/Return lines to graph identities.
            for statement in statements:
                if isinstance(statement, ast.Assign):
                    if statement.targets[0].id in count_names:
                        continue  # Repeat node is mapped to the real For statement.
                    key = (definition.name, statement.targets[0].id)
                    index = assignment_counts.get(key, 0)
                    assignment_counts[key] = index + 1
                    node_id = source_nodes[key][index]
                    lines.append((node_id, statement.lineno))
                elif isinstance(statement, ast.For):
                    lines.append((next(loops), statement.lineno))
                    map_statements(statement.body)
                    lines.append((next(loop_ends), statement.end_lineno))
                elif isinstance(statement, ast.If):
                    # Repeat range guard is not a Require node.
                    if statement.body and isinstance(statement.body[0], ast.Raise) and (
                            isinstance(statement.body[0].exc, ast.Call) and
                            statement.body[0].exc.args and
                            isinstance(statement.body[0].exc.args[0], ast.Constant) and
                            str(statement.body[0].exc.args[0].value).startswith('Superior MI graph Repeat count')):
                        continue
                    # Require's generated guard has only a raising true arm;
                    # Branch has both explicit execution arms.
                    lines.append((next(branch_ids) if statement.orelse else next(require_ids),
                                  statement.lineno))
                    if statement.orelse:
                        map_statements(statement.body)
                        map_statements(statement.orelse)
                elif isinstance(statement, ast.Return):
                    lines.append((next(returns), statement.lineno))

        map_statements(definition.body)
    return PythonPreview(source, (), tuple(lines))


def preview_python(state: dict) -> PythonPreview:
    """Qualify full document and return deterministic preview or diagnostic.

    Structural failures are reported, never changed; graph state remains valid
    independently of whether a Python preview is possible.
    """
    try:
        validate(state)
        return _preview(state)
    except (_Unqualified, ValueError, SyntaxError, TypeError, RecursionError) as exc:
        return PythonPreview(None, (str(exc),))


def _align_generated_value_names(base_source: str, baseline: PythonPreview,
                                 lowered_source: str, lowered: PythonPreview):
    """Align compiler-created local temporaries via stable graph node IDs.

    Emission may change the numbering of `_smi_value_*` when dependencies
    change. Only compare source AST after a one-to-one rename justified by
    node-line receipts from BOTH successful compiler lowerings. This is a
    transient proof, never a stored source mapping or a rename of user text.
    """
    import copy
    def node_symbols(text, preview):
        tree = ast.parse(text)
        per_line = {}
        for fn in tree.body:
            if isinstance(fn, ast.FunctionDef):
                for item in ast.walk(fn):
                    if (isinstance(item, ast.Assign) and len(item.targets) == 1
                            and isinstance(item.targets[0], ast.Name)
                            and item.targets[0].id.startswith('_smi_value_')):
                        per_line[item.lineno] = (fn.name, item.targets[0].id)
        return tree, {node_id: per_line[line] for node_id, line in preview.node_lines
                      if line in per_line}
    original_tree, original = node_symbols(base_source, baseline)
    lowered_tree, updated = node_symbols(lowered_source, lowered)
    if set(original) != set(updated):
        return None
    renames = {}
    for node_id in original:
        old_scope, old_name = original[node_id]
        new_scope, new_name = updated[node_id]
        if old_scope != new_scope:
            return None
        renames.setdefault(old_scope, {})[new_name] = old_name
    for scope, renamed in renames.items():
        if len(renamed) != len(set(renamed.values())):
            return None
    result = copy.deepcopy(lowered_tree)
    class Reassign(ast.NodeTransformer):
        def __init__(self, names):
            self.names = names
        def visit_Name(self, node):
            if node.id.startswith('_smi_value_'):
                if node.id not in self.names:
                    raise ValueError('Unmapped generated value')
                node.id = self.names[node.id]
            return node
    try:
        for fn in result.body:
            if isinstance(fn, ast.FunctionDef):
                Reassign(renames.get(fn.name, {})).visit(fn)
    except ValueError:
        return None
    return result


def _pure_reorderable_value(expression):
    """Shared conservative value policy for independent-source identity/order proofs.

    Not a claim of arbitrary expression purity: calls, division/modulo,
    comprehensions and potentially effectful/raising constructs are excluded.
    Both proofs still require complete compiler equivalence before import.
    """
    if isinstance(expression, (ast.Name, ast.Constant)):
        return True
    if isinstance(expression, ast.BinOp):
        return (isinstance(expression.op, (ast.Add, ast.Sub, ast.Mult))
                and _pure_reorderable_value(expression.left)
                and _pure_reorderable_value(expression.right))
    if isinstance(expression, ast.Compare):
        return (len(expression.ops) == len(expression.comparators) == 1
                and type(expression.ops[0]) in INTEGER_COMPARISON_BY_AST
                and _pure_reorderable_value(expression.left)
                and _pure_reorderable_value(expression.comparators[0]))
    if isinstance(expression, ast.UnaryOp):
        return (isinstance(expression.op, (ast.Not, ast.USub))
                and _pure_reorderable_value(expression.operand))
    if isinstance(expression, ast.IfExp):
        return ( _pure_reorderable_value(expression.test)
                 and _pure_reorderable_value(expression.body)
                 and _pure_reorderable_value(expression.orelse))
    return False


def _equivalent_pure_assignment_order(generated: ast.AST, candidate: ast.AST) -> bool:
    """Prove equality modulo safe adjacent generated-value ordering.

    This is exclusively an *independent-source* proof. Neither owner receives a
    persistent mapping. Reordering is limited to contiguous pure assignments
    within one suite (including separate if/else and loop suites). It cannot
    cross control, call, state or effect boundaries, nor reorder potentially
    raising division/modulo. Each source must define its dependencies before
    use. The complete graph has independently passed lowering.
    """
    import copy


    def normalize(tree):
        clone = copy.deepcopy(tree)
        if not isinstance(clone, ast.Module):
            return None

        def target(statement):
            if (isinstance(statement, ast.Assign) and len(statement.targets) == 1
                    and isinstance(statement.targets[0], ast.Name)
                    and statement.targets[0].id.startswith('_smi_value_')
                    and _pure_reorderable_value(statement.value)):
                return statement.targets[0].id
            return None

        def normalize_suite(statements):
            # Suites are execution boundaries. Only reorder *within* a branch
            # or loop body, never across the condition, iteration, else arm,
            # call, or effect. Nested expressions are not independently edited.
            for statement in statements:
                if isinstance(statement, (ast.If, ast.For, ast.While)):
                    if not (normalize_suite(statement.body)
                            and normalize_suite(statement.orelse)):
                        return False
            index = 0
            while index < len(statements):
                if target(statements[index]) is None:
                    index += 1
                    continue
                end = index
                while end < len(statements) and target(statements[end]) is not None:
                    end += 1
                run = statements[index:end]
                if len(run) > 1:
                    names = [target(statement) for statement in run]
                    if len(names) != len(set(names)):
                        return False
                    run_names = set(names)
                    defined = set()
                    for statement in run:
                        # A reference to a later producer is not rescued by
                        # the graph's *eventual* topology. Python executes the
                        # current source in order, so reject that forward read.
                        uses = {n.id for n in ast.walk(statement.value)
                                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
                        if (uses & run_names) - defined:
                            return False
                        defined.add(target(statement))
                    statements[index:end] = sorted(run, key=target)
                index = end
            return True

        for fn in clone.body:
            if isinstance(fn, ast.FunctionDef) and not normalize_suite(fn.body):
                return None
        return clone

    normalized_generated = normalize(generated)
    normalized_candidate = normalize(candidate)
    return (normalized_generated is not None and normalized_candidate is not None
            and ast.dump(normalized_generated, include_attributes=False)
            == ast.dump(normalized_candidate, include_attributes=False))


def _source_ast_mismatch(expected: ast.AST, actual: ast.AST) -> str:
    """Explain the first AST disagreement; never decide whether an edit is valid.

    Reconciliation is authorized solely by the graph compiler/re-lowering proof.
    This bounded, read-only diagnostic traverses *that proof's* two parsed
    trees. Paths are structural, not persistent source anchors. Independent
    source functions are normalized before this point; their real source
    region is provided by the caller's error wrapper.
    """
    def describe(node):
        if isinstance(node, ast.AST):
            return type(node).__name__
        if isinstance(node, list):
            return f'{len(node)} entries'
        if isinstance(node, str):
            return repr(node[:60]) + ('...' if len(node) > 60 else '')
        if isinstance(node, (int, bool, type(None))):
            return repr(node)
        return type(node).__name__

    def walk(left, right, path, location, depth):
        if depth > 80:
            return path, location, 'nested syntax exceeds diagnostic depth'
        if isinstance(left, ast.AST) and isinstance(right, ast.AST):
            location = (getattr(right, 'lineno', None) or location)
            if type(left) is not type(right):
                return path, location, f'{describe(left)} vs {describe(right)}'
            for field in left._fields:
                result = walk(getattr(left, field), getattr(right, field),
                              path + '.' + field, location, depth + 1)
                if result is not None:
                    return result
            return None
        if isinstance(left, list) and isinstance(right, list):
            for index, (a, b) in enumerate(zip(left, right)):
                result = walk(a, b, f'{path}[{index}]', location, depth + 1)
                if result is not None:
                    return result
            if len(left) != len(right):
                return path, location, f'{len(left)} statements vs {len(right)} statements'
            return None
        if type(left) is not type(right) or left != right:
            return path, location, f'{describe(left)} vs {describe(right)}'
        return None

    mismatch = walk(expected, actual, 'module', None, 0)
    if mismatch is None:
        return 'no syntax difference (source formatting only)'
    path, line, detail = mismatch
    # These line numbers come from the parsed candidate supplied to the
    # compiler. For independent functions that candidate is synthetic, so
    # callers must not mistake them for exact original file positions.
    where = f' at candidate AST line {line}' if line is not None else ''
    return f'first mismatch {path}{where}: {detail}'


@dataclass(frozen=True)
class SourceEditChange:
    """One supported edit to an existing graph identity; no new code owner."""
    function: str
    node_id: str
    action: str
    before: object
    after: object
    # Named receiving input for a compiler-proven wire replacement. None for
    # literal/operator changes. Existing callers retain their receipt shape.
    input_port: str | None = None


@dataclass(frozen=True)
class SourceEditReview:
    """Read-only result of the same compiler proof used by import."""
    graph_revision: int
    changes: tuple[SourceEditChange, ...]


def _qualified_source_edit_plan(graph, base_source: str, edited_source: str, *,
                                expected_revision: int, allow_source_trivia: bool = False,
                                allow_pure_reordering: bool = False,
                                _baseline_preview: PythonPreview | None = None,
                                _baseline_tree: ast.Module | None = None):
    """Qualify mapped generated-Python edits *without* mutating the owner.

    The caller retains ownership of the edited text until this explicit import.
    There is no fuzzy source matching, automatic text overwrite, or new graph
    authority. A literal, compatible operator, or existing data-input change is recognized
    using the existing generated source map; a complete re-lowering must reproduce the
    candidate exactly for generated-source imports; independent-source review
    may additionally prove narrow, dependency-valid pure statement reordering
    with stable graph-owned node IDs. Effects, unsupported control changes,
    ambiguous identities and concurrent edits are always refused.
    """
    from .program_graph import ProgramGraph, ProgramGraphError, GraphConflict
    if not isinstance(graph, ProgramGraph):
        raise TypeError('Generated-source import requires a ProgramGraph')
    if type(expected_revision) is not int or expected_revision != graph.revision:
        raise GraphConflict('Graph revision changed since source generation')
    # ProgramGraph.state is a defensive deep copy. Capture the exact state
    # *once* after the revision guard; all candidate mapping and trial lowering
    # refer to the same authoritative graph snapshot in this preflight.
    state = graph.state
    # The independent-function caller has already qualified this exact
    # graph revision and parsed the generated source. Reuse those immutable
    # witnesses for the same synchronous preflight; never cache across edits.
    baseline = _baseline_preview if _baseline_preview is not None else preview_python(state)
    if baseline.source is None or base_source != baseline.source:
        raise GraphConflict('Generated source base no longer matches this graph')
    if not isinstance(edited_source, str):
        raise TypeError('Edited source must be text')
    try:
        edited_bytes = edited_source.encode('utf-8')
    except UnicodeError as exc:
        raise ProgramGraphError('Edited Python source cannot be encoded as UTF-8') from exc
    if len(edited_bytes) > MAX_PREVIEW_BYTES:
        raise ProgramGraphError('Edited Python exceeds preview size limit')
    if edited_source == base_source:
        return SourceEditReview(expected_revision, ()), ()
    try:
        candidate_tree = ast.parse(edited_source)
    except (SyntaxError, UnicodeError, ValueError, RecursionError) as exc:
        raise ProgramGraphError(
            f'Edited Python syntax at line {getattr(exc, "lineno", None) or "unknown"}, '
            f'column {getattr(exc, "offset", None) or "unknown"}: {exc}') from exc
    # The graph-owned generated baseline is already validated; parse it once
    # for mapping, read-only diagnostics, and final compiler proof.
    baseline_tree = _baseline_tree if _baseline_tree is not None else ast.parse(base_source)
    # Independent-source imports identify statements by their existing
    # function/target identity, not by assignment position. This allows a
    # dependency-correct reordering of qualified pure values while the final
    # independent compiler proof still refuses effects/control-flow drift.
    # Generated-Python dialog imports retain their stronger byte-exact gate.
    mapped_lines = {}
    if allow_pure_reordering and not allow_source_trivia:
        raise ValueError('Pure ordering exception requires independent-source proof')
    if allow_source_trivia and not allow_pure_reordering:
        base_assigns = [n for n in ast.walk(baseline_tree) if isinstance(n, ast.Assign)]
        edited_assigns = [n for n in ast.walk(candidate_tree) if isinstance(n, ast.Assign)]
        if len(base_assigns) != len(edited_assigns) or any(
            [ast.dump(t, include_attributes=False) for t in a.targets] !=
            [ast.dump(t, include_attributes=False) for t in b.targets]
            for a, b in zip(base_assigns, edited_assigns)
        ):
            raise ProgramGraphError('Edited Python changed mapped assignment structure')
        mapped_lines = {a.lineno: b.lineno for a, b in zip(base_assigns, edited_assigns)}
        base_returns = [n for n in ast.walk(baseline_tree) if isinstance(n, ast.Return)]
        candidate_returns = [n for n in ast.walk(candidate_tree) if isinstance(n, ast.Return)]
        if len(base_returns) != len(candidate_returns):
            raise ProgramGraphError('Edited Python changed mapped Return structure')
        mapped_lines.update((a.lineno, b.lineno) for a, b in zip(base_returns, candidate_returns))
    if allow_pure_reordering:
        # Unique (top-level function, generated target) names are exact graph
        # identities, not fuzzy matches. Repeated assignments to the same
        # variable retain the original positional rule (and cannot reorder).
        def statements_by_scope(tree):
            return {fn.name: [item for item in ast.walk(fn) if isinstance(item, ast.Assign)]
                    for fn in tree.body if isinstance(fn, ast.FunctionDef)}
        base_scopes = statements_by_scope(baseline_tree)
        edited_scopes = statements_by_scope(candidate_tree)
        if set(base_scopes) != set(edited_scopes):
            raise ProgramGraphError('Edited Python changed mapped function structure')
        for scope, base_assigns in base_scopes.items():
            edited_assigns = edited_scopes[scope]
            def assign_key(item):
                if len(item.targets) == 1 and isinstance(item.targets[0], ast.Name):
                    return item.targets[0].id
                return None
            base_keys = [assign_key(item) for item in base_assigns]
            edited_keys = [assign_key(item) for item in edited_assigns]
            if len(base_keys) != len(edited_keys) or sorted(str(k) for k in base_keys) != sorted(str(k) for k in edited_keys):
                raise ProgramGraphError(f'Function {scope!r} changed mapped assignment identities')
            # A duplicated variable target is ambiguous when statement order
            # changes. Exact positional alignment is still safe for it.
            from collections import Counter
            counts = Counter(base_keys)
            candidates = {k: item for k, item in zip(edited_keys, edited_assigns) if counts[k] == 1}
            for position, (key, original) in enumerate(zip(base_keys, base_assigns)):
                current = (candidates[key] if counts[key] == 1
                           else edited_assigns[position])
                if counts[key] != 1 and assign_key(current) != key:
                    raise ProgramGraphError(f'Function {scope!r} reordered ambiguous assignment')
                mapped_lines[original.lineno] = current.lineno
        base_returns = [n for n in ast.walk(baseline_tree) if isinstance(n, ast.Return)]
        candidate_returns = [n for n in ast.walk(candidate_tree) if isinstance(n, ast.Return)]
        if len(base_returns) != len(candidate_returns):
            raise ProgramGraphError('Edited Python changed mapped Return structure')
        mapped_lines.update((a.lineno, b.lineno) for a, b in zip(base_returns, candidate_returns))
    def candidate_line(node_id):
        line = line_by_node.get(node_id)
        return mapped_lines.get(line, line) if allow_source_trivia else line
    def literal_value(expression):
        # In parsed Python, -3 is UnaryOp(USub, Constant(3)), not a
        # Constant(-3). Accept this one bounded integer-literal spelling,
        # without evaluating arbitrary unary expressions or coercing bools.
        # Final graph lowering still proves the complete edited AST.
        if isinstance(expression, ast.Constant):
            return expression.value
        if (isinstance(expression, ast.UnaryOp) and isinstance(expression.op, ast.USub)
                and isinstance(expression.operand, ast.Constant)
                and type(expression.operand.value) is int):
            return -expression.operand.value
        return None

    # One read-only candidate AST pass collects the exact statements needed
    # by literals, operations and inputs. No additional parser or source map.
    candidates_by_line = {}
    mapped_operations = {}
    edited_assignments = {}
    edited_returns = {}
    edited_conditions = {}
    edited_loops = {}
    repeat_counts = {}
    for item in ast.walk(candidate_tree):
        if isinstance(item, ast.Assign) and len(item.targets) == 1 and isinstance(item.targets[0], ast.Name):
            edited_assignments.setdefault(item.lineno, []).append(item)
            value = literal_value(item.value)
            if type(value) in (int, bool):
                candidates_by_line.setdefault(item.lineno, []).append(value)
            if isinstance(item.value, ast.BinOp):
                operation = INTEGER_ARITHMETIC_BY_AST.get(type(item.value.op))
            elif (isinstance(item.value, ast.Compare) and
                  len(item.value.ops) == len(item.value.comparators) == 1):
                operation = INTEGER_COMPARISON_BY_AST.get(type(item.value.ops[0]))
            else:
                operation = None
            if operation is not None:
                mapped_operations.setdefault(item.lineno, []).append(operation)
        elif isinstance(item, ast.Return):
            edited_returns.setdefault(item.lineno, []).append(item)
        elif isinstance(item, ast.If):
            edited_conditions.setdefault(item.lineno, []).append(item)
        elif isinstance(item, ast.For):
            edited_loops.setdefault(item.lineno, []).append(item)
    line_by_node = dict(baseline.node_lines)
    proposed = []
    # Existing typed node identities remain the sole reversible edit targets.
    for node in state['nodes']:
        if node['operation'] != 'python.literal':
            continue
        line = candidate_line(node['id'])
        values = candidates_by_line.get(line, [])
        if len(values) != 1 or type(values[0]) not in (int, bool):
            continue
        original = node['properties'].get('value')
        if type(values[0]) is type(original) and values[0] != original:
            proposed.append(('set_property', node['id'], {'key': 'value', 'value': values[0]}))
    for node in state['nodes']:
        if node['operation'] not in SOURCE_EDITABLE_OPERATIONS:
            continue
        changed = mapped_operations.get(candidate_line(node['id']), [])
        if len(changed) == 1 and changed[0] != node['operation']:
            proposed.append(('replace_node_operation', node['id'], {'operation': changed[0]}))
    # Input wiring is already owned by ProgramGraph.replace_input. Source edits
    # may select another *existing* generated value, but only when we can map
    # both values by unique canonical assignments in the same graph function.
    # Never synthesize nodes or a source-to-graph identity store. The complete
    # trial graph below must emit the edited AST, including evaluation order.
    generated_assignments = {item.lineno: item for item in ast.walk(baseline_tree)
        if isinstance(item, ast.Assign) and len(item.targets) == 1 and
        isinstance(item.targets[0], ast.Name)}
    members = {node['id']: node for node in state['nodes']}
    values_by_function = {}
    for node in members.values():
        origin = generated_assignments.get(line_by_node.get(node['id']))
        if origin is not None:
            values_by_function.setdefault(node['function'], {}).setdefault(
                origin.targets[0].id, []).append(node)
    existing_inputs = {(edge['target'], edge['target_port']): edge for edge in state['edges']
                       if edge['relation'] == 'data'}
    # Use one existing graph input owner for every supported expression shape.
    # A pure Return and structured Return Flow are included because their
    # graph inputs already exist; source Return expressions are not operations
    # that need synthetic assignment nodes. A trial re-lowering remains the
    # final authority for return scope, reachability, effects and data typing.
    # Repeat declarations are already present in the candidate AST. Restrict
    # their lookup to the actual owning function, never a global name index.
    candidate_functions = {fn.name: fn for fn in candidate_tree.body
                           if isinstance(fn, ast.FunctionDef)}
    for scope, function in candidate_functions.items():
        counts = {}
        for item in ast.walk(function):
            if (isinstance(item, ast.Assign) and len(item.targets) == 1
                    and isinstance(item.targets[0], ast.Name)
                    and item.targets[0].id.startswith('_smi_repeat_count_')):
                counts.setdefault(item.targets[0].id, []).append(item)
        repeat_counts[scope] = counts

    functions_by_id = {fn['id']: fn for fn in state['functions']}

    def source_operands(node, statement):
        operation = node['operation']
        if operation in ('python.return', 'python.return_flow'):
            if isinstance(statement, ast.Return):
                return {'value': statement.value}
            return {}
        if operation == 'python.branch':
            # Structured Branch has two executable arms and one existing bool
            # condition pin. Exact trial lowering proves arm and effect identity.
            if isinstance(statement, ast.If) and statement.orelse:
                return {'condition': statement.test}
            return {}
        if operation == 'python.repeat_int':
            # Repeat's source-map line belongs to its For node, while its
            # count is single-evaluated in the preceding generated assignment.
            # Reuse that exact generated name only; malformed or unrelated
            # loops are rejected by the final whole-function AST proof.
            if (isinstance(statement, ast.For) and
                    isinstance(statement.iter, ast.Call) and
                    isinstance(statement.iter.func, ast.Name) and
                    statement.iter.func.id == 'range' and
                    len(statement.iter.args) == 1 and not statement.iter.keywords and
                    isinstance(statement.iter.args[0], ast.Name)):
                scope = functions_by_id[node['function']]['name']
                count_name = statement.iter.args[0].id
                if not count_name.startswith('_smi_repeat_count_'):
                    return {}
                declarations = repeat_counts.get(scope, {}).get(count_name, ())
                if len(declarations) == 1 and declarations[0].lineno < statement.lineno:
                    return {'count': declarations[0].value}
            return {}
        if operation == 'python.require':
            # Require is lowered as `if not condition: raise ValueError(...)`.
            # Only its existing condition pin is editable; changing the guard
            # shape or raising behavior must fail the full compiler proof.
            if (isinstance(statement, ast.If) and not statement.orelse
                    and len(statement.body) == 1
                    and isinstance(statement.body[0], ast.Raise)
                    and isinstance(statement.test, ast.UnaryOp)
                    and isinstance(statement.test.op, ast.Not)):
                return {'condition': statement.test.operand}
            return {}
        if not isinstance(statement, ast.Assign):
            return {}
        if operation in BIND_OPERATIONS | LOCAL_OPERATIONS | ASSIGN_OPERATIONS:
            # These existing effectful writes have a single typed value input.
            # Never edit the destination, ordering, or local identity.
            return {'value': statement.value}
        expression = statement.value
        if (operation in SOURCE_EDITABLE_OPERATIONS and isinstance(expression, ast.BinOp)
                and type(expression.op) in INTEGER_ARITHMETIC_BY_AST):
            return {'left': expression.left, 'right': expression.right}
        if (operation in SOURCE_EDITABLE_OPERATIONS and isinstance(expression, ast.Compare)
                and len(expression.ops) == len(expression.comparators) == 1
                and type(expression.ops[0]) in INTEGER_COMPARISON_BY_AST):
            return {'left': expression.left, 'right': expression.comparators[0]}
        if operation in ('python.call', 'python.call_exec') and isinstance(expression, ast.Call):
            callee = functions_by_id.get(node['properties'].get('callee_id'))
            if (callee is not None and isinstance(expression.func, ast.Name)
                    and expression.func.id == callee['name'] and not expression.keywords
                    and len(expression.args) == len(callee['parameters'])):
                # The execution pin of call_exec is never an argument. Match
                # the existing callee signature, not incidental port order.
                return {parameter['name']: arg for parameter, arg in
                        zip(callee['parameters'], expression.args)}
            return {}
        if operation == 'python.not' and isinstance(expression, ast.UnaryOp) and isinstance(expression.op, ast.Not):
            return {'value': expression.operand}
        if (operation in ('python.select_int', 'python.select_bool')
                and isinstance(expression, ast.IfExp)):
            return {'condition': expression.test, 'true_value': expression.body,
                    'false_value': expression.orelse}
        return {}

    for node in members.values():
        if node['operation'] not in SOURCE_REWIRE_OPERATIONS:
            continue
        statements = (edited_returns if node['operation'] in ('python.return', 'python.return_flow')
                      else edited_conditions if node['operation'] in ('python.branch', 'python.require')
                      else edited_loops if node['operation'] == 'python.repeat_int'
                      else edited_assignments).get(candidate_line(node['id']), ())
        if len(statements) != 1:
            continue
        operands = source_operands(node, statements[0])
        for input_port in node['ports']['inputs']:
            name = input_port['name']
            if name not in operands or not isinstance(operands[name], ast.Name):
                continue
            possible = values_by_function.get(node['function'], {}).get(operands[name].id, ())
            if len(possible) != 1 or len(possible[0]['ports']['outputs']) != 1:
                continue
            source = possible[0]
            outgoing_port = source['ports']['outputs'][0]['id']
            current = existing_inputs.get((node['id'], input_port['id']))
            if (current is not None and (current['source'], current['source_port']) !=
                    (source['id'], outgoing_port)):
                proposed.append(('replace_input', node['id'], {
                    'target': node['id'], 'target_port': input_port['id'],
                    'source': source['id'], 'source_port': outgoing_port,
                    'before': (current['source'], current['source_port']),
                    'input_name': name}))
    if not proposed and allow_source_trivia:
        if (ast.dump(candidate_tree, include_attributes=False) ==
                ast.dump(baseline_tree, include_attributes=False)):
            return SourceEditReview(expected_revision, ()), ()
        # A source-only permutation of *already proven* pure assignments
        # should not be misreported as a graph edit. This exception is
        # independent-source-only and uses the same suite/dependency proof
        # as the nonempty trial-graph path.
        if allow_pure_reordering and _equivalent_pure_assignment_order(
                baseline_tree, candidate_tree):
            return SourceEditReview(expected_revision, ()), ()
        raise ProgramGraphError('Edited Python differs beyond qualified mapped expressions; '+
                                _source_ast_mismatch(baseline_tree, candidate_tree))
    if not 1 <= len(proposed) <= 32:
        raise ProgramGraphError('Only 1 to 32 mapped literal, operator, or input edits are qualified')
    commands=[(action, {'node': node_id, **{k:v for k,v in changes.items() if k not in ('before','input_name')}})
              for action,node_id,changes in proposed]
    # Prove the entire candidate matches an independently lowered graph before
    # committing anything. This rejects unrelated edits, syntax/format churn,
    # extra statements, moved IDs and changes to effect ordering. The existing
    # ProgramGraph owner validates and publishes the whole batch atomically.
    trial = ProgramGraph(state)
    trial.edit_many(trial.revision,commands)
    checked = preview_python(trial.state)
    if checked.issues or checked.source is None:
        raise ProgramGraphError('Edited Python cannot be reproduced by the qualified graph: '+
                                '; '.join(checked.issues))
    if allow_source_trivia:
        lowered_tree = ast.parse(checked.source)
        if ast.dump(lowered_tree, include_attributes=False) != ast.dump(candidate_tree, include_attributes=False):
            if not allow_pure_reordering:
                raise ProgramGraphError('Edited Python differs beyond qualified mapped expressions; '+
                                        _source_ast_mismatch(lowered_tree, candidate_tree))
            aligned = _align_generated_value_names(base_source, baseline, checked.source, checked)
            if aligned is None or not _equivalent_pure_assignment_order(aligned, candidate_tree):
                raise ProgramGraphError('Edited Python changes unsupported statement order, effects, or graph semantics; '+
                                        _source_ast_mismatch(lowered_tree, candidate_tree))
    elif checked.source != edited_source:
        raise ProgramGraphError('Generated Python must match the qualified compiler output exactly')
    function_names={fn['id']:fn['name'] for fn in state['functions']}
    originals={node['id']:node for node in state['nodes']}
    edits=[]
    for action,node_id,changes in proposed:
        original=originals[node_id]
        if action == 'set_property':
            before, after = original['properties']['value'], changes['value']
        elif action == 'replace_node_operation':
            before, after = original['operation'], changes['operation']
        else:
            before, after = changes['before'], (changes['source'], changes['source_port'])
        edits.append(SourceEditChange(function_names[original['function']],node_id,action,before,after,
                                      changes.get('input_name') if action=='replace_input' else None))
    return SourceEditReview(expected_revision,tuple(edits)),commands





def review_generated_source_edit(graph, base_source: str, edited_source: str, *,
                                 expected_revision: int, allow_source_trivia: bool = False) -> SourceEditReview:
    """Preflight proposed generated-source edits without assigning a later graph revision.

    A reentrant ProgramGraph transaction invalidates the review, even when
    the trial compiler succeeded or the proposed edit is a no-op.
    """
    from .program_graph import ProgramGraphError, GraphConflict
    try:
        review,_=_qualified_source_edit_plan(graph,base_source,edited_source,
            expected_revision=expected_revision,allow_source_trivia=allow_source_trivia)
    except ProgramGraphError as exc:
        if graph.revision != expected_revision:
            raise GraphConflict('Graph revision changed during generated source review') from exc
        raise
    if graph.revision != expected_revision:
        raise GraphConflict('Graph revision changed during generated source review')
    return review


def import_generated_source_edit(graph, base_source: str, edited_source: str, *,
                                 expected_revision: int, allow_source_trivia: bool = False) -> bool:
    """Requalify and atomically commit only the exact proven graph revision."""
    from .program_graph import ProgramGraphError, GraphConflict
    try:
        review,commands=_qualified_source_edit_plan(graph,base_source,edited_source,
            expected_revision=expected_revision,allow_source_trivia=allow_source_trivia)
    except ProgramGraphError as exc:
        if graph.revision != expected_revision:
            raise GraphConflict('Graph revision changed during generated source import') from exc
        raise
    if graph.revision != expected_revision:
        raise GraphConflict('Graph revision changed during generated source import')
    if not commands:
        return False
    return graph.edit_many(review.graph_revision,commands)


@dataclass(frozen=True)
class IndependentFunctionReview:
    """Proven edit candidates in ONE source-owned top-level function.

    The unmodeled rest of the Python file is retained by the source owner and
    is NOT declared to be represented by ProgramGraph. This is a review receipt,
    not a persistent source link or authorization to import a later revision.
    """
    graph_revision: int
    source_revision: int
    source_sha256: str
    function: str
    start_line: int
    end_line: int
    changes: tuple[SourceEditChange, ...]
    unmodeled_top_level: int
    change_lines: tuple[tuple[str, str, int], ...] = ()
    # 1-based source-owner statement columns, end exclusive; advisory only.
    change_spans: tuple[tuple[str, str, int, int, int, int], ...] = ()


@dataclass(frozen=True)
class IndependentFunctionsReview:
    """One atomic preflight for explicitly selected, graph-owned function regions.

    The regions are informational evidence, not an independently persisted
    mapping. The exact source text and graph are requalified at commit time.
    """
    graph_revision: int
    source_revision: int
    source_sha256: str
    functions: tuple[str, ...]
    regions: tuple[tuple[str, int, int], ...]
    changes: tuple[SourceEditChange, ...]
    unmodeled_top_level: int
    # Optional original source-owner locations. This is evidence, not a
    # persistent anchor: commit requalifies the current source/graph revisions.
    change_lines: tuple[tuple[str, str, int], ...] = ()
    change_spans: tuple[tuple[str, str, int, int, int, int], ...] = ()


def _module_function_binding_conflicts(module, selected):
    """Find explicit shadows of ALL selected graph functions in one AST pass.

    This is one conservative static identity guard, not Python dataflow. A
    selected definition is not its own shadow. Deferred function/lambda bodies
    and class-local bindings do not shadow module names; definition-time
    expressions and explicit class ``global`` writes do. No project code runs.
    """
    names = frozenset(selected)

    class Visitor(ast.NodeVisitor):
        def __init__(self):
            self.lines = {name: set() for name in names}

        def mark(self, target, line):
            if target in names:
                self.lines[target].add(line)

        def definition_expressions(self, node):
            for expression in node.decorator_list:
                self.visit(expression)
            for expression in (*node.args.defaults, *node.args.kw_defaults):
                if expression is not None:
                    self.visit(expression)
            for argument in (*node.args.posonlyargs, *node.args.args,
                             *node.args.kwonlyargs,
                             *((node.args.vararg,) if node.args.vararg else ()),
                             *((node.args.kwarg,) if node.args.kwarg else ())):
                if argument.annotation is not None:
                    self.visit(argument.annotation)
            if node.returns is not None:
                self.visit(node.returns)

        def visit_FunctionDef(self, node):
            if selected.get(node.name) is not node:
                self.mark(node.name, node.lineno)
            self.definition_expressions(node)

        def visit_AsyncFunctionDef(self, node):
            self.mark(node.name, node.lineno)
            self.definition_expressions(node)

        def visit_ClassDef(self, node, *, module_binding=True):
            # A nested class is bound in its enclosing class namespace, not
            # the module. Its own explicit `global` writes nevertheless reach
            # the module and must be checked independently.
            if module_binding:
                self.mark(node.name, node.lineno)
            if module_binding:
                for expression in (*node.decorator_list, *node.bases):
                    self.visit(expression)
                for keyword in node.keywords:
                    self.visit(keyword.value)
            # Nested class definition expressions were visited in the
            # enclosing ClassSuite, where their writes have class scope.
            # Normal class assignments belong to the class, not module. An
            # explicit global declaration makes a matching write module-owned.
            class ClassSuite(ast.NodeVisitor):
                """Collect actual class-scope binds, never deferred method bodies.

                Python's `global` applies to imports, definitions, exception
                targets and pattern captures as well as simple assignments.
                Class-local names without that declaration are not shadows.
                Nested class scopes are examined separately.
                """
                def __init__(self):
                    self.globals = set()
                    self.writes = []
                    self.nested = []

                def bind(self, name, line):
                    if name in names:
                        self.writes.append((name, line))

                def visit_Global(self, statement):
                    self.globals.update(statement.names)

                def visit_Name(self, expression):
                    if isinstance(expression.ctx, (ast.Store, ast.Del)):
                        self.bind(expression.id, expression.lineno)

                def function_signature(self, statement):
                    for expression in statement.decorator_list:
                        self.visit(expression)
                    for expression in (*statement.args.defaults, *statement.args.kw_defaults):
                        if expression is not None:
                            self.visit(expression)
                    for argument in (*statement.args.posonlyargs, *statement.args.args,
                                     *statement.args.kwonlyargs,
                                     *((statement.args.vararg,) if statement.args.vararg else ()),
                                     *((statement.args.kwarg,) if statement.args.kwarg else ())):
                        if argument.annotation is not None:
                            self.visit(argument.annotation)
                    if statement.returns is not None:
                        self.visit(statement.returns)

                def visit_FunctionDef(self, statement):
                    self.bind(statement.name, statement.lineno)
                    self.function_signature(statement)

                def visit_AsyncFunctionDef(self, statement):
                    self.bind(statement.name, statement.lineno)
                    self.function_signature(statement)

                def visit_ClassDef(self, statement):
                    self.bind(statement.name, statement.lineno)
                    for expression in (*statement.decorator_list, *statement.bases):
                        self.visit(expression)
                    for keyword in statement.keywords:
                        self.visit(keyword.value)
                    self.nested.append(statement)

                def visit_Import(self, statement):
                    for alias in statement.names:
                        self.bind(alias.asname or alias.name.split('.')[0], statement.lineno)

                def visit_ImportFrom(self, statement):
                    for alias in statement.names:
                        if alias.name == '*':
                            for name in names:
                                self.bind(name, statement.lineno)
                        else:
                            self.bind(alias.asname or alias.name, statement.lineno)

                def visit_ExceptHandler(self, statement):
                    if statement.name:
                        self.bind(statement.name, statement.lineno)
                    self.generic_visit(statement)

                def visit_MatchAs(self, statement):
                    if statement.name:
                        self.bind(statement.name, statement.lineno)
                    self.generic_visit(statement)

                def visit_MatchStar(self, statement):
                    if statement.name:
                        self.bind(statement.name, statement.lineno)

                def visit_MatchMapping(self, statement):
                    if statement.rest:
                        self.bind(statement.rest, statement.lineno)
                    self.generic_visit(statement)

                def visit_Lambda(self, expression):
                    # Defaults evaluate during class execution; body is deferred.
                    for default in (*expression.args.defaults, *expression.args.kw_defaults):
                        if default is not None:
                            self.visit(default)

                def visit_ListComp(self, expression):
                    # Comprehension iteration targets have their own scope.
                    self.visit(expression.elt)
                    for generator in expression.generators:
                        self.visit(generator.iter)
                        for condition in generator.ifs:
                            self.visit(condition)

                def visit_SetComp(self, expression):
                    self.visit_ListComp(expression)

                def visit_GeneratorExp(self, expression):
                    self.visit_ListComp(expression)

                def visit_DictComp(self, expression):
                    self.visit(expression.key)
                    self.visit(expression.value)
                    for generator in expression.generators:
                        self.visit(generator.iter)
                        for condition in generator.ifs:
                            self.visit(condition)

            suite = ClassSuite()
            for statement in node.body:
                suite.visit(statement)
            for target, line in suite.writes:
                if target in suite.globals:
                    self.mark(target, line)
            for nested in suite.nested:
                self.visit_ClassDef(nested, module_binding=False)

        def visit_Import(self, node):
            for alias in node.names:
                self.mark(alias.asname or alias.name.split('.')[0], node.lineno)

        def visit_ImportFrom(self, node):
            for alias in node.names:
                if alias.name == '*':
                    for name in names:
                        self.mark(name, node.lineno)
                else:
                    self.mark(alias.asname or alias.name, node.lineno)

        def visit_AnnAssign(self, node):
            # A bare module annotation (`function: Type`) does NOT bind a
            # value. Its annotation expression still runs unless postponed,
            # so inspect that expression; an initializer does bind normally.
            if node.value is not None:
                self.visit(node.target)
                self.visit(node.value)
            self.visit(node.annotation)

        def visit_Name(self, node):
            if isinstance(node.ctx, (ast.Store, ast.Del)):
                self.mark(node.id, node.lineno)

        def visit_ExceptHandler(self, node):
            if node.name:
                self.mark(node.name, node.lineno)
            self.generic_visit(node)

        def visit_MatchAs(self, node):
            if node.name:
                self.mark(node.name, node.lineno)
            self.generic_visit(node)

        def visit_MatchStar(self, node):
            if node.name:
                self.mark(node.name, node.lineno)

        def visit_MatchMapping(self, node):
            if node.rest:
                self.mark(node.rest, node.lineno)
            self.generic_visit(node)

        def visit_Lambda(self, node):
            for expression in (*node.args.defaults, *node.args.kw_defaults):
                if expression is not None:
                    self.visit(expression)

        def visit_ListComp(self, node):
            self.visit(node.elt)
            for gen in node.generators:
                self.visit(gen.iter)
                for condition in gen.ifs:
                    self.visit(condition)

        def visit_SetComp(self, node):
            self.visit_ListComp(node)

        def visit_GeneratorExp(self, node):
            self.visit_ListComp(node)

        def visit_DictComp(self, node):
            self.visit(node.key)
            self.visit(node.value)
            for gen in node.generators:
                self.visit(gen.iter)
                for condition in gen.ifs:
                    self.visit(condition)

    visitor = Visitor()
    for statement in module.body:
        visitor.visit(statement)
    return {name: tuple(sorted(lines)) for name, lines in visitor.lines.items()}


def _independent_change_lines(external_functions, canonical_tree, baseline, changes,
                              original_source):
    """Locate proven edits in original source without inventing fuzzy matching.

    Compiler mappings identify the generated assignment of each graph node.
    Recover its unique assignment target name in the canonical function, and
    match that exact target once in the independently authored function. If
    either side is ambiguous, omit line evidence rather than guess. The main
    AST/compiler proof has already approved the complete candidate.
    """
    canonical_functions={node.name:node for node in canonical_tree.body
                         if isinstance(node,ast.FunctionDef)}
    node_lines=dict(baseline.node_lines)
    source_lines=original_source.splitlines()
    evidence=[]
    spans=[]
    # One read-only index per selected function, rather than repeated AST walks
    # for every changed graph node. Unknown or duplicate targets are omitted.
    indices={}
    for name,authored in external_functions.items():
        canonical=canonical_functions.get(name)
        if canonical is None:
            continue
        # Build the entire read-only function evidence index in one AST walk
        # per owner. Previously we separately walked assignments, conditions,
        # loops and returns, repeating work and inviting mapping drift.
        generated={}
        occurrences={}
        originals={}
        canonical_conditions=[]
        authored_conditions=[]
        canonical_loops=[]
        authored_loops=[]
        canonical_returns=[]
        authored_returns=[]
        for item in ast.walk(canonical):
            if (isinstance(item,ast.Assign) and len(item.targets)==1
                    and isinstance(item.targets[0],ast.Name)):
                target=item.targets[0].id
                ordinal=occurrences.get(target,0)
                occurrences[target]=ordinal+1
                generated.setdefault(item.lineno,[]).append((target,ordinal))
            elif isinstance(item,ast.If):
                canonical_conditions.append(item)
            elif isinstance(item,ast.For):
                canonical_loops.append(item)
            elif isinstance(item,ast.Return):
                canonical_returns.append(item)
        for item in ast.walk(authored):
            if ((isinstance(item,ast.Assign) and len(item.targets)==1
                     and isinstance(item.targets[0],ast.Name)) or
                    (isinstance(item,ast.AnnAssign) and item.simple==1
                     and item.value is not None and isinstance(item.target,ast.Name))):
                target=(item.targets[0].id if isinstance(item,ast.Assign)
                        else item.target.id)
                originals.setdefault(target,[]).append(item)
            elif isinstance(item,ast.If):
                authored_conditions.append(item)
            elif isinstance(item,ast.For):
                authored_loops.append(item)
            elif isinstance(item,ast.Return):
                authored_returns.append(item)
        # Branch/Require, Repeat and Return are not all represented by
        # assignments. Pair source-owned statement witnesses only when the
        # structurally qualified function has an equal count in that family.
        conditions={}
        if len(canonical_conditions)==len(authored_conditions):
            for original,current in zip(canonical_conditions,authored_conditions):
                conditions.setdefault(original.lineno,[]).append(current)
        loops={}
        if len(canonical_loops)==len(authored_loops):
            for original,current in zip(canonical_loops,authored_loops):
                loops.setdefault(original.lineno,[]).append(current)
        returns={}
        if len(canonical_returns)==len(authored_returns):
            for original,current in zip(canonical_returns,authored_returns):
                returns.setdefault(original.lineno,[]).append(current)
        indices[name]=(generated,originals,conditions,loops,occurrences,returns)

    def text_column(line, byte_offset):
        # CPython AST columns are UTF-8 *bytes*, whereas editor columns are
        # Unicode codepoints. Return a 1-based column, end exclusive.
        if line < 1 or line > len(source_lines):
            return None
        try:
            return len(source_lines[line-1].encode('utf-8')[:byte_offset].decode('utf-8'))+1
        except UnicodeError:
            return None

    def precise_input_span(statement, port):
        """Report only the existing receiving expression, never a whole write.

        This remains advisory after the trial compiler has approved the edit.
        Unknown syntax/port combinations deliberately have no source span.
        """
        if isinstance(statement, ast.Return) and port=='value':
            return statement.value
        if not isinstance(statement,(ast.Assign,ast.AnnAssign)):
            return None
        expression=statement.value
        if expression is None:
            return None
        if port=='value':
            if isinstance(expression,ast.UnaryOp) and isinstance(expression.op,ast.Not):
                return expression.operand
            return expression
        if isinstance(expression,ast.BinOp):
            return {'left':expression.left,'right':expression.right}.get(port)
        if isinstance(expression,ast.Compare) and len(expression.ops)==len(expression.comparators)==1:
            return {'left':expression.left,'right':expression.comparators[0]}.get(port)
        if isinstance(expression,ast.IfExp):
            return {'condition':expression.test, 'true_value':expression.body,
                    'false_value':expression.orelse}.get(port)
        if isinstance(expression,ast.Call) and isinstance(expression.func,ast.Name):
            callee=canonical_functions.get(expression.func.id)
            if callee is None:
                return None
            parameters=[arg.arg for arg in callee.args.args]
            if port not in parameters or len(expression.args)+len(expression.keywords)!=len(parameters):
                return None
            position=parameters.index(port)
            if position<len(expression.args):
                return expression.args[position]
            if any(keyword.arg is None for keyword in expression.keywords):
                return None
            matches=[keyword.value for keyword in expression.keywords if keyword.arg==port]
            return matches[0] if len(matches)==1 else None
        return None

    for change in changes:
        owned=indices.get(change.function)
        line=node_lines.get(change.node_id)
        if owned is None or line is None:
            continue
        generated,originals,conditions,loops,occurrences,returns=owned
        if change.action=='replace_input' and change.input_port=='count':
            matches=loops.get(line,())
            if len(matches)!=1:
                continue
            loop=matches[0]
            if (not isinstance(loop.iter,ast.Call) or
                    not isinstance(loop.iter.func,ast.Name) or loop.iter.func.id!='range' or
                    len(loop.iter.args)!=1 or not isinstance(loop.iter.args[0],ast.Name)):
                continue
            assignments=originals.get(loop.iter.args[0].id,())
            if len(assignments)!=1 or assignments[0].lineno>=loop.lineno:
                continue
            node=assignments[0].value
        elif change.action=='replace_input' and change.input_port=='condition' and line in conditions:
            # Return only the condition expression span, never the complete
            # executable branch/raise body. If the If identity is ambiguous,
            # omit advisory evidence rather than point at an unrelated line.
            choices=conditions.get(line,())
            if len(choices)!=1:
                continue
            conditional=choices[0]
            node=(conditional.test.operand if isinstance(conditional.test,ast.UnaryOp)
                  and isinstance(conditional.test.op,ast.Not) else conditional.test)
        else:
            if change.action=='replace_input' and change.input_port=='value' and line in returns:
                # Pure and structured Return nodes have no generated target.
                # Their existing source-line receipts and positional Return
                # pairing are checked by the complete compiler proof.
                choices=returns[line]
                if len(choices)!=1 or choices[0].value is None:
                    continue
                node=choices[0].value
            else:
                targets=generated.get(line,())
                if len(targets)!=1:
                    continue
                target, ordinal=targets[0]
                matches=originals.get(target,())
                # Mutable slots intentionally reuse one generated target across
                # ordered writes. Occurrence counts are *per function*.
                if len(matches)!=occurrences.get(target,0) or ordinal>=len(matches):
                    continue
                node=matches[ordinal]
                if change.action=='replace_input':
                    node=precise_input_span(node,change.input_port)
                    if node is None:
                        continue
                elif change.action in ('set_property','replace_node_operation'):
                    # These edits belong to the RHS expression, not the
                    # generated assignment target. The exact operator token
                    # has no Python AST location, so select its expression.
                    node=node.value
        evidence.append((change.function,change.node_id,node.lineno))
        end_line=getattr(node,'end_lineno',None)
        end_offset=getattr(node,'end_col_offset',None)
        if end_line is None or end_offset is None:
            continue
        start_col=text_column(node.lineno,node.col_offset)
        end_col=text_column(end_line,end_offset)
        if start_col is not None and end_col is not None:
            spans.append((change.function,change.node_id,node.lineno,start_col,
                          end_line,end_col))
    return tuple(evidence),tuple(spans)

def _function_parameter_names(arguments: ast.arguments) -> set[str]:
    names = {arg.arg for arg in (*arguments.posonlyargs, *arguments.args,
                                 *arguments.kwonlyargs)}
    if arguments.vararg:
        names.add(arguments.vararg.arg)
    if arguments.kwarg:
        names.add(arguments.kwarg.arg)
    return names


class _IndependentCandidateSyntax(ast.NodeTransformer):
    """Normalize a temporary source AST for existing compiler proof only.

    This never modifies SourceDocumentSession text or produces graph edits.
    The whole-graph trial compiler remains the acceptance authority.
    """

    def __init__(self, bound_locals: set[str]):
        self.bound_locals = bound_locals

    def strip_noops(self, statements):
        kept=[]
        for item in statements:
            if isinstance(item,ast.Pass):
                continue
            normalized=self.visit(item)
            if normalized is not None:
                kept.append(normalized)
        # Never erase an entire control suite as an incidental side
        # effect of stripping no-ops. Its structure remains subject
        # to the authoritative compiler proof.
        return kept if kept else statements

    def visit_If(self, statement):
        statement.test=self.visit(statement.test)
        # An if whose condition is a *proven* Boolean constant and
        # whose only bodies are pass has no observable effect. Do not
        # generalize this to truthy integers or dynamic conditions:
        # those could evaluate arbitrary user code.
        if (isinstance(statement.test,ast.Constant) and
                type(statement.test.value) is bool and
                all(isinstance(item,ast.Pass) for item in statement.body) and
                all(isinstance(item,ast.Pass) for item in statement.orelse)):
            return None
        statement.body=self.strip_noops(statement.body)
        statement.orelse=self.strip_noops(statement.orelse)
        return statement

    def visit_For(self, statement):
        statement.target=self.visit(statement.target)
        statement.iter=self.visit(statement.iter)
        statement.body=self.strip_noops(statement.body)
        statement.orelse=self.strip_noops(statement.orelse)
        return statement

    def visit_While(self, statement):
        statement.test=self.visit(statement.test)
        statement.body=self.strip_noops(statement.body)
        statement.orelse=self.strip_noops(statement.orelse)
        return statement

    # Source-only constant expressions can describe existing graph
    # literals without taking ownership of their authored spelling.
    # Fold only exact bounded integer arithmetic/comparisons and
    # fixed Boolean expressions in this temporary proof candidate:
    # no eval(), calls, powers, shifts, float or bool/int coercion.
    # The complete compiler still has to reproduce the result.
    def visit_Compare(self, expression):
        self.generic_visit(expression)
        if len(expression.ops)!=1 or len(expression.comparators)!=1:
            return expression
        right=expression.comparators[0]
        left=expression.left
        if (not isinstance(left,ast.Constant) or
                not isinstance(right,ast.Constant) or
                type(left.value) is not int or type(right.value) is not int or
                abs(left.value)>2**63-1 or abs(right.value)>2**63-1):
            return expression
        a,b=left.value,right.value
        operation=expression.ops[0]
        if isinstance(operation,ast.Lt): result=a<b
        elif isinstance(operation,ast.LtE): result=a<=b
        elif isinstance(operation,ast.Gt): result=a>b
        elif isinstance(operation,ast.GtE): result=a>=b
        elif isinstance(operation,ast.Eq): result=a==b
        elif isinstance(operation,ast.NotEq): result=a!=b
        else: return expression
        return ast.copy_location(ast.Constant(value=result),expression)

    def visit_BoolOp(self, expression):
        self.generic_visit(expression)
        if not all(isinstance(value,ast.Constant) and
                   type(value.value) is bool for value in expression.values):
            return expression
        if isinstance(expression.op,ast.And):
            result=all(value.value for value in expression.values)
        elif isinstance(expression.op,ast.Or):
            result=any(value.value for value in expression.values)
        else:
            return expression
        return ast.copy_location(ast.Constant(value=result),expression)

    def visit_UnaryOp(self, expression):
        self.generic_visit(expression)
        operand=expression.operand
        if (isinstance(expression.op,ast.Not) and
                isinstance(operand,ast.Constant) and type(operand.value) is bool):
            return ast.copy_location(ast.Constant(value=not operand.value),expression)
        if (isinstance(expression.op,(ast.UAdd,ast.USub)) and
                isinstance(operand,ast.Constant) and
                type(operand.value) is int and abs(operand.value)<=2**63-1):
            number=(operand.value if isinstance(expression.op,ast.UAdd)
                    else -operand.value)
            if abs(number)<=2**63-1:
                return ast.copy_location(ast.Constant(value=number),expression)
        return expression

    def visit_BinOp(self, expression):
        self.generic_visit(expression)
        left,right=expression.left,expression.right
        if (not isinstance(left,ast.Constant) or
                not isinstance(right,ast.Constant) or
                type(left.value) is not int or type(right.value) is not int or
                abs(left.value)>2**63-1 or abs(right.value)>2**63-1):
            return expression
        a,b=left.value,right.value
        operation=expression.op
        if isinstance(operation,ast.Add):
            result=a+b
        elif isinstance(operation,ast.Sub):
            result=a-b
        elif isinstance(operation,ast.Mult):
            result=a*b
        elif isinstance(operation,ast.FloorDiv) and b!=0:
            result=a//b
        elif isinstance(operation,ast.Mod) and b!=0:
            result=a%b
        else:
            return expression
        if abs(result)>2**63-1:
            return expression
        return ast.copy_location(ast.Constant(value=result),expression)

    def visit_IfExp(self, expression):
        # An authored conditional *expression* is source-only spelling
        # for a literal only when the condition and BOTH alternatives
        # are already proven fixed literals of the same exact type.
        # Never evaluate or discard an unknown/effectful branch, even
        # if Python would short-circuit it at runtime.
        self.generic_visit(expression)
        test,yes,no=expression.test,expression.body,expression.orelse
        if not all(isinstance(item,ast.Constant) for item in (test,yes,no)):
            return expression
        if type(test.value) is not bool or type(yes.value) is not type(no.value):
            return expression
        chosen=yes.value if test.value else no.value
        if type(chosen) is int:
            if any(type(item.value) is not int or abs(item.value)>2**63-1
                   for item in (yes,no)):
                return expression
        elif type(chosen) is not bool:
            return expression
        return ast.copy_location(ast.Constant(value=chosen),expression)

    def visit_AnnAssign(self, statement):
        if (isinstance(statement.target,ast.Name) and statement.simple==1
            and isinstance(statement.annotation,ast.Name) and
            statement.annotation.id in ('int','bool','str')):
            if statement.value is not None:
                return ast.copy_location(ast.Assign(
                    targets=[statement.target],value=self.visit(statement.value),
                    type_comment=None),statement)
            if statement.target.id in self.bound_locals:
                return None
        return statement


def _pure_expression_witness(expression: ast.AST, rename: dict[str,str],
                             unknown: set[str]) -> str | None:
    """Exact pure AST witness; never infer a producer from unresolved names."""
    if not _pure_reorderable_value(expression):
        return None

    class CanonicalNames(ast.NodeTransformer):
        def visit_Name(self, node):
            if node.id in unknown:
                raise ValueError('Unresolved source value')
            if node.id in rename:
                node.id=rename[node.id]
            return node

    try:
        normalized=CanonicalNames().visit(copy.deepcopy(expression))
    except ValueError:
        return None
    return ast.dump(normalized,include_attributes=False)


def _independent_local_correspondence(owned: ast.FunctionDef, reference: ast.FunctionDef,
                                      parameter_names: set[str], source_functions: dict) -> ast.FunctionDef:
    """Rename only compiler-proven generated bindings on an ephemeral function AST.

    Never creates a source map or mutates SourceDocumentSession. A name inferred
    here is only a candidate for the unchanged full-graph compiler proof.
    """
    from collections import Counter
    generated=[item for item in ast.walk(reference)
               if isinstance(item,ast.Assign) and len(item.targets)==1
               and isinstance(item.targets[0],ast.Name)]
    authored=[item for item in ast.walk(owned)
              if isinstance(item,ast.Assign) and len(item.targets)==1
              and isinstance(item.targets[0],ast.Name)]
    if len(generated)==len(authored):
        old_names=[item.targets[0].id for item in generated]
        new_names=[item.targets[0].id for item in authored]
        old_counts=Counter(old_names)
        new_counts=Counter(new_names)
        old_set=set(old_names)
        new_set=set(new_names)
        param_names=parameter_names
        aliases={}
        valid=True
        # A uniquely identified renamed temporary may move within a pure
        # execution suite. Multiple renamed values need independent
        # structural witnesses; position alone is not evidence after
        # a reorder. Infer those witnesses iteratively (dependencies first)
        # and reject any ambiguity. This only normalizes a *candidate*;
        # the full graph compiler remains the import authority.
        missing=[original for original in old_names if original not in new_set]
        introduced=[current for current in new_names if current not in old_set]
        pairs=[]
        if len(missing)==len(introduced)==1:
            pairs=[(missing[0],introduced[0])]
        elif len(missing)==len(introduced)>1:
            unresolved_old=set(missing)
            unresolved_new=set(introduced)
            known={}
            old_defs={item.targets[0].id:item.value for item in generated
                      if old_counts[item.targets[0].id]==1}
            new_defs={item.targets[0].id:item.value for item in authored
                      if new_counts[item.targets[0].id]==1}
            # Match only uniquely shared pure expression ASTs after any
            # independently proven input aliases have been resolved.
            # Never try to infer producer identity from ambiguous shapes.
            while unresolved_old and unresolved_new:
                old_keys={name:_pure_expression_witness(old_defs[name],{},set()) for name in unresolved_old
                          if name in old_defs}
                new_keys={name:_pure_expression_witness(new_defs[name],known,unresolved_new) for name in unresolved_new
                          if name in new_defs}
                candidates=[]
                for original,old_key in old_keys.items():
                    if old_key is None:continue
                    compatible=[current for current,value in new_keys.items()
                                if value is not None and value==old_key]
                    reverse=[name for name,value in old_keys.items() if value==old_key]
                    if len(compatible)==len(reverse)==1:
                        candidates.append((original,compatible[0]))
                if not candidates:
                    break
                for original,current in candidates:
                    pairs.append((original,current))
                    known[current]=original
                    unresolved_old.discard(original)
                    unresolved_new.discard(current)
            valid=not unresolved_old and not unresolved_new
        else:
            # A positional mapping remains acceptable only for a pure
            # rename with unchanged surviving generated-value order.
            stable_old=[name for name in old_names if name in new_set]
            stable_new=[name for name in new_names if name in old_set]
            valid=stable_old==stable_new
            pairs=[(original,current) for original,current in zip(old_names,new_names)
                   if original != current] if valid else []
        for original,current in pairs:
            if (not original.startswith('_smi_value_') or
                    not original[len('_smi_value_'):].isdigit() or
                    current.startswith('_smi_') or current in old_set or
                    current in param_names or current in source_functions or
                    old_counts[original]!=1 or new_counts[current]!=1 or
                    original in aliases or current in aliases.values()):
                valid=False
                break
            aliases[current]=original
        if aliases and valid:
            # Refuse scope-sensitive syntax rather than rename through a
            # closure, comprehension, global/nonlocal, or deletion. Those
            # constructs are outside this bounded identity proof.
            forbidden=(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef,
                       ast.Lambda,ast.ListComp,ast.SetComp,ast.DictComp,
                       ast.GeneratorExp,ast.Global,ast.Nonlocal,
                       ast.Delete,ast.NamedExpr)
            if not any(isinstance(item,forbidden) for statement in owned.body
                       for item in ast.walk(statement)):
                # An old generated binding left in the source after its
                # declaration was renamed would be unbound or ambiguous.
                removed={old for new,old in aliases.items()}
                if not any(isinstance(item,ast.Name) and item.id in removed
                           for statement in owned.body for item in ast.walk(statement)):
                    class CanonicalLocals(ast.NodeTransformer):
                        def visit_Name(self, item):
                            if item.id in aliases:
                                item.id=aliases[item.id]
                            return item
                    owned=CanonicalLocals().visit(owned)

    return owned


def _independent_keyword_calls(owned: ast.FunctionDef, keyword_parameters: dict) -> ast.FunctionDef:
    """Use graph-owned parameter signatures to canonicalize local-name keyword calls.

    Unsupported, reordered or effectful operands are left unchanged so that
    the single full-graph trial compiler can reject them without guessing.
    """
    class CanonicalCalls(ast.NodeTransformer):
        def visit_Call(self, call):
            self.generic_visit(call)
            if not isinstance(call.func,ast.Name) or not call.keywords:
                return call
            parameters=keyword_parameters.get(call.func.id)
            if parameters is None or len(call.args)+len(call.keywords)!=len(parameters):
                return call
            if (any(not isinstance(arg,ast.Name) for arg in call.args) or
                    any(keyword.arg is None or not isinstance(keyword.value,ast.Name)
                        for keyword in call.keywords)):
                return call
            # Explicit positional arguments must be a prefix. Every
            # remaining parameter must appear once by exact name.
            names=[keyword.arg for keyword in call.keywords]
            remaining=parameters[len(call.args):]
            if len(names)!=len(set(names)) or set(names)!=set(remaining):
                return call
            by_name={keyword.arg:keyword.value for keyword in call.keywords}
            call.args.extend(by_name[param] for param in remaining)
            call.keywords=[]
            return call

    return CanonicalCalls().visit(owned)


def _independent_proof_function(source: ast.FunctionDef, reference: ast.FunctionDef,
                                keyword_parameters: dict, source_functions: dict,
                                name: str) -> ast.FunctionDef:
    """Build one temporary proof candidate without changing the source AST."""
    from .program_graph import ProgramGraphError
    owned=copy.deepcopy(source)
    # A function docstring and direct-body `pass` are source-owned trivia.
    # They are never published to the graph or removed from the actual
    # source buffer. Only the ephemeral compiler candidate omits them.
    # A string expression in any other position remains substantive AST
    # and is refused by the complete compiler proof.
    if (owned.body and isinstance(owned.body[0], ast.Expr) and
            isinstance(owned.body[0].value, ast.Constant) and
            isinstance(owned.body[0].value.value, str)):
        owned.body.pop(0)
    # Normalize source-only, non-executing syntax solely in the ephemeral
    # compiler candidate. Local Name annotations are not evaluated by
    # Python in function bodies, but do not generalize this to attribute
    # annotations, subscript targets, arbitrary annotation expressions or
    # empty control suites. The graph proof still must reproduce the
    # *entire* remaining function exactly.
    # A bare local annotation has no runtime value, but it can still
    # declare a Python-local name. Ignore it only for a binding already
    # owned by this selected function, never for a new source-only local.
    # Compile proof will reject any unsupported binding and preserve the
    # authored annotation in SourceDocumentSession.
    parameter_names=_function_parameter_names(owned.args)
    bound_locals=set(parameter_names)
    for statement in ast.walk(owned):
        if isinstance(statement,ast.Assign):
            bound_locals.update(target.id for target in statement.targets
                                if isinstance(target,ast.Name))
        elif isinstance(statement,ast.For) and isinstance(statement.target,ast.Name):
            bound_locals.add(statement.target.id)

    # Bound the transient source-owned syntax before walking it multiple
    # times for normalization, local correspondence and trial proof. This
    # is independent of the 256-node executable graph size limit.
    if sum(1 for _ in ast.walk(owned)) > MAX_INDEPENDENT_AST_NODES:
        raise ProgramGraphError(
            f'Function {name!r}: independently authored AST exceeds '
            f'{MAX_INDEPENDENT_AST_NODES} nodes; reconciliation refused')
    normalizer=_IndependentCandidateSyntax(bound_locals)
    owned.body=normalizer.strip_noops(owned.body)

    # Readable source locals are normalized only when their graph-owned
    # assignments have unique positional or pure-expression witnesses.
    # Repeated targets, speculative scope moves, and parameter renames
    # are never admitted. Full compiler re-lowering proves every edit.
    # The subsequent full graph re-lowering must still reproduce every
    # operation and connection. This is a transient alpha-renaming proof,
    # not a source map, graph command or persistent binding.
    owned=_independent_local_correspondence(owned,reference,parameter_names,source_functions)
    return _independent_keyword_calls(owned,keyword_parameters)


def _top_level_function_index(module, *, include_async):
    index = {}
    kinds = ((ast.FunctionDef, ast.AsyncFunctionDef) if include_async
             else (ast.FunctionDef,))
    for node in module.body:
        if isinstance(node, kinds):
            index.setdefault(node.name, []).append(node)
    return index


def _independent_keyword_parameter_contract(module: ast.Module, selected: dict,
                                            source_functions: dict,
                                            owned_functions: dict) -> dict:
    """Preflight keyword-call signatures and exact module binding identity.

    This inspects the *current* source module once, not its generated trial or
    a workspace index. A rejected selected function always fails before any
    graph edit; an unqualified callee stays unnormalized for compiler refusal.
    The returned parameter names are transient proof data, not bindings stored
    on a document or graph.
    """
    from .program_graph import ProgramGraphError
    # Keyword calls in independently authored functions can name existing
    # graph-owned parameters without changing the callable or graph identity.
    # Qualify any additional target *against this source module* before
    # temporarily converting its keyword names to canonical positional args.
    # A non-selected target must be byte-independent AST-equivalent to the
    # graph-owned function. Selected targets still require the full trial proof.
    keyword_targets={call.func.id for function in selected.values()
        for call in ast.walk(function) if isinstance(call,ast.Call)
        and isinstance(call.func,ast.Name) and call.keywords}
    candidate_callees={}
    for name in keyword_targets:
        source=source_functions.get(name,())
        owned=owned_functions.get(name,())
        if len(source)!=1 or len(owned)!=1 or not isinstance(source[0],ast.FunctionDef):
            continue
        if name not in selected and ast.dump(source[0],include_attributes=False) != \
                ast.dump(owned[0],include_attributes=False):
            continue
        if (source[0].decorator_list or source[0].args.posonlyargs or
                source[0].args.kwonlyargs or source[0].args.vararg or
                source[0].args.kwarg or source[0].args.defaults or
                any(default is not None for default in source[0].args.kw_defaults)):
            continue
        candidate_callees[name]=source[0]
    # The source AST is shared by the entire selection. One module binding
    # traversal checks all identities (including keyword-call targets) rather
    # than re-walking it for each chosen function.
    conflicts_by_name=_module_function_binding_conflicts(
        module,{**candidate_callees,**selected})
    for name in selected:
        conflicts=conflicts_by_name[name]
        if conflicts:
            raise ProgramGraphError(
                f'Function {name!r} (source line {selected[name].lineno}): '
                'module-scope binding shadows selected function at line(s) '+
                ', '.join(map(str,conflicts))+ '; reconciliation refused')
    # A keyword call is source-owned syntax, not a new graph operation. Only
    # existing, unshadowed graph functions with exact signatures qualify; all
    # explicit operands must be pure local-name reads. No keyword unpacking,
    # starred arguments, defaults, or expression evaluation reordering.
    keyword_parameters={name:tuple(arg.arg for arg in fn.args.args)
        for name,fn in candidate_callees.items() if not conflicts_by_name[name]}
    return keyword_parameters


def _assert_independent_source_snapshot(session, revision: int, source_text: str,
                                        saved_raw: bytes, *, stage: str) -> None:
    """Check one existing source owner before AND after external disk inspection.

    A source save can change saved_raw without advancing the editor revision.
    The preflight and commit receipt must therefore cover revision, live text
    and the exact saved-byte baseline. This is a read-only qualification gate,
    not another document snapshot owner or writer.
    """
    from .program_graph import GraphConflict

    def check_owner():
        if session.revision != revision or session.text != source_text:
            raise GraphConflict('Source revision changed ' + stage)
        if session.saved_raw != saved_raw:
            raise GraphConflict('Source saved baseline changed ' + stage)

    check_owner()
    if session.inspect_external() != 'current':
        raise GraphConflict('Source changed on disk ' + stage)
    check_owner()


def _independent_functions_plan(graph, session, functions, *, expected_graph_revision: int):
    """Qualify named independent regions with the existing whole-graph compiler.

    Unselected functions remain the graph-generated baseline for proof. All
    other source statements are opaque and source-owned. No implicit matching,
    filesystem writes, or new mutable model is involved.
    """
    import hashlib
    from .program_graph import ProgramGraph, ProgramGraphError, GraphConflict
    from .source_editor import SourceDocumentSession
    if not isinstance(graph, ProgramGraph) or not isinstance(session, SourceDocumentSession):
        raise TypeError('Function review requires ProgramGraph and SourceDocumentSession owners')
    if type(expected_graph_revision) is not int or graph.revision != expected_graph_revision:
        raise GraphConflict('Graph revision changed before function review')
    if (not isinstance(functions, (list, tuple)) or not 1 <= len(functions) <= 32 or
            any(not isinstance(name, str) or not name.isidentifier() for name in functions) or
            len(set(functions)) != len(functions)):
        raise ProgramGraphError('Select 1 to 32 distinct named top-level functions')
    names=tuple(functions)
    # Keep one authoritative source-owner snapshot for the whole compiler
    # proof. Never mix AST, source spans and hash from different revisions.
    source_revision=session.revision
    source_text=session.text
    source_saved_raw=session.saved_raw
    _assert_independent_source_snapshot(
        session,source_revision,source_text,source_saved_raw,
        stage='before independent function review')

    def assert_proof_owners():
        """One source/disk/graph gate shared by result and error attribution."""
        if graph.revision != expected_graph_revision:
            raise GraphConflict('Graph revision changed during independent function review')
        _assert_independent_source_snapshot(
            session,source_revision,source_text,source_saved_raw,
            stage='during independent function review')

    try:
        raw=source_text.encode('utf-8')
    except UnicodeError as exc:
        raise ProgramGraphError('Independent Python source cannot be encoded as UTF-8') from exc
    if len(raw) > MAX_PREVIEW_BYTES:
        raise ProgramGraphError('Independent Python review exceeds compiler size limit')
    # Previewing a graph-owned source can invoke a reentrant host callback.
    # Do not attribute a rejection to an AST/graph from a stale preimage.
    try:
        baseline=preview_python(graph.state)
    except ProgramGraphError:
        assert_proof_owners()
        raise
    assert_proof_owners()
    if baseline.source is None:
        raise ProgramGraphError('Graph is not qualified for Python: '+'; '.join(baseline.issues))
    try:
        external=ast.parse(source_text)
        canonical=ast.parse(baseline.source)
    except SyntaxError as exc:
        # A failed parse has no safe function-region mapping. Report the
        # *source owner's* location rather than guessing an AST function.
        raise ProgramGraphError(
            f'Independent Python source syntax at line {exc.lineno}, '
            f'column {exc.offset}: {exc.msg}') from exc
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ProgramGraphError('Independent Python source must parse before function review') from exc
    # One bounded per-batch index of the actual source and the compiler baseline.
    # Neither index becomes a persistent source map or runtime dependency scan.
    source_functions = _top_level_function_index(external, include_async=True)
    owned_functions = _top_level_function_index(canonical, include_async=False)
    selected={}
    for name in names:
        found=source_functions.get(name, ())
        owned=owned_functions.get(name, ())
        if len(found) != 1 or len(owned) != 1:
            # Exact-name identity only: report what the source owner actually
            # contains, without guessing a rename or binding a similarly
            # shaped function to a different graph identity.
            if len(found) > 1:
                detail='duplicate source definitions at lines '+', '.join(
                    str(item.lineno) for item in found)
            elif not found:
                available=list(source_functions)
                detail='no matching source definition; top-level functions: '+(
                    ', '.join(repr(item) for item in available[:12]) or '(none)')
                if len(available)>12:
                    detail+=f' (+{len(available)-12} more)'
            else:
                detail='no unique matching graph-owned function'
            raise ProgramGraphError(
                f'Function {name!r} must occur exactly once in source and graph baseline: {detail}')
        if not isinstance(found[0], ast.FunctionDef):
            raise ProgramGraphError(f'Async function {name!r} is not qualified by the graph compiler')
        if found[0].decorator_list or getattr(found[0], 'type_params', ()):
            raise ProgramGraphError(f'Decorated or generic function {name!r} is not qualified')
        # Function names are explicit identities, not fuzzy matches. Fail at
        # the actual source owner's signature before trying to interpret its
        # body against a synthetic full-file graph baseline. The trial compiler
        # still supplies the authoritative proof for every admitted edit.
        if (ast.dump(found[0].args,include_attributes=False) !=
                ast.dump(owned[0].args,include_attributes=False) or
                (ast.dump(found[0].returns,include_attributes=False)
                 if found[0].returns is not None else None) !=
                (ast.dump(owned[0].returns,include_attributes=False)
                 if owned[0].returns is not None else None)):
            raise ProgramGraphError(
                f'Function {name!r} (source line {found[0].lineno}): '
                'signature differs from graph-owned function; rename, parameters, '
                'defaults, annotations and return contract are not imported')
        selected[name]=found[0]
    # Existing graph-owned callee signature and module-scope shadow preflight.
    # The helper uses this exact source AST and the indexed graph baseline.
    try:
        keyword_parameters = _independent_keyword_parameter_contract(
            external, selected, source_functions, owned_functions)

        # Replace only explicitly selected functions in the synthetic trial.
        # The source owner retains its original AST and exact text evidence.
        proved={name:_independent_proof_function(
            selected[name],owned_functions[name][0],keyword_parameters,source_functions,name)
            for name in names}
    except ProgramGraphError:
        # An owner change during keyword admission or transient syntax proof
        # takes precedence over the error of an obsolete source revision.
        assert_proof_owners()
        raise
    assert_proof_owners()
    candidate=ast.Module(body=[proved.get(node.name,node) if isinstance(node,ast.FunctionDef)
                               else node for node in canonical.body],type_ignores=[])
    rendered=ast.unparse(candidate)+'\n'
    try:
        review,commands=_qualified_source_edit_plan(graph,baseline.source,rendered,
            expected_revision=expected_graph_revision,allow_source_trivia=True,
            allow_pure_reordering=True, _baseline_preview=baseline,
            _baseline_tree=canonical)
    except ProgramGraphError as exc:
        # Reentrant source or graph edits outrank stale compiler diagnostics.
        # The same gate will also protect every trial region attribution.
        assert_proof_owners()
        # A failed multi-region proof must name the offending source region.
        # Isolate each selected function against the same canonical baseline;
        # this diagnostic reuses the compiler rather than independently
        # interpreting Python or approving any subset of an invalid batch.
        for name in names:
            # Compare the *proved* transient candidate with the already
            # indexed graph baseline. Authored docstrings, pass, annotations,
            # aliases and keywords may differ while the normalized function
            # is identical; retrying those regions cannot explain the batch
            # refusal. Leave the original source AST for evidence locations.
            if ast.dump(proved[name], include_attributes=False) == ast.dump(
                    owned_functions[name][0], include_attributes=False):
                continue
            only_one=ast.Module(body=[proved[name] if isinstance(node,ast.FunctionDef)
                and node.name==name else node for node in canonical.body],type_ignores=[])
            try:
                _qualified_source_edit_plan(graph,baseline.source,ast.unparse(only_one)+'\n',
                    expected_revision=expected_graph_revision,allow_source_trivia=True,
                    allow_pure_reordering=True, _baseline_preview=baseline,
                    _baseline_tree=canonical)
            except ProgramGraphError as region_error:
                assert_proof_owners()
                region=selected[name]
                raise ProgramGraphError(
                    f'Function {name!r} (source lines {region.lineno}-{region.end_lineno}): '
                    f'{region_error}') from exc
        # In the unlikely case that each individual region is valid but their
        # combination is not, retain the complete batch refusal intact.
        assert_proof_owners()
        raise ProgramGraphError('Combined function review refused: '+str(exc)) from exc
    if any(change.function not in selected for change in review.changes):
        raise ProgramGraphError('Proposed edits escaped the selected functions')
    # The compiler is synchronous, but a review and its advisory evidence
    # must be bound to the same original owners after any reentrant callback.
    assert_proof_owners()
    lines,spans=_independent_change_lines(selected,canonical,baseline,review.changes,
                                         source_text)
    receipt=IndependentFunctionsReview(expected_graph_revision,source_revision,
        hashlib.sha256(raw).hexdigest(),names,
        tuple((name,selected[name].lineno,selected[name].end_lineno) for name in names),
        review.changes,len(external.body)-len(names),lines,spans)
    # Span/line evidence is derived after proof; its receipt cannot inherit a
    # source, disk or graph revision observed later than the compiler witness.
    assert_proof_owners()
    return receipt,commands


def _independent_function_plan(graph, session, function: str, *, expected_graph_revision: int):
    """Compatibility interface to the shared one-or-many function proof."""
    receipt,commands=_independent_functions_plan(graph,session,(function,),
        expected_graph_revision=expected_graph_revision)
    _,first,last=receipt.regions[0]
    return IndependentFunctionReview(receipt.graph_revision,receipt.source_revision,
        receipt.source_sha256,function,first,last,receipt.changes,
        receipt.unmodeled_top_level,receipt.change_lines,receipt.change_spans),commands


def review_independent_source_functions(graph, session, functions, *,
                                        expected_graph_revision: int) -> IndependentFunctionsReview:
    """Read-only preflight of explicitly named regions; never modifies source."""
    receipt,_=_independent_functions_plan(graph,session,functions,
        expected_graph_revision=expected_graph_revision)
    return receipt


def import_independent_source_functions(graph, session, functions, *,
                                        expected_graph_revision: int,
                                        expected_source_revision: int,
                                        expected_source_sha256: str) -> bool:
    """Requalify a multi-function receipt and commit one undoable transaction."""
    import hashlib
    from .program_graph import GraphConflict, ProgramGraphError
    revision,text,saved_raw=session.revision,session.text,session.saved_raw
    try:
        source_hash=hashlib.sha256(text.encode('utf-8')).hexdigest()
    except UnicodeError as exc:
        raise ProgramGraphError('Independent Python source cannot be encoded as UTF-8') from exc
    if (type(expected_source_revision) is not int or
            expected_source_revision != revision or
            not isinstance(expected_source_sha256,str) or
            source_hash!=expected_source_sha256):
        raise GraphConflict('Independent source revision changed after review')
    receipt,commands=_independent_functions_plan(graph,session,functions,
        expected_graph_revision=expected_graph_revision)
    if (receipt.source_revision != expected_source_revision or
            receipt.source_sha256 != expected_source_sha256):
        raise GraphConflict('Independent source changed during qualification')
    # Recheck the exact source owner's saved baseline as well as its text,
    # before and after disk inspection, even when no graph command is needed.
    _assert_independent_source_snapshot(
        session,revision,text,saved_raw,stage='before graph import')
    if graph.revision != receipt.graph_revision:
        raise GraphConflict('Graph revision changed before independent source import')
    return graph.edit_many(receipt.graph_revision,commands) if commands else False


def review_independent_source_function(graph, session, function: str, *,
                                       expected_graph_revision: int) -> IndependentFunctionReview:
    """Read-only review of a supported function in a separately authored .py."""
    receipt,_=_independent_function_plan(graph,session,function,
                                        expected_graph_revision=expected_graph_revision)
    return receipt


def import_independent_source_function(graph, session, function: str, *,
                                       expected_graph_revision: int,
                                       expected_source_revision: int,
                                       expected_source_sha256: str) -> bool:
    """Existing one-function API uses the same bounded batch proof and commit."""
    return import_independent_source_functions(graph,session,(function,),
        expected_graph_revision=expected_graph_revision,
        expected_source_revision=expected_source_revision,
        expected_source_sha256=expected_source_sha256)


@dataclass
class LinkedPythonSource:
    """Explicit reconciliation receipt between existing document owners.

    Neither owner is replaced: SourceDocumentSession keeps the live text and
    recovery history; ProgramGraph keeps graph transactions. A link can only
    begin where both owners contain byte-exact generated Python. It never
    writes either file, executes code, or guesses at unsupported source.
    """
    graph: object
    session: object
    base_source: str
    graph_revision: int
    source_revision: int
    disk_sha256: str
    source_text: str
    graph_fingerprint: str

    @staticmethod
    def _graph_fingerprint(graph):
        import hashlib
        from .program_graph import encode
        # Revision alone advances on undo/redo. Compare every *other* graph
        # field, including layouts, identities, signatures and connections.
        state = graph.state
        return hashlib.sha256(encode({k: v for k, v in state.items()
                                      if k != 'revision'})).hexdigest()

    @classmethod
    def attach(cls, graph, session):
        import hashlib
        from .program_graph import ProgramGraph, GraphConflict
        from .source_editor import SourceDocumentSession
        if not isinstance(graph, ProgramGraph):
            raise TypeError('Python link requires a ProgramGraph')
        if not isinstance(session, SourceDocumentSession):
            raise TypeError('Python link requires a source document session')
        # A pending unsaved source draft has no provable common ancestor at
        # association time. Once linked, unsaved edits are the intended input.
        if session.dirty:
            raise GraphConflict('Link requires a clean Python source document')
        source_revision,source_text,saved_raw=(session.revision,session.text,session.saved_raw)
        graph_revision=graph.revision
        fingerprint=cls._graph_fingerprint(graph)

        def assert_current():
            # One admission preimage, not a second source/graph owner. Source
            # saves can advance saved_raw without advancing editor revision.
            if (session.revision != source_revision or session.text != source_text or
                    session.saved_raw != saved_raw):
                raise GraphConflict('Source changed during Python link admission')
            if graph.revision != graph_revision:
                raise GraphConflict('Graph changed during Python link admission')

        if session.inspect_external() != 'current':
            raise GraphConflict('Source changed on disk; link refused')
        assert_current()
        preview = preview_python(graph.state)
        # Preview generation can invoke a reentrant host callback. Refuse an
        # association based on two different owner revisions, even if the
        # source text from the earlier snapshot happened to match.
        if session.inspect_external() != 'current':
            raise GraphConflict('Source changed on disk during Python link admission')
        assert_current()
        if preview.source is None:
            raise GraphConflict('Cannot link unqualified graph: ' + '; '.join(preview.issues))
        if source_text != preview.source or saved_raw != preview.source.encode('utf-8'):
            raise GraphConflict('Source is not an exact generated-Python baseline for this graph')
        return cls(graph,session,preview.source,graph_revision,source_revision,
                   hashlib.sha256(saved_raw).hexdigest(),source_text,fingerprint)

    def _qualify_receipt(self) -> str:
        """One source+graph conflict gate shared by review and import.

        Read-only wrt the document and ProgramGraph. A normal external source
        save matching the last accepted source is not a conflicting edit.
        """
        import hashlib
        from .program_graph import GraphConflict
        if self.graph.revision != self.graph_revision and (
                self._graph_fingerprint(self.graph) != self.graph_fingerprint):
            raise GraphConflict('Graph changed since source link; relink explicitly')
        if self.session.revision < self.source_revision:
            raise GraphConflict('Source session revision moved backwards')
        if self.session.inspect_external() != 'current':
            raise GraphConflict('Source changed on disk; source draft retained')
        current_disk_hash=hashlib.sha256(self.session.saved_raw).hexdigest()
        if current_disk_hash != self.disk_sha256 and (
                self.session.saved_raw != self.source_text.encode('utf-8') and
                (self.session.dirty or
                 self.session.saved_raw != self.session.text.encode('utf-8'))):
            raise GraphConflict('Source disk baseline changed with unproven draft; relink refused')
        if self.session.revision == self.source_revision and self.session.text != self.source_text:
            raise GraphConflict('Source changed without a document revision')
        return current_disk_hash

    def _assert_current_source(self, revision: int, text: str, saved_raw: bytes) -> str:
        """Revalidate the exact source-owner snapshot after compiler proof.

        The link is not an independent text owner. Both reviews and imports
        refuse if a reentrant editor change or disk write invalidates the
        previously checked source; the existing link gate also verifies graph
        identity. The final source/disk check precedes ProgramGraph.edit_many.
        """
        from .program_graph import GraphConflict
        if (self.session.revision != revision or self.session.text != text or
                self.session.saved_raw != saved_raw):
            raise GraphConflict('Source changed during linked Python qualification')
        current_disk_hash = self._qualify_receipt()
        if (self.session.revision != revision or self.session.text != text or
                self.session.saved_raw != saved_raw):
            raise GraphConflict('Source changed during linked Python qualification')
        return current_disk_hash

    def review_edits(self) -> SourceEditReview:
        """Read-only compiler review of one current source-owner revision."""
        from .program_graph import ProgramGraphError, GraphConflict
        self._qualify_receipt()
        revision, text, saved_raw = (self.session.revision, self.session.text,
                                     self.session.saved_raw)
        try:
            if revision == self.source_revision:
                review = SourceEditReview(self.graph.revision, ())
            else:
                review = review_generated_source_edit(
                    self.graph, self.base_source, text,
                    expected_revision=self.graph.revision, allow_source_trivia=True)
        except (ProgramGraphError, GraphConflict):
            # A concurrent source change takes priority over a stale compiler
            # diagnostic; neither issue may yield a review receipt.
            self._assert_current_source(revision, text, saved_raw)
            raise
        self._assert_current_source(revision, text, saved_raw)
        return review

    def import_edits(self) -> bool:
        """Prove then commit against one source snapshot, or refuse unchanged."""
        from .program_graph import ProgramGraphError, GraphConflict
        self._qualify_receipt()
        revision, text, saved_raw = (self.session.revision, self.session.text,
                                     self.session.saved_raw)
        if revision == self.source_revision:
            self.disk_sha256 = self._assert_current_source(revision, text, saved_raw)
            self.graph_revision = self.graph.revision
            return False
        try:
            # Use exactly the existing generated-source compiler planner.
            # Unlike import_generated_source_edit, it does not commit before
            # we can recheck the live source and the disk preimage.
            review, commands = _qualified_source_edit_plan(
                self.graph, self.base_source, text,
                expected_revision=self.graph.revision, allow_source_trivia=True)
        except (ProgramGraphError, GraphConflict):
            self._assert_current_source(revision, text, saved_raw)
            raise
        current_disk_hash = self._assert_current_source(revision, text, saved_raw)
        changed = self.graph.edit_many(review.graph_revision, commands) if commands else False
        self.graph_revision = self.graph.revision
        self.graph_fingerprint = self._graph_fingerprint(self.graph)
        self.source_revision = revision
        self.base_source = preview_python(self.graph.state).source
        self.source_text = text
        self.disk_sha256 = current_disk_hash
        return changed

@dataclass(frozen=True)
class PythonPublication:
    path: str
    source_sha256: str
    graph_sha256: str
    graph_revision: int
    node_lines: tuple[tuple[str, int], ...]


def publish_python(graph, destination, *, expected_revision: int,
                   expected_target_sha256: str | None = None) -> PythonPublication:
    """Explicitly publish a qualified, saved ProgramGraph as a separate .py.

    Never auto-executes, never mutates the graph, and never silently overwrites
    an existing Python file. Exact existing-file updates require the caller to
    provide a previously observed SHA-256 and use the established source writer
    with its stable lock, preimage checks, and backup.
    """
    import hashlib
    from pathlib import Path
    from .program_graph import ProgramGraph, GraphConflict
    from .python_edit import EditProposal, apply_proposal, create_source_exclusive
    from .python_graph import SourceError
    if not isinstance(graph, ProgramGraph):
        raise TypeError('Publication requires a ProgramGraph owner')
    if type(expected_revision) is not int or graph.revision != expected_revision:
        raise GraphConflict('Stale graph revision; publication refused')
    state, raw_graph = graph.saved_snapshot_for_publication()
    preview=preview_python(state)
    if preview.source is None:
        raise GraphConflict('Python publication refused: ' + '; '.join(preview.issues))
    path=Path(destination).expanduser().absolute()
    if path.suffix != '.py' or path.is_symlink():
        raise SourceError('Publication requires a regular .py destination')
    raw=preview.source.encode('utf-8')
    # Verify the source at the publication boundary, not merely in the UI.
    compile(ast.parse(raw.decode('utf-8')),str(path),'exec')
    if expected_target_sha256 is None:
        published=create_source_exclusive(path,raw)
    else:
        if (not isinstance(expected_target_sha256,str) or len(expected_target_sha256)!=64 or
                any(ch not in '0123456789abcdef' for ch in expected_target_sha256)):
            raise SourceError('Expected target revision must be a lowercase SHA-256 digest')
        if path.is_symlink() or not path.is_file():
            raise SourceError('Existing source is missing or unsafe')
        original=path.read_bytes()
        if hashlib.sha256(original).hexdigest()!=expected_target_sha256:
            raise SourceError('Existing source SHA-256 differs; refusing publication')
        apply_proposal(EditProposal(path,original,raw,'utf-8','Publish qualified ProgramGraph Python'))
        published=path.resolve(strict=True)
    return PythonPublication(str(published),hashlib.sha256(raw).hexdigest(),
                             hashlib.sha256(raw_graph).hexdigest(),state['revision'],preview.node_lines)

def main(argv=None) -> int:
    """Inspect a graph-owned document as Python without saving or executing it."""
    import argparse
    from .program_graph import ProgramGraph, ProgramGraphError
    parser = argparse.ArgumentParser(description='Read-only qualified Python preview of an .smi-graph document')
    parser.add_argument('graph', help='Path to a saved graph-owned program')
    parser.add_argument('--publish', metavar='PATH', help='Explicit output .py path; refuses existing files')
    parser.add_argument('--expected-target-sha256', metavar='SHA256',
                        help='Explicit exact preimage for replacing an existing .py (backup retained)')
    arguments = parser.parse_args(argv)
    try:
        document = ProgramGraph.open(arguments.graph)
        if arguments.expected_target_sha256 and not arguments.publish:
            parser.error('--expected-target-sha256 requires --publish')
        if arguments.publish:
            receipt=publish_python(document,arguments.publish,expected_revision=document.revision,
                           expected_target_sha256=arguments.expected_target_sha256)
            print('PYTHON_PUBLICATION_PASS',receipt.path,receipt.source_sha256)
            return 0
        preview = preview_python(document.state)
    except (OSError, ProgramGraphError, ValueError) as exc:
        parser.exit(2, f'Preview refused: {exc}\n')
    if preview.source is None:
        parser.exit(2, 'Preview refused: ' + '; '.join(preview.issues) + '\n')
    print(preview.source, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
