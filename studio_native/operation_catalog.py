"""Read-only operation discovery from validated graph descriptors.

This is a *projection*, not another source of truth or a visual compiler.
The language adapter remains responsible for advertising/validating any future
creation or source transform. Never infer an authoring capability from a painted
node, source annotation, or data/control connection.
"""
from __future__ import annotations
from dataclasses import dataclass
from .semantic_contract import ContractError, GraphDescriptor, NodeDescriptor


@dataclass(frozen=True)
class ObservedOperation:
    id: str
    kind: str
    occurrences: tuple[str, ...]
    input_roles: tuple[str, ...]
    output_roles: tuple[str, ...]
    authoring: str = 'not-qualified'


def observed_operations(graph: GraphDescriptor, *, language: str = 'python') -> tuple[ObservedOperation, ...]:
    """Inventory actual adapter-produced constructs, without inventing ports.

    Only source graphs are supported. This deliberately does *not* list absent
    language operations or promise creation capability from observed syntax.
    """
    if not isinstance(graph, GraphDescriptor) or graph.origin != 'source':
        raise ContractError('Operation discovery requires a validated source graph')
    if not language or not language.isidentifier():
        raise ContractError('Operation discovery requires a language identifier')
    relevant = {'branch', 'loop', 'invocation', 'definition', 'return',
                'augmented_assignment', 'assignment', 'operation', 'compare'}
    groups: dict[str, list[NodeDescriptor]] = {}
    for node in graph.nodes:
        kind = node.operation_kind
        if kind in relevant:
            groups.setdefault(kind, []).append(node)
    result=[]
    for kind, examples in sorted(groups.items()):
        result.append(ObservedOperation(
            f'{language}:{kind}', kind, tuple(x.id for x in examples),
            tuple(sorted({p.role for x in examples for p in x.ports if p.direction == 'inputs'})),
            tuple(sorted({p.role for x in examples for p in x.ports if p.direction == 'outputs'}))))
    return tuple(result)


@dataclass(frozen=True)
class FunctionBoundary:
    """A definition's interface and observed body sites, not a call node.

    `inputs` and `return_sites` are source-owned IDs. No synthetic execution
    edge, mirrored semantic port, or runtime call result is created.
    """
    definition_id: str
    scope: str
    inputs: tuple[str, ...]
    result_port: str | None
    return_sites: tuple[str, ...]
    entry_bindings: tuple[tuple[str, str], ...]


def function_boundaries(graph: GraphDescriptor) -> tuple[FunctionBoundary, ...]:
    if not isinstance(graph, GraphDescriptor) or graph.origin != 'source':
        raise ContractError('Function boundary inspection requires a source graph')
    result=[]
    for node in graph.nodes:
        if node.semantic_role != 'definition' or not node.interface or node.interface.category != 'function':
            continue
        scope=node.definition_graph
        if not scope:
            raise ContractError('Function definition lacks an implementation scope')
        # A PARAMETER inside the definition is a lexical binding, not a second
        # external input pin. Identify matches only when their names and types
        # can be proven from the already validated port descriptors.
        parameters={}
        for entry in graph.nodes:
            if entry.owner_graph != scope or entry.construct != 'param':
                continue
            for p in entry.ports:
                if p.direction == 'outputs':
                    parameters.setdefault((p.label,p.type_id), []).append(p.id)
        mappings=[]
        for pid in node.interface.inputs:
            port=next(p for p in node.ports if p.id == pid)
            matches=parameters.get((port.label,port.type_id),())
            if len(matches)==1:
                mappings.append((pid,matches[0]))
        returns=tuple(site for exit_ in node.interface.exits if exit_.kind=='return' for site in exit_.sites)
        output=next((ex.value_port for ex in node.interface.exits if ex.kind=='return'),None)
        result.append(FunctionBoundary(node.id,scope,node.interface.inputs,output,returns,tuple(mappings)))
    return tuple(result)


def qualified_operations(language: str = 'python'):
    """Adapter-defined source-authoring capabilities, never inferred from observations.

    Only explicitly qualified lowering paths can return source proposals. This
    is a registry *projection*: definitions live with each language adapter.
    """
    if language == 'python':
        from .python_authoring import definitions
        return definitions()
    return ()
