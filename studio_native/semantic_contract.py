"""Stable read-only semantic/visual interface for Studio's existing graph producers.

This module does NOT parse source, execute a graph, or own source edits.
Both the Python AST projection and the draft Node Workspace adapt to this same
versioned description. Source authority stays in PythonDocument/source file;
authored drafts stay in model.py. No duplicate node/edge registry is stored.

All graph IDs and port IDs are preserved verbatim. Normalization MUST NOT create
additional programming nodes, control flow or casts.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

CONTRACT_VERSION = 1
RELATIONS = frozenset(('data', 'control', 'call', 'reference', 'effect', 'contains', 'imports'))


class ContractError(ValueError):
    pass


@dataclass(frozen=True)
class SourceLocation:
    line: int
    col: int
    end_line: int
    end_col: int


@dataclass(frozen=True)
class PortDescriptor:
    id: str
    label: str
    type_id: str
    direction: Literal['inputs', 'outputs']
    role: str  # value, execution, current_binding, etc. (never a claim of purity)
    has_inline_default: bool


@dataclass(frozen=True)
class ExitDescriptor:
    """A graph boundary's semantic exit, not an executable helper node.

    Normal returns have a control lane and optionally a typed value lane.
    Both are facets of one exit identity. Return *sites* belong to the source
    semantics; no extra flow/data graph nodes or edges are introduced here.
    """
    id: str
    kind: str
    control_type: str
    value_port: str | None
    control_port: str | None
    sites: tuple[str, ...]

    @property
    def control_anchor_id(self) -> str:
        """One stable control-facet identity, even without an authored port."""
        return self.control_port or (self.id+':control')


@dataclass(frozen=True)
class InterfaceDescriptor:
    """Stable graph interface shared by definition, region, and resource owners."""
    owner_node: str
    category: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    exits: tuple[ExitDescriptor, ...]


@dataclass(frozen=True)
class AppearanceDescriptor:
    """Read-only visual hints from the same authoritative graph producer.

    No language-specific widget or behavior is encoded in this descriptor.
    Adapters may supply a visual family and symbol, while the shared renderer
    applies the same compact/full node components to all graph origins.
    """
    title: str
    family: str
    symbol: str | None
    icon_id: str | None
    tooltip: str


@dataclass(frozen=True)
class NodeDescriptor:
    id: str
    title: str
    construct: str
    origin: Literal['source', 'draft', 'resource', 'program']
    ports: tuple[PortDescriptor, ...]
    source: SourceLocation | None
    child_graph: str | None
    owner_graph: str
    hidden: bool
    interface: InterfaceDescriptor | None = None
    appearance: AppearanceDescriptor | None = None
    folded_exit_owner: str | None = None  # source-declared terminal fold; not arbitrary hidden node
    semantic_role: str = 'unspecified'  # producer-owned definition vs invocation vs other
    effect_verification: str = 'unspecified'  # absence of a control pin never proves purity

    @property
    def definition_graph(self) -> str | None:
        """A reusable definition's implementation; never a branch body viewport."""
        return self.child_graph if self.semantic_role == 'definition' else None

    @property
    def operation_kind(self) -> str:
        """Adapter-reported semantic role, distinct from visual containment."""
        if self.semantic_role == 'definition':
            return 'definition'
        if self.semantic_role == 'invocation':
            return 'invocation'
        if self.semantic_role == 'control_operation':
            if self.construct in ('conditional', 'branch', 'if'):
                return 'branch'
            if self.construct in ('loop', 'for', 'while'):
                return 'loop'
            return 'control'
        return self.construct


@dataclass(frozen=True)
class SourceEvidence:
    """An observed source fragment supporting a relationship, not a runtime trace."""
    path: str
    line: int
    syntax: str


@dataclass(frozen=True)
class EdgeDescriptor:
    id: str
    source_node: str
    source_port: str
    target_node: str
    target_port: str
    relation: str
    certainty: str = 'unspecified'
    evidence: tuple[SourceEvidence, ...] = ()


@dataclass(frozen=True)
class GraphDescriptor:
    version: int
    identity: str
    origin: Literal['source', 'draft', 'resource', 'program']
    nodes: tuple[NodeDescriptor, ...]
    edges: tuple[EdgeDescriptor, ...]


def validated_port_payloads(node: NodeDescriptor, raw_node: dict, direction: Literal['inputs', 'outputs']) -> tuple[dict, ...]:
    """Map an adapter's UI payloads to the immutable port contract, in contract order.

    Source/resource graphs are snapshots: if the producer changes a pin after
    validation, fail rather than painting a pin whose identity/type changed.
    Mutable draft editing still uses its existing in-place editor lifecycle.
    This function never creates or alters a source node, port, or edge.
    """
    if direction not in ('inputs', 'outputs'):
        raise ContractError('Unknown port direction')
    if raw_node.get('id') != node.id:
        raise ContractError('Renderer node differs from validated port owner')
    declared = tuple(port for port in node.ports if port.direction == direction)
    payloads = raw_node.get('draft_ports', {}).get(direction, ())
    if len(payloads) != len(declared):
        raise ContractError(f'Port count changed after validation: {node.id}/{direction}')
    by_id = {payload.get('id'): payload for payload in payloads}
    if len(by_id) != len(payloads):
        raise ContractError(f'Duplicate renderer port: {node.id}/{direction}')
    if set(by_id) != {port.id for port in declared}:
        raise ContractError(f'Renderer port identity changed after validation: {node.id}/{direction}')
    result=[]
    for port in declared:
        payload = by_id[port.id]
        if str(payload.get('type', 'unknown')) != port.type_id or str(payload.get('label', '')) != port.label:
            raise ContractError(f'Renderer port contract changed after validation: {node.id}/{port.id}')
        result.append(payload)
    return tuple(result)


def validated_edge_payloads(contract: GraphDescriptor, graph: dict) -> tuple[dict, ...]:
    """Return raw layout/paint metadata in the exact validated edge order.

    A Qt canvas must pass the *same* graph that it described during rebuild.
    A background resize from an inactive tab must never fetch edges from the
    window's current provider alias. Refuse mismatches; never silently hide
    a missing edge or infer a replacement from another graph revision.
    """
    payloads=graph.get('edges', ())
    by_id={raw.get('id'): raw for raw in payloads}
    declared={edge.id for edge in contract.edges}
    if len(by_id)!=len(payloads) or set(by_id)!=declared:
        raise ContractError('Renderer edges differ from the validated canvas revision')
    result=[]
    for edge in contract.edges:
        raw=by_id[edge.id]
        if (raw.get('source'),raw.get('sourcePort'),raw.get('target'),raw.get('targetPort'),
                raw.get('relation','data'),str(raw.get('certainty','unspecified'))) != (
                edge.source_node,edge.source_port,edge.target_node,edge.target_port,
                edge.relation,edge.certainty):
            raise ContractError('Renderer edge endpoints/relationship changed after validation: '+edge.id)
        result.append(raw)
    return tuple(result)


def describe_graph(graph: dict, *, origin: Literal['source', 'draft', 'resource', 'program']) -> GraphDescriptor:
    """Validate and snapshot the existing graph's interface without mutation.

    The renderer may consume the same legacy dictionaries, but this contract
    is the common validation boundary; languages only provide descriptors.
    The type id is opaque because `py:int`, `rust:&str`, and prototype types
    must be expressible without inventing conversions or compatibility rules.
    """
    if origin not in ('source', 'draft', 'resource', 'program'):
        raise ContractError('Unknown graph origin')
    if not isinstance(graph, dict):
        raise ContractError('Graph must be a mapping')
    seen_nodes: set[str] = set()
    port_lookup: dict[tuple[str, str], str] = {}
    port_types: dict[tuple[str, str], str] = {}
    nodes: list[NodeDescriptor] = []
    for node in graph.get('nodes', ()):
        nid = node.get('id')
        if not isinstance(nid, str) or not nid or nid in seen_nodes:
            raise ContractError('Duplicate or missing node identity')
        seen_nodes.add(nid)
        seen_ports: set[str] = set()
        ports: list[PortDescriptor] = []
        for direction in ('inputs', 'outputs'):
            for port in node.get('draft_ports', {}).get(direction, ()):
                pid = port.get('id')
                if not isinstance(pid, str) or not pid or pid in seen_ports:
                    raise ContractError(f'Duplicate or missing port identity on {nid}')
                seen_ports.add(pid)
                role = ('execution' if port.get('type') == 'execution'
                        else port.get('binding_mode', 'value'))
                ports.append(PortDescriptor(pid, str(port.get('label', '')),
                    str(port.get('type', 'unknown')), direction, str(role),
                    'default' in port))
                port_lookup[(nid, pid)] = direction
                port_types[(nid, pid)] = str(port.get('type', 'unknown'))
        span = node.get('source_span')
        location = None
        if span is not None:
            try:
                location = SourceLocation(*(int(span[key]) for key in
                    ('line', 'col', 'end_line', 'end_col')))
            except (KeyError, ValueError, TypeError) as exc:
                raise ContractError(f'Invalid source location: {nid}') from exc
            if (location.line < 1 or location.end_line < location.line or
                    location.col < 0 or location.end_col < 0 or
                    (location.end_line == location.line and location.end_col < location.col)):
                raise ContractError(f'Invalid source span order: {nid}')
        if origin in ('draft', 'resource', 'program') and span:
            raise ContractError('Draft node must not claim source authority')
        child = node.get('child_region_key') or node.get('source_scope')
        if not isinstance(child, str):
            child = None
        interface=None
        raw_interface=node.get('graph_interface')
        if raw_interface is not None:
            if not isinstance(raw_interface, dict):
                raise ContractError(f'Invalid region interface on {nid}')
            ins=tuple(p['id'] for p in node.get('draft_ports',{}).get('inputs',()))
            outs=tuple(p['id'] for p in node.get('draft_ports',{}).get('outputs',()))
            declared_ins=tuple(raw_interface.get('inputs',ins))
            declared_outs=tuple(raw_interface.get('outputs',outs))
            if declared_ins != ins or declared_outs != outs:
                raise ContractError(f'Region interface must use existing port IDs: {nid}')
            exits=[]
            for entry in raw_interface.get('exits',()):
                if not isinstance(entry,dict) or not isinstance(entry.get('id'),str):
                    raise ContractError('Invalid interface exit')
                kind=entry.get('kind')
                if kind not in ('return','normal','body','true','false','break','continue','exception','yield','cancel'):
                    raise ContractError('Unknown interface exit kind')
                value_port=entry.get('value_port')
                if value_port is not None and value_port not in outs:
                    raise ContractError('Return value port does not belong to region owner')
                control_port=entry.get('control_port')
                if control_port is not None and control_port not in outs:
                    raise ContractError('Exit control port does not belong to region owner')
                if control_port is not None and next((p for p in ports if p.id==control_port),None).type_id != 'execution':
                    raise ContractError('Exit control port must have execution type')
                if value_port is not None:
                    value_descriptor=next(p for p in ports if p.id==value_port)
                    if value_descriptor.type_id == 'execution':
                        raise ContractError('Exit value must use a data port')
                if kind=='return' and raw_interface.get('category')!='function':
                    raise ContractError('Only function interfaces can declare return exits')
                if kind=='return' and control_port is not None:
                    raise ContractError('Return completion is one interface facet, not an authored control output')
                sites=tuple(entry.get('sites',()))
                if any(not isinstance(site,str) or not site for site in sites):
                    raise ContractError('Invalid exit site identity')
                exits.append(ExitDescriptor(entry['id'],kind,'execution',value_port,control_port,sites))
            if len({e.id for e in exits})!=len(exits):
                raise ContractError('Duplicate interface exit identity')
            interface=InterfaceDescriptor(nid,str(raw_interface.get('category','region')),
                                          declared_ins,declared_outs,tuple(exits))
        title=str(node.get('display_title') or node.get('title') or '')
        family=str(node.get('visual_family') or
                   ('resource' if origin=='resource' else
                    'source' if origin=='source' else 'program' if origin=='program' else 'draft'))
        if not family or len(family)>128:
            raise ContractError('Invalid node visual family')
        icon_ref=node.get('visual_assets',{}).get('header_icon') if isinstance(node.get('visual_assets',{}),dict) else None
        if icon_ref is not None and not isinstance(icon_ref,str):
            raise ContractError('Invalid header icon descriptor')
        symbol=node.get('display_symbol')
        if symbol is not None and not isinstance(symbol,str):
            raise ContractError('Invalid symbol descriptor')
        appearance=AppearanceDescriptor(title,family,symbol,icon_ref,
                                        str(node.get('subtitle','')))
        # The language adapter, not Qt, declares whether a construct is a
        # definition or a call. Missing metadata is intentionally unknown,
        # including for producers that predate this optional contract field.
        semantic_role=node.get('semantic_role','unspecified')
        if semantic_role not in ('unspecified','definition','invocation','control_operation','binding_write'):
            raise ContractError(f'Unknown semantic role on {nid}')
        if origin!='source' and semantic_role!='unspecified':
            raise ContractError('Non-source graphs cannot claim source semantic roles')
        if semantic_role == 'control_operation':
            if child is not None or node.get('embedded_region') is not None:
                raise ContractError('Control operation cannot own a nested graph viewport')
            # An IF/loop remains an operation even when presentation embeds
            # its body. A source graph must not convert it to a callable.
            allowed = {'conditional': 'conditional', 'loop': 'loop'}
            construct = str(node.get('source_construct') or node.get('source_kind'))
            expected = allowed.get(construct)
            if expected is None or (interface and interface.category != expected):
                raise ContractError('Control operation cannot own a callable/organizational interface')
            if not any(p.type_id == 'execution' and p.direction == 'outputs' for p in ports):
                raise ContractError('Control operation has no execution successors')
        if interface and interface.category=='function' and semantic_role!='definition':
            raise ContractError('Function interface must belong to a definition')
        effect_verification=node.get('effect_verification','unspecified')
        if effect_verification not in ('unspecified','unverified'):
            raise ContractError('Unsupported effect verification claim')
        if effect_verification!='unspecified' and semantic_role!='invocation':
            raise ContractError('Only a call site can carry invocation-effect metadata')
        folded_owner=node.get('terminal_boundary_owner')
        if folded_owner is not None and (origin!='source' or
                not isinstance(folded_owner,str) or not folded_owner or
                node.get('source_kind')!='return' or
                not node.get('presentation_hidden')):
            raise ContractError('Invalid source-declared folded return')
        nodes.append(NodeDescriptor(nid, str(node.get('title', '')),
            str(node.get('source_construct') or node.get('source_kind') or node.get('kind') or 'opaque'),
            origin, tuple(ports), location, child,
            str(node.get('containing_scope') or 'root'),
            bool(node.get('presentation_hidden', False)),interface,appearance,folded_owner,
            semantic_role,effect_verification))
    source_by_id={n['id']:n for n in graph.get('nodes',())}
    claimed_exit_sites=set()
    for descriptor in nodes:
        if descriptor.interface:
            for exit_spec in descriptor.interface.exits:
                if any(site not in seen_nodes for site in exit_spec.sites):
                    raise ContractError(f'Exit site missing from graph: {descriptor.id}')
                for sid in exit_spec.sites:
                    if sid in claimed_exit_sites:
                        raise ContractError('A nonlocal exit cannot belong to multiple regions')
                    claimed_exit_sites.add(sid)
                    raw_site=source_by_id[sid]
                    if exit_spec.kind=='return' and raw_site.get('source_kind')!='return':
                        raise ContractError('Return exit must reference an actual RETURN statement')
                    if raw_site.get('terminal_boundary_owner') is not None and (
                            exit_spec.kind!='return' or
                            raw_site['terminal_boundary_owner']!=source_by_id[descriptor.id].get('source_scope')):
                        raise ContractError('Folded return is not owned by the declared function exit')
                    declared_owner=raw_site.get('exit_target_owner')
                    declared_kind=raw_site.get('exit_kind')
                    if declared_owner is not None and declared_owner != descriptor.id:
                        raise ContractError('Exit site targets another owner')
                    if declared_kind is not None and declared_kind != exit_spec.kind:
                        raise ContractError('Exit site kind differs from region interface')
    for desc in nodes:
        if desc.folded_exit_owner and desc.id not in claimed_exit_sites:
            raise ContractError('Folded return has no declared interface exit')
    edges: list[EdgeDescriptor] = []
    seen_edges: set[str] = set()
    for e in graph.get('edges', ()):
        eid = e.get('id')
        relation = e.get('relation', 'data')
        if not isinstance(eid, str) or not eid or eid in seen_edges:
            raise ContractError('Duplicate or missing edge identity')
        seen_edges.add(eid)
        if relation not in RELATIONS:
            raise ContractError(f'Unknown relationship {relation!r}')
        source = (e.get('source'), e.get('sourcePort'))
        target = (e.get('target'), e.get('targetPort'))
        if port_lookup.get(source) != 'outputs' or port_lookup.get(target) != 'inputs':
            raise ContractError(f'Edge {eid} has an unknown or reversed port')
        # Prevent a future language producer from painting a value dependency
        # as executable flow (or vice versa). Opaque language-qualified data
        # types remain legal; this validates channels, not type coercion.
        source_exec=port_types[source]=='execution'
        target_exec=port_types[target]=='execution'
        if relation=='control' and not (source_exec and target_exec):
            raise ContractError('Control edges require execution ports at both ends')
        if relation in ('data','call','reference','imports') and (source_exec or target_exec):
            raise ContractError(f'{relation} edges cannot carry execution ports')
        evidence=[]
        for item in e.get('provenance', ()): 
            if not isinstance(item, dict):raise ContractError('Invalid provenance record')
            try:
                line=int(item['line'])
                path=str(item['source'])
                syntax=str(item['syntax'])
            except (KeyError, TypeError, ValueError) as exc:
                raise ContractError('Invalid source evidence') from exc
            if line<1 or not path or len(path)>4096 or len(syntax)>4096:
                raise ContractError('Invalid or excessive source evidence')
            evidence.append(SourceEvidence(path,line,syntax))
            if len(evidence)>64:raise ContractError('Excessive source evidence')
        certainty=str(e.get('certainty','unspecified'))
        if certainty not in ('unspecified','source-backed','syntactic-name-match','local-file-candidate','literal-path-candidate'):
            raise ContractError('Unknown evidence certainty')
        edges.append(EdgeDescriptor(eid, source[0], source[1], target[0], target[1], relation,
                                    certainty,tuple(evidence)))
    return GraphDescriptor(CONTRACT_VERSION,
        str(graph.get('scope') or ('draft:workspace' if origin == 'draft' else 'program:root' if origin == 'program' else 'source:module')),
        origin, tuple(nodes), tuple(edges))


def canvas_graph_source(*, source_view: bool = False, resource_view: bool = False,
                        settings_view: bool = False, state: dict | None = None,
                        source_graph: dict | None = None,
                        resource_graph: dict | None = None):
    """Select EXACTLY one graph authority for a canvas, or none if unloaded.

    This must not fallback to the draft workspace when the Python or filesystem
    graph is missing. Settings are synthesized by the settings node adapter
    and have no document graph in this version. This selector stays Qt-free.
    """
    if sum(bool(v) for v in (source_view, resource_view, settings_view)) > 1:
        raise ContractError('Ambiguous graph canvas role')
    if settings_view:return None, None
    if source_view:return source_graph, 'source'
    if resource_view:return resource_graph, 'resource'
    return state, 'draft' if state is not None else None


def port_presentation_role(node: NodeDescriptor, port_id: str) -> str:
    """Classify a validated port without creating a second port authority.

    An output on a definition boundary is not an invocation's runtime value;
    only a call-site result can hold that role. These tags describe painting
    and tooltips, not execution or source-edit permissions.
    """
    port=next((p for p in node.ports if p.id==port_id),None)
    if port is None:
        raise ContractError('Port does not belong to node descriptor')
    if port.type_id=='execution':
        return ('definition-time-execution' if node.semantic_role=='definition'
                else 'execution')
    if (node.semantic_role=='definition' and node.interface and
            port.direction=='outputs' and any(
                exit_spec.kind=='return' and exit_spec.value_port==port_id
                for exit_spec in node.interface.exits)):
        return 'definition-result-interface'
    if node.semantic_role=='definition' and port.direction=='outputs':
        return 'definition-output'
    if node.semantic_role=='invocation' and port.direction=='outputs':
        return 'invocation-result'
    return 'data'
