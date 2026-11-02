"""Language-agnostic deterministic presentation layout.

Coordinates are derived from node source-order hints and existing graph edges.
No semantic operations or connections are created, changed, or removed.
One graph surface owns one call; never layout a parent and child together.
"""
from collections import defaultdict
import heapq


def node_size(node):
    info=node.get('embedded_region')
    if info:
        return float(info['width']),float(info['height'])
    kind=node.get('source_kind','')
    count=max(len(node['draft_ports']['inputs']),len(node['draft_ports']['outputs']))
    width=155.0 if (kind in {'param','capture','global','literal','operation','compare','loop_test','return'} or node.get('visual_family')=='operator_assignment') else 225.0
    return width,max(55.0,37.0+count*24.0)


def source_line(node):
    span=node.get('source_span') or {}
    return int(span.get('line',0) or 0)


def arrange(nodes,edges,*,root=False):
    """Arrange nodes within one graph, returning the bounding content extent.

    Root: declarations form one legible vertical rail, executable/module sites
    go on a second rail. Children: source-line rows and in-row dependency
    order; this keeps AST structure visible without pretending to execute it.
    """
    visible=[n for n in nodes if not n.get('presentation_hidden')]
    for n in nodes:
        if n.get('presentation_hidden'):n['x']=n['y']=0.0
    if not visible:return 215.,88.
    nodes=visible
    pad=9. if root else 25.
    gap_x=18.;gap_y=12.
    index={node['id']:node for node in nodes}
    predecessors=defaultdict(set)
    for e in edges:
        if e['source'] in index and e['target'] in index and e['source']!=e['target']:
            predecessors[e['target']].add(e['source'])
    ordered=sorted(enumerate(nodes),key=lambda pair:(source_line(pair[1]),pair[0]))
    if root:
        declarations=[n for _,n in ordered if n.get('source_scope')]
        others=[n for _,n in ordered if not n.get('source_scope')]
        left=declarations if declarations else others
        right=others if declarations else []
        x_left=pad
        x_right=pad+max(node_size(n)[0] for n in left)+72.
        y=pad
        for node in left:
            node['x']=x_left;node['y']=y
            y+=node_size(node)[1]+gap_y
        # Center the module's executable entry points by the declarations they
        # actually reference; source order is the stable fallback.
        y_next=pad
        for node in right:
            linked=[index[nid] for nid in predecessors[node['id']] if nid in index and nid!=node['id']]
            hint=(sum(n['y']+node_size(n)[1]*.5 for n in linked)/len(linked)
                  if linked else y_next)
            node['x']=x_right;node['y']=max(y_next,hint)
            y_next=node['y']+node_size(node)[1]+gap_y
    else:
        rows=defaultdict(list)
        for _,node in ordered:rows[source_line(node)].append(node)
        y=pad
        for line in sorted(rows):
            group=rows[line]
            # A same-line expression may contain a *chain* of operators.
            # Sorting by predecessor count alone isn't topological (a+b+c
            # could put a consumer ahead of its producer). A stable Kahn
            # traversal respects actual value connections while preserving
            # source order for independent nodes. Cycles use source order as a
            # conservative fallback; they aren't interpreted as operations.
            ids={node['id'] for node in group}
            original={node['id']:i for i,node in enumerate(group)}
            outgoing=defaultdict(set)
            incoming={nid: set(predecessors[nid] & ids) for nid in ids}
            for nid,dependencies in incoming.items():
                for parent in dependencies:outgoing[parent].add(nid)
            ready=[(original[nid],nid) for nid in ids if not incoming[nid]]
            heapq.heapify(ready)
            chosen=[]
            while ready:
                _,nid=heapq.heappop(ready)
                chosen.append(nid)
                for successor in outgoing[nid]:
                    incoming[successor].discard(nid)
                    if not incoming[successor]:
                        heapq.heappush(ready,(original[successor],successor))
            chosen.extend(sorted((nid for nid in ids if nid not in chosen), key=original.__getitem__))
            by_id={n['id']:n for n in group}
            x=pad;row_h=0.
            # One extremely long expression shouldn't expand every enclosing
            # viewport to an unreadable strip. Wrap the *presentation* at a
            # bounded row width; do not create semantic nodes or change edges.
            max_row_width=990.
            for nid in chosen:
                node=by_id[nid]
                w,h=node_size(node)
                if x>pad and x+w>max_row_width:
                    y+=row_h+gap_y
                    x=pad;row_h=0.
                node['x']=x;node['y']=y
                x+=w+gap_x;row_h=max(row_h,h)
            y+=row_h+gap_y
    return (max(n['x']+node_size(n)[0] for n in nodes)+pad,
            max(n['y']+node_size(n)[1] for n in nodes)+pad)
