"""Read-only projection of semantic region exits into visual route endpoints.

This is NOT an execution graph or a source editing authority.  Route identities
refer exclusively to existing interface descriptions and source RETURN sites.
Qt geometry, cameras, colors and animations are purposefully kept elsewhere.
"""
from __future__ import annotations
from dataclasses import dataclass
from .semantic_contract import GraphDescriptor, ContractError


@dataclass(frozen=True)
class ExitRoute:
    id: str
    owner_node: str
    site_node: str
    kind: str
    control_anchor: str
    value_port: str | None
    value_input: str | None
    # A folded site is represented by the boundary instead of an internal card.
    folded: bool


def project_exit_routes(graph: GraphDescriptor) -> tuple[ExitRoute, ...]:
    """Describe source-backed exit routes without creating nodes or edges.

    A route has one control facet and an optional value facet.  Multiple
    distinct RETURN sites may share one enclosing function boundary; no
    extra RETURN/merge operations are synthesized.  This is deliberately
    language-neutral at the contract layer: language adapters supply exits.
    """
    by_id={n.id:n for n in graph.nodes}
    routes=[]
    for owner in graph.nodes:
        if owner.interface is None:continue
        for spec in owner.interface.exits:
            if spec.kind!='return':continue
            if owner.interface.category!='function':
                raise ContractError('Return exit belongs to nonfunction composite')
            for site_id in spec.sites:
                site=by_id[site_id]
                # Source constructs and their interface exits must agree.
                if site.construct!='return':
                    raise ContractError('Return exit site is not a RETURN statement')
                value_inputs=tuple(p for p in site.ports if
                                   p.direction=='inputs' and p.type_id!='execution')
                if len(value_inputs)>1:
                    raise ContractError('Ambiguous return value inputs')
                if value_inputs and spec.value_port is None:
                    raise ContractError('Value-return site has no owner value interface')
                routes.append(ExitRoute(spec.id+':site:'+site_id, owner.id,
                    site_id, spec.kind, spec.control_anchor_id, spec.value_port,
                    value_inputs[0].id if value_inputs else None,
                    site.folded_exit_owner==owner.child_graph))
    return tuple(routes)


@dataclass(frozen=True)
class FoldedExitConnection:
    """A real incoming edge redirected to an existing function interface facet.

    This is geometry intent, not a new source edge or port. A value edge
    terminates on the typed result; control terminates on normal completion.
    """
    edge_id: str
    route: ExitRoute
    facet: str


def project_folded_exit_connections(graph: GraphDescriptor,
                                    routes: tuple[ExitRoute, ...]) -> tuple[FoldedExitConnection, ...]:
    """Resolve folded RETURN *existing* inbound edges by validated port IDs."""
    sites={r.site_node:r for r in routes if r.folded}
    node_by_id={n.id:n for n in graph.nodes}
    connections=[]
    for edge in graph.edges:
        route=sites.get(edge.target_node)
        if route is None:
            continue
        if edge.relation=='data' and edge.target_port==route.value_input and route.value_port:
            connections.append(FoldedExitConnection(edge.id,route,'value'))
        elif edge.relation=='control':
            target_port=next((p for p in node_by_id[route.site_node].ports
                              if p.id==edge.target_port),None)
            if target_port and target_port.direction=='inputs' and target_port.type_id=='execution':
                connections.append(FoldedExitConnection(edge.id,route,'control'))
    return tuple(connections)
