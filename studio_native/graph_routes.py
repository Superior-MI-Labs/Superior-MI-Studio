"""Resolve a view route through its owning provider into one validated graph.

A Route selects a view. It never represents a source edit, runtime execution,
filesystem mutation, or a second graph authority. Consumers receive the graph
from the existing resource/Python adapter and its validated descriptor together.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .navigation import Route
from .python_graph import PythonDocument
from .resource_graph import directory_graph
from .semantic_contract import GraphDescriptor, describe_graph


class GraphRouteError(ValueError):
    """A route cannot be resolved by the installed providers."""


@dataclass(frozen=True)
class ResolvedGraph:
    route: Route
    graph: dict
    descriptor: GraphDescriptor
    document: PythonDocument | None = None


def resolve_source_session_route(
    route: Route, session, *, detail: str = 'readable',
    expanded_scopes=(), collapsed_regions=(),
) -> ResolvedGraph:
    """Resolve navigation strictly from the current revisioned source owner.

    Unlike resolve_graph(document=None), this path must NEVER silently reread
    saved bytes when an edited or invalid live document is awaiting analysis.
    Historical focus routes can outlive the function they addressed: refusing
    the destination preserves the history cursor and never displays old AST.
    """
    if route.kind != 'source':
        raise GraphRouteError('A source session can resolve only source routes')
    if Path(session.path).expanduser().absolute()!=Path(route.path).expanduser().absolute():
        raise GraphRouteError('Source owner does not match the requested route')
    if session.parsed is None or not session.graph_ready:
        raise GraphRouteError('Current Python source revision has no qualified graph: '
                              +str(session.diagnostic))
    return resolve_graph(route,document=session.parsed,detail=detail,
                         expanded_scopes=expanded_scopes,
                         collapsed_regions=collapsed_regions)


def resolve_graph(
    route: Route, *, document: PythonDocument | None = None,
    detail: str = 'readable', expanded_scopes=(), collapsed_regions=(),
    resource_expanded=(), resource_offset: int = 0,
    resource_imports: bool = False, source_documents=None,
    resource_relationship_kinds=('imports','references'),
    resource_relationship_focus=None, resource_relationship_direction='both',
) -> ResolvedGraph:
    """Resolve known views without guessing unknown semantics.

    Reuse `document` only for its exact source identity, so separate tabs cannot
    accidentally show a different file's AST. One invocation projects one view;
    no provider graph or document cache is created here.
    """
    if not isinstance(route, Route):
        raise TypeError('Expected a validated view Route')
    if route.kind == 'region':
        raise GraphRouteError('Nested control-region focus is not qualified by the Python adapter')
    requested = Path(route.path).expanduser().absolute()
    if route.kind == 'resource':
        if route.scope != 'module' or route.mode != 'whole' or route.region:
            raise GraphRouteError('A resource route cannot contain Python scope or region state')
        if document is not None:
            raise GraphRouteError('Resource views cannot bind a Python document')
        graph = directory_graph(requested, offset=resource_offset,
                                show_imports=resource_imports,
                                relationship_kinds=resource_relationship_kinds,
                                relationship_focus=resource_relationship_focus,
                                relationship_direction=resource_relationship_direction,
                                expanded_paths=resource_expanded,
                                source_documents=source_documents)
        descriptor = describe_graph(graph, origin='resource')
        return ResolvedGraph(Route('resource', graph['path']), graph, descriptor)
    if route.kind != 'source':
        raise GraphRouteError('No graph provider for route')
    if route.region:
        raise GraphRouteError('A source route cannot carry a control-region identity')
    if requested.suffix.lower() != '.py':
        raise GraphRouteError('No qualified language adapter for '+requested.suffix)
    if route.mode == 'whole' and route.scope != 'module':
        raise GraphRouteError('Whole-file views must use the module scope')
    if document is not None and Path(document.path).absolute() != requested:
        raise GraphRouteError('Document identity does not match the requested route')
    doc = document if document is not None else PythonDocument(requested)
    if route.mode == 'focus':
        if route.scope not in doc.scopes:
            raise GraphRouteError('Source scope is not present in the selected document')
        graph = doc.composite_file_graph(detail=detail, collapsed_regions=set(collapsed_regions),
                                         focus_scope=route.scope)
    else:
        graph = doc.composite_file_graph(set(expanded_scopes), detail=detail,
                                         collapsed_regions=set(collapsed_regions))
    descriptor = describe_graph(graph, origin='source')
    return ResolvedGraph(Route('source', str(doc.path), route.scope, route.mode),
                         graph, descriptor, doc)
