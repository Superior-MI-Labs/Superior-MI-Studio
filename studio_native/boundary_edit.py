"""Map existing function-boundary anchors to exact source-edit endpoints.

No fabricated ports or source operations. A composite parameter is the same
underlying parameter as its hidden source binding; a terminal return dot is
an alias for exactly one real `return` statement. All actual edits continue
through python_edit.rewire_source_operand() and its guarded diff approval.
"""
from __future__ import annotations
from .semantic_contract import describe_graph, ContractError


class BoundaryEditError(ValueError):
    pass


def parameter_source(graph: dict, owner_id: str, boundary_port: str) -> tuple[str, str]:
    """A function's inner INPUT dot can supply a value inside its body."""
    describe_graph(graph,origin='source')
    owners=[n for n in graph['nodes'] if n['id']==owner_id]
    if len(owners)!=1:raise BoundaryEditError('Function definition is not in the graph')
    owner=owners[0]
    key=owner.get('source_scope')
    if owner.get('graph_interface',{}).get('category')!='function' or not key:
        raise BoundaryEditError('Only function parameters can be rewired through this boundary')
    ports=[p for p in owner['draft_ports']['inputs'] if p['id']==boundary_port]
    if len(ports)!=1 or ports[0].get('type')=='execution':
        raise BoundaryEditError('Boundary input is not a function parameter')
    name=ports[0]['label']
    found=[]
    for n in graph['nodes']:
        if (n.get('source_kind')!='param' or n.get('containing_scope')!=key or
                not n.get('presentation_hidden')):continue
        for port in n['draft_ports']['outputs']:
            if port['label']==name:found.append((n['id'],port['id']))
    if len(found)!=1:
        raise BoundaryEditError('Cannot unambiguously resolve parameter binding')
    return found[0]


def terminal_return_target(graph: dict, owner_id: str, boundary_port: str) -> tuple[str, str]:
    """An expanded function's inner RETURN dot targets its real last return."""
    describe_graph(graph,origin='source')
    owners=[n for n in graph['nodes'] if n['id']==owner_id]
    if len(owners)!=1:raise BoundaryEditError('Function definition is not in the graph')
    owner=owners[0]
    key=owner.get('source_scope')
    if owner.get('graph_interface',{}).get('category')!='function' or not key:
        raise BoundaryEditError('Target must be a function output boundary')
    ports=[p for p in owner['draft_ports']['outputs'] if p['id']==boundary_port]
    if len(ports)!=1 or ports[0].get('label')!='return':
        raise BoundaryEditError('Boundary output is not a return value')
    terminal=[n for n in graph['nodes'] if n.get('terminal_boundary_owner')==key and
              n.get('source_kind')=='return' and n.get('presentation_hidden')]
    if len(terminal)!=1:
        raise BoundaryEditError('Multiple/early returns are not rewired through a single boundary dot')
    result=[p for p in terminal[0]['draft_ports']['inputs'] if p['id'].endswith(':value')]
    if len(result)!=1:
        raise BoundaryEditError('No editable return value exists at this boundary')
    return terminal[0]['id'], result[0]['id']
