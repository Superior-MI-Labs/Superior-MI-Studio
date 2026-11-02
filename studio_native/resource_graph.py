"""Read-only filesystem resource adapter for Studio's shared recursive graph canvas.

A directory listing is an intentionally bounded *snapshot* of immediate entries.
No code execution, recursive crawling, symlink traversal, or filesystem writes.
Program semantics continue to belong solely to the language adapter.
"""
from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass
import os
import hashlib
import heapq
import stat
import unicodedata
from copy import deepcopy
from .graph_surface import RESOURCE_COMPACT_WIDTH, RESOURCE_COMPACT_HEIGHT

MAX_ENTRIES = 72
MAX_INLINE_ENTRIES = 18
MAX_INLINE_DEPTH = 3
MAX_VISIBLE_NODES = 180

# File presentation capabilities are read-only and belong to the resource
# adapter. They do not imply editing, execution, or a new document authority.
IMAGE_SUFFIXES=frozenset({'.png','.jpg','.jpeg','.gif','.bmp','.webp'})
MAX_PREVIEW_FILE_BYTES=8_000_000
MAX_EMBEDDED_SOURCE_NODES=64
TEXT_SUFFIXES=frozenset({'.txt','.md','.rst','.json','.jsonl','.toml','.yaml','.yml',
                         '.ini','.cfg','.csv','.tsv','.xml','.html','.css','.js','.ts','.sh'})
MAX_TEXT_PREVIEW_BYTES=4096
MAX_TEXT_PREVIEW_LINES=8
MAX_TEXT_PREVIEW_COLUMNS=58

def preview_kind(path: Path, kind: str) -> str:
    """The resource owner declares whether a file has a qualified preview."""
    if kind!='file':return 'none'
    suffix=Path(path).suffix.lower()
    if suffix=='.py':return 'python-graph'
    if suffix in IMAGE_SUFFIXES:return 'image'
    if suffix in TEXT_SUFFIXES and not path.name.startswith('.'):return 'text'
    return 'none'

def expanded_file_preview(path: Path, preview: str) -> dict:
    """Never load binary image pixels here; Qt performs bounded display only."""
    try:
        if path.is_symlink() or not path.is_file():return {'kind':preview,'status':'Unavailable'}
        size=path.stat().st_size
        if size>MAX_PREVIEW_FILE_BYTES:return {'kind':preview,'status':'Preview exceeds 8 MB limit'}
        if preview=='image':return {'kind':'image','status':'','bytes':size}
        if preview=='text':
            # Explicit, local read-only capability. No generic document owner,
            # unbounded read, rich/HTML execution or encoding fallback. Refuse
            # symlink swaps at open time (including on systems with O_NOFOLLOW).
            descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
            with os.fdopen(descriptor,'rb') as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    return {'kind':'text','status':'Not a regular file'}
                sample=stream.read(MAX_TEXT_PREVIEW_BYTES+1)
            if b'\x00' in sample:
                return {'kind':'text','status':'Binary content; text preview refused'}
            # Decode only complete UTF-8 sequences; if the read stops in a
            # multi-byte character, trim that incomplete trailing sequence.
            truncated=len(sample)>MAX_TEXT_PREVIEW_BYTES
            sample=sample[:MAX_TEXT_PREVIEW_BYTES]
            try:
                decoded=sample.decode('utf-8')
            except UnicodeDecodeError as exc:
                if not truncated or exc.end!=len(sample) or exc.reason!='unexpected end of data':
                    return {'kind':'text','status':'Not valid UTF-8'}
                decoded=sample[:exc.start].decode('utf-8')
            # Do not send escape/control characters into a Qt text surface.
            cleaned=''.join(c if c in '\n\t' or unicodedata.category(c) not in ('Cc','Cf')
                            else ' ' for c in decoded)
            lines=cleaned.expandtabs(4).splitlines()
            snippet='\n'.join(line[:MAX_TEXT_PREVIEW_COLUMNS]+('…' if len(line)>MAX_TEXT_PREVIEW_COLUMNS else '')
                              for line in lines[:MAX_TEXT_PREVIEW_LINES])
            if not snippet:snippet='(empty file)'
            more=truncated or len(lines)>MAX_TEXT_PREVIEW_LINES
            return {'kind':'text','status':'Read-only excerpt'+(' · more content' if more else ''),
                    'text':snippet,'bytes':size}
        if preview=='python-graph':return {'kind':preview,'status':''}
    except OSError:return {'kind':preview,'status':'Resource unavailable'}
    return {'kind':'none','status':''}


def _attach_python_projection(owner: dict, nodes: list, edges: list, source_documents: dict) -> None:
    """Embed one existing Python graph projection, never another document owner.

    First validate its native source contract. The resource workbench then
    displays a namespaced, read-only *presentation* of those nodes and edges;
    executable semantics, source spans and function interfaces stay owned by
    the source adapter, not by the resource graph's descriptor.
    """
    path=Path(owner['resource_path'])
    try:
        if (path.is_symlink() or not path.is_file() or
                path.stat().st_size>MAX_PREVIEW_FILE_BYTES):return
        active=source_documents.get(str(path))
        if active is not None:
            # Callers may hand in only their existing SourceDocumentSession.
            if Path(active.path)!=path:
                raise ResourceError('Source session path does not match resource identity')
            if not active.graph_ready:
                owner['resource_preview']={'kind':'python-graph',
                    'status':'Live source has no qualified graph (syntax/analysis error)'}
                return
            doc=active.parsed
            status=f'Live source · revision {active.revision}' if active.dirty else 'Open source · saved revision'
        else:
            from .python_graph import PythonDocument
            doc=PythonDocument(path)
            status='Saved source · read-only projection'
        from .semantic_contract import describe_graph
        expanded=set(doc.scopes)-{'module'}
        graph=doc.composite_file_graph(expanded,max_nodes=MAX_EMBEDDED_SOURCE_NODES,detail='readable')
        if any('capped at' in str(w) for w in graph.get('warnings',())):
            graph=doc.composite_file_graph(set(),max_nodes=MAX_EMBEDDED_SOURCE_NODES,detail='readable')
            status+=' · open file to see all scopes'
        describe_graph(graph,origin='source')
    except (OSError,ValueError):
        owner['resource_preview']={'kind':'python-graph','status':'Python analysis unavailable'}
        return
    # A resource snapshot is bounded even when several files are expanded.
    if len(nodes)+len(graph['nodes'])>MAX_VISIBLE_NODES:
        owner['resource_preview']={'kind':'python-graph','status':'Workspace node limit; open source graph'}
        return
    scope='resource-python-region:'+owner['id']
    prefix=owner['id']+':python:'
    node_ids={n['id']:prefix+n['id'] for n in graph['nodes']}
    port_ids={p['id']:prefix+p['id'] for n in graph['nodes']
              for direction in ('inputs','outputs') for p in n['draft_ports'][direction]}
    def region_key(value):return scope if value in ('module',None) else scope+':'+str(value)
    for raw in graph['nodes']:
        node=deepcopy(raw)
        node['id']=node_ids[raw['id']]
        node['containing_scope']=region_key(raw.get('containing_scope','module'))
        if node.get('child_region_key'):
            node['child_region_key']=region_key(node['child_region_key'])
        if node.get('embedded_region'):
            node['embedded_region']['scope']=region_key(node['embedded_region']['scope'])
        for direction in ('inputs','outputs'):
            for port in node['draft_ports'][direction]:
                port['id']=port_ids[port['id']]
        # A resource descriptor must not masquerade as source authority.
        # Original source semantics are independently validated above and are
        # available when the user opens the canonical Python source view.
        node.pop('source_span',None)
        node.pop('graph_interface',None)
        node.pop('terminal_boundary_owner',None)
        node.pop('exit_target_owner',None)
        node.pop('exit_kind',None)
        node.pop('terminal_return_span',None)
        node['semantic_role']='unspecified'
        node['effect_verification']='unspecified'
        node['resource_source_path']=str(path)
        node['resource_source_scope']=raw.get('source_scope')
        nodes.append(node)
    for raw in graph['edges']:
        edge=deepcopy(raw)
        edge['id']=prefix+edge['id']
        edge['source']=node_ids[edge['source']]
        edge['target']=node_ids[edge['target']]
        edge['sourcePort']=port_ids[edge['sourcePort']]
        edge['targetPort']=port_ids[edge['targetPort']]
        edges.append(edge)
    # Existing GraphCanvas owns child surfaces, cameras, clipping and resize.
    # No nested QGraphicsView, tab registry, or new AST representation is made.
    content_w=max((n['x']+260 for n in nodes if n.get('containing_scope')==scope),default=320.)
    content_h=max((n['y']+180 for n in nodes if n.get('containing_scope')==scope),default=170.)
    view_w=min(750.,max(320.,content_w))
    view_h=min(420.,max(170.,content_h))
    owner['child_region_key']=scope
    owner['region_role']='python-source'
    owner['embedded_region']={'scope':scope,'role':'python-source',
        'width':view_w+12.,'height':31.+view_h+6.,'surface_top':31.,
        'viewport_width':view_w,'viewport_height':view_h,
        'content_width':content_w,'content_height':content_h}
    owner['resource_preview']=None
    owner['subtitle']=status

class ResourceError(ValueError):
    pass

@dataclass(frozen=True)
class ResourceEntry:
    path: Path
    kind: str
    label: str
    uri: str


def _entry(path: Path) -> ResourceEntry:
    # Identifying a symlink never follows it; it is a resource, not its target.
    if path.is_symlink(): kind='symlink'
    elif path.is_dir(): kind='directory'
    elif path.is_file(): kind='file'
    else: kind='other'
    return ResourceEntry(path,kind,path.name or str(path),path.as_uri())


def snapshot(path: str | Path, *, limit: int=MAX_ENTRIES, offset: int=0):
    path=Path(path).expanduser().absolute()
    if path.is_symlink(): raise ResourceError('Refusing to traverse a symlink directory')
    if not path.is_dir(): raise ResourceError('Not a readable directory: '+str(path))
    if not 1 <= limit <= MAX_ENTRIES or not 0 <= offset <= 720:
        raise ResourceError('Invalid directory page size or offset')
    # Keep memory bounded and ordering deterministic, even with unsorted
    # os.scandir results. Pagination never traverses into a child directory.
    count=0
    def entries():
        nonlocal count
        try:
            with os.scandir(path) as it:
                for item in it:
                    count+=1
                    if count>50_000:break
                    entry=_entry(path/item.name)
                    yield (entry.kind!='directory',entry.label.casefold(),entry.uri,entry)
        except OSError as exc:
            raise ResourceError('Cannot browse directory: '+str(exc)) from exc
    selected=heapq.nsmallest(offset+limit+1,entries())
    selected_entries=[e[-1] for e in selected[offset:offset+limit]]
    has_more=len(selected)>offset+limit
    return path,selected_entries,has_more,offset>0



@dataclass(frozen=True)
class ResourceRelationshipInspection:
    """Read-only view of one qualified resource association, no new graph owner."""
    edge_id: str
    source: Path
    target: Path
    relation: str
    certainty: str
    evidence: tuple


@dataclass(frozen=True)
class ResourceRelationshipSearch:
    """Bounded query of one immutable displayed relationship revision."""
    results: tuple[ResourceRelationshipInspection, ...]
    total: int
    imports: int
    references: int
    limit: int


def search_resource_relationships(contract, graph: dict, *, query='', focus=None,
                                  direction='both', hops=1, limit=24):
    """Search already-visible candidate edges, with bounded adjacency browsing.

    One or two hops means walking edges in THIS immutable visible snapshot,
    never following a filesystem path or inventing transitive dependencies.
    Results and evidence are not runtime authority.
    """
    from .semantic_contract import ContractError, validated_edge_payloads
    if contract is None or contract.origin!='resource' or graph is None:
        raise ContractError('Relationship search requires a resource graph')
    if not isinstance(query,str) or len(query)>128:
        raise ValueError('Relationship search must be at most 128 characters')
    if type(limit) is not int or not 1<=limit<=48:
        raise ValueError('Relationship result limit must be between 1 and 48')
    if type(hops) is not int or hops not in (1,2):
        raise ValueError('Relationship traversal supports one or two visible hops')
    if direction not in ('both','incoming','outgoing'):
        raise ValueError('Unknown relationship search direction')
    if focus is not None and not isinstance(focus,(str,Path)):
        raise ValueError('Search focus must be a visible file path')
    if focus is None and (direction!='both' or hops!=1):
        raise ValueError('Relationship traversal requires a focused file')
    validated_edge_payloads(contract,graph)
    eligible={n['resource_path'] for n in graph.get('nodes',())
              if n.get('resource_kind')=='file' and n.get('resource_path')}
    focus_path=str(Path(focus).expanduser().absolute()) if focus is not None else None
    if focus_path is not None and focus_path not in eligible:
        raise ContractError('Search focus is not visible in this graph revision')
    # One raw-revision validation up front. Each endpoint still receives its
    # own identity, symlink and file-existence checks before being exposed.
    inspected=tuple(_inspect_resource_relationship_validated(contract,graph,edge.id)
                    for edge in sorted(contract.edges,key=lambda e:e.id)
                    if edge.relation in ('imports','reference'))
    allowed=None
    if focus_path is not None:
        allowed=set()
        frontier={focus_path}
        visited=set(frontier)
        for _ in range(hops):
            next_frontier=set()
            for item in inspected:
                src,dst=str(item.source),str(item.target)
                forward=direction in ('both','outgoing') and src in frontier
                backward=direction in ('both','incoming') and dst in frontier
                if forward or backward:
                    allowed.add(item.edge_id)
                    if forward:next_frontier.add(dst)
                    if backward:next_frontier.add(src)
            frontier=next_frontier-visited
            visited.update(frontier)
            if not frontier:break
    found=[]; total=imports=references=0
    term=query.casefold().strip()
    for item in inspected:
        if allowed is not None and item.edge_id not in allowed:
            continue
        if term and not any(term in field.casefold() for field in (
                str(item.source),str(item.target),item.relation,item.certainty,
                *(f'{p.path}:{p.line} {p.syntax}' for p in item.evidence))):
            continue
        total+=1
        imports+=item.relation=='imports'
        references+=item.relation=='reference'
        if len(found)<limit:found.append(item)
    return ResourceRelationshipSearch(tuple(found),total,imports,references,limit)


def inspect_resource_relationship(contract, graph: dict, edge_id: str) -> ResourceRelationshipInspection:
    """Inspect only an edge in *this canvas's* already validated revision.

    The graph's producer owns resource identities and the immutable semantic
    contract owns evidence. An inactive canvas or a stale edge must never be
    interpreted using the current window's provider alias.
    """
    from .semantic_contract import ContractError, validated_edge_payloads
    if contract is None or contract.origin != 'resource' or graph is None:
        raise ContractError('Relationship inspection requires a resource graph')
    # Check every declared edge against the matching raw revision, not just
    # the requested ID. A mutated graph has no valid inspection actions.
    validated_edge_payloads(contract, graph)
    return _inspect_resource_relationship_validated(contract,graph,edge_id)


def _inspect_resource_relationship_validated(contract,graph,edge_id):
    """Caller already verified this raw revision against its descriptor."""
    from .semantic_contract import ContractError
    edge=next((item for item in contract.edges if item.id==edge_id),None)
    if edge is None or edge.relation not in ('imports','reference'):
        raise ContractError('No inspectable resource relationship')
    resources={node['id']:node for node in graph.get('nodes',())
               if node.get('resource_kind')=='file' and node.get('resource_path')}
    source=resources.get(edge.source_node)
    target=resources.get(edge.target_node)
    if source is None or target is None:
        raise ContractError('Relationship endpoint is not a visible file')
    root=Path(graph['path']).absolute()
    if root.is_symlink() or not root.is_dir():
        raise ContractError('Relationship workspace root changed after validation')
    def qualified_path(node):
        path=Path(node['resource_path']).absolute()
        expected='resource:'+hashlib.sha256(os.fsencode(str(path))).hexdigest()[:24]
        if expected!=node['id']:
            raise ContractError('Resource endpoint identity changed after validation')
        try:
            parts=path.relative_to(root).parts
        except ValueError as exc:
            raise ContractError('Relationship endpoint escapes workspace root') from exc
        if not parts or any(part.startswith('.') for part in parts):
            raise ContractError('Hidden or root endpoint cannot be inspected')
        # A symlink introduced after the snapshot must also fail closed.
        cursor=root
        for part in parts:
            cursor=cursor/part
            if cursor.is_symlink():
                raise ContractError('Relationship endpoint is a symlink')
        if not path.is_file():
            raise ContractError('Relationship endpoint is no longer a regular file')
        return path
    return ResourceRelationshipInspection(edge.id,qualified_path(source),
        qualified_path(target),edge.relation,edge.certainty,edge.evidence)

def directory_graph(path: str | Path, *, limit: int=MAX_ENTRIES, offset: int=0,
                    show_imports: bool=False, expanded_paths=(), source_documents=None,
                    relationship_kinds=('imports','references'),
                    relationship_focus=None, relationship_direction='both'):
    layers=frozenset(relationship_kinds)
    if relationship_direction not in ('both','incoming','outgoing'):
        raise ResourceError('Unknown relationship direction')
    if not layers.issubset({'imports','references'}):
        raise ResourceError('Unknown resource relationship layer')
    root,entries,truncated,previous=snapshot(path,limit=limit,offset=offset)
    nodes=[];edges=[]
    # One resource node per real directory entry. No fabricated execution nodes.
    cols=4
    requested_expansions={str(Path(p).expanduser().absolute()) for p in expanded_paths}
    for ix,entry in enumerate(entries):
        name=entry.label
        suffix=entry.path.suffix.lower()
        preview='Python source · open as graph' if entry.kind=='file' and suffix=='.py' else entry.kind
        nid='resource:'+hashlib.sha256(os.fsencode(str(entry.path))).hexdigest()[:24]
        capability=preview_kind(entry.path,entry.kind)
        nodes.append({'id':nid,'title':name,'display_title':name,
            'subtitle':preview,'kind':'resource','source_kind':'resource',
            'resource_uri':entry.uri,'resource_path':str(entry.path),'resource_kind':entry.kind,
            'preview_kind':capability,'resource_preview':(expanded_file_preview(entry.path,capability)
                if str(entry.path) in requested_expansions and capability!='none' else None),
            'accent':'#7ac7e0' if entry.kind=='directory' else '#e0ba78' if suffix=='.py' else '#7b91a6',
            'x':100+(ix%cols)*(RESOURCE_COMPACT_WIDTH+16.),'y':85+(ix//cols)*(RESOURCE_COMPACT_HEIGHT+16.),
            'draft_ports':{'inputs':[],'outputs':[]},'containers':[]})
    # Graphs and files are resources, not executable operations. Expanding a
    # folder reveals a *bounded* child surface in the SAME scene/renderer.
    # Never scan recursively except for explicit, currently expanded paths.
    # The authoritative root remains the selected filesystem directory.
    requested=requested_expansions
    def region_for(nid):return 'resource-region:'+nid
    def attach_children(parent_node, depth):
        if depth>MAX_INLINE_DEPTH or len(nodes)>=MAX_VISIBLE_NODES:return
        folder=Path(parent_node['resource_path'])
        if parent_node['resource_kind']!='directory' or str(folder) not in requested:return
        if folder.is_symlink():return
        try:
            _, children, more, _=snapshot(folder,limit=MAX_INLINE_ENTRIES)
        except (OSError,ResourceError,ValueError):return
        key=region_for(parent_node['id'])
        parent_node['child_region_key']=key
        parent_node['region_role']='directory'
        direct=[]
        for entry in children:
            if len(nodes)>=MAX_VISIBLE_NODES:break
            nid='resource:'+hashlib.sha256(os.fsencode(str(entry.path))).hexdigest()[:24]
            if any(item['id']==nid for item in nodes):continue
            kind=entry.kind
            icon='📁' if kind=='directory' else '🔗' if kind=='symlink' else '📄'
            suffix=entry.path.suffix.lower()
            capability=preview_kind(entry.path,entry.kind)
            child={'id':nid,'title':entry.label,'display_title':icon+'  '+entry.label,
                   'subtitle':kind,'kind':'resource','source_kind':'resource',
                   'resource_uri':entry.uri,'resource_path':str(entry.path),
                   'resource_kind':kind,'containing_scope':key,'preview_kind':capability,
                   'resource_preview':(expanded_file_preview(entry.path,capability)
                      if str(entry.path) in requested and capability!='none' else None),
                   'accent':'#7ac7e0' if kind=='directory' else '#e0ba78' if suffix=='.py' else '#7b91a6',
                   'draft_ports':{'inputs':[],'outputs':[]},'containers':[]}
            nodes.append(child);direct.append(child)
        # Source order in resource graphs is lexical filesystem order. A
        # compact grid is deterministic; it creates no invented data edges.
        cols=3
        for i,node in enumerate(direct):
            node['x']=12.+(i%cols)*(RESOURCE_COMPACT_WIDTH+16.)
            node['y']=12.+(i//cols)*(RESOURCE_COMPACT_HEIGHT+16.)
        for child in direct:
            if child['resource_kind']=='directory':attach_children(child,depth+1)
        # Nested folders use the same stable grid. Expanding a grandchild
        # overlays neighbors until the user chooses to arrange them.
        for i,child in enumerate(direct):
            child['x']=12.+(i%cols)*(RESOURCE_COMPACT_WIDTH+16.)
            child['y']=12.+(i//cols)*(RESOURCE_COMPACT_HEIGHT+16.)
        width=12.+min(cols,max(1,len(direct)))*(RESOURCE_COMPACT_WIDTH+16.)
        height=max(90.,max((child['y']+float(child.get('embedded_region',{}).get('height',RESOURCE_COMPACT_HEIGHT))+12.
                              for child in direct),default=90.))
        view_w=min(750.,max(235.,width))
        view_h=min(420.,max(100.,height))
        parent_node['embedded_region']={'scope':key,'role':'directory',
            'width':view_w+12.,'height':31.+view_h+6.,'surface_top':31.,
            'viewport_width':view_w,'viewport_height':view_h,
            'content_width':width,'content_height':height}
        if more:parent_node['subtitle']='Folder · first 18 entries shown; open to browse all'

    for root_node in tuple(nodes):
        if root_node['resource_kind']=='directory':attach_children(root_node,1)
    # Python files remain real resource nodes; the parser supplies a bounded
    # projection inside them only when the user explicitly expands them.
    source_documents=source_documents or {}
    for node in tuple(nodes):
        if (node['resource_kind']=='file' and node.get('preview_kind')=='python-graph'
                and node['resource_path'] in requested_expansions
                and not (node.get('resource_preview') or {}).get('status')):
            _attach_python_projection(node,nodes,edges,source_documents)
    # Source-independent positions: expanding a folder never pushes other
    # resources around. The selected composite is raised by the shared Qt
    # stacking policy and its internal viewport clips descendants. Manual
    # positions are overlaid by the owner canvas after this first layout.
    root_nodes=[node for node in nodes if not node.get('containing_scope')]
    cols=4
    for i,node in enumerate(root_nodes):
        node['x']=100.+(i%cols)*(RESOURCE_COMPACT_WIDTH+16.)
        node['y']=85.+(i//cols)*(RESOURCE_COMPACT_HEIGHT+18.)

    # Validate a focus against the visible snapshot even when its overlay is
    # temporarily hidden. Toggling visibility must not erase per-tab focus.
    visible_files={Path(n['resource_path']):n for n in nodes
                   if n.get('resource_kind')=='file'}
    focused=Path(relationship_focus).expanduser().absolute() if relationship_focus is not None else None
    if focused is not None:
        if focused not in visible_files or focused.is_symlink():
            raise ResourceError('Focused relationship file is not a visible regular file')
        try:parts=focused.relative_to(root).parts
        except ValueError as exc:raise ResourceError('Focused file escapes workspace') from exc
        cursor=root
        for part in parts:
            cursor=cursor/part
            if cursor.is_symlink():raise ResourceError('Focused file crosses a symlink')
    def in_focus(src,dst):
        if focused is None:return True
        if relationship_direction=='incoming':return dst==focused
        if relationship_direction=='outgoing':return src==focused
        return src==focused or dst==focused
    if show_imports:
        from .source_associations import local_python_imports, local_python_symbol_candidates, local_python_literal_files
        # Only already visible file cards participate; no recursive traversal.
        by_path={path:node for path,node in visible_files.items() if path.suffix.lower()=='.py'}
        # Use current SourceDocumentSession revisions when available. This is
        # transient evidence, not a second copy of source owned by resources.
        active_text={Path(path):session.text for path,session in source_documents.items()
                     if Path(path) in visible_files}
        candidates=[]; symbols=[]; assets=[]
        for source_path in sorted(by_path)[:MAX_ENTRIES]:
            if 'imports' in layers:
                candidates.extend(local_python_imports(source_path,set(by_path),
                    source_texts=active_text,workspace_root=root))
                symbols.extend(local_python_symbol_candidates(source_path,set(by_path),
                    source_texts=active_text,workspace_root=root))
            if 'references' in layers:
                assets.extend(local_python_literal_files(source_path,set(visible_files),
                    source_texts=active_text,workspace_root=root))
        symbols_by_pair={}
        for match in symbols:
            symbols_by_pair.setdefault((match.source,match.target),[]).append(match)
        # Multiple source statements may cite the same file. Keep a single
        # resource association wire with all exact source line provenance.
        by_pair={}
        for candidate in candidates:
            by_pair.setdefault((candidate.source,candidate.target),[]).append(candidate)
        for index,((src,dst),references) in enumerate(sorted(by_pair.items())):
            if not in_focus(src,dst):continue
            a=by_path[src];b=by_path[dst]
            out_id=a['id']+':outputs:imports:'+b['id']
            in_id=b['id']+':inputs:referenced:'+a['id']
            a['draft_ports']['outputs'].append({'id':out_id,'label':'import candidate',
                                                'type':'resource:module-candidate'})
            b['draft_ports']['inputs'].append({'id':in_id,'label':'referenced by',
                                               'type':'resource:module-candidate'})
            edges.append({'id':'resource-import:'+a['id']+':'+b['id'],
                'source':a['id'],'sourcePort':out_id,
                'target':b['id'],'targetPort':in_id,'relation':'imports',
                'certainty':'local-file-candidate',
                'provenance':([{'source':str(ref.source),'line':ref.line,
                                'syntax':ref.evidence} for ref in references] +
                              [{'source':str(match.target),'line':match.declaration_line,
                                'syntax':f'{match.declaration_kind} {match.symbol} (syntactic declaration match)'}
                               for match in symbols_by_pair.get((src,dst),())[:12]])})
        by_asset_pair={}
        for ref in assets:by_asset_pair.setdefault((ref.source,ref.target),[]).append(ref)
        for (src,dst),references in sorted(by_asset_pair.items()):
            if not in_focus(src,dst):continue
            a=by_path.get(src)
            b=visible_files.get(dst)
            if a is None or b is None:continue
            out_id=a['id']+':outputs:literal:'+b['id']
            in_id=b['id']+':inputs:literal:'+a['id']
            a['draft_ports']['outputs'].append({'id':out_id,'label':'literal path',
                                               'type':'resource:path-candidate'})
            b['draft_ports']['inputs'].append({'id':in_id,'label':'referenced by',
                                              'type':'resource:path-candidate'})
            edges.append({'id':'resource-literal:'+a['id']+':'+b['id'],
                'source':a['id'],'sourcePort':out_id,'target':b['id'],'targetPort':in_id,
                'relation':'reference','certainty':'literal-path-candidate',
                'provenance':[{'source':str(ref.source),'line':ref.line,'syntax':ref.evidence}
                              for ref in references]})
    relationship_limit_reached=bool(show_imports and len(by_path)>MAX_ENTRIES) if show_imports else False
    return {'scope':'resource:'+root.as_uri(),'title':str(root),
            'origin':'resource','nodes':nodes,'edges':edges,'path':str(root),
            'associations_enabled':bool(show_imports),'relationship_layers':sorted(layers) if show_imports else [],
            'relationship_focus':str(focused) if focused is not None else None,
            'relationship_direction':relationship_direction,'presentation':'composite',
            'truncated':truncated,'has_previous':previous,'offset':offset,
            'warnings':(['Some entries not displayed; use a narrower directory.'] if truncated else [])+\
                        (['Relationship sources capped at 72 visible Python files.'] if relationship_limit_reached else [])}
