"""Readable view projection of the Python source-analysis graph.

The Python AST and PythonDocument.scope_graph() are authoritative for source
identity/analysis. This module is a *pure, disposable view*: no interpreter,
no alternate variable table, no source mutation, and no presentation-only
operations claiming to execute. Opaque/uncertain analysis is retained when it
cannot safely be simplified. See docs/V10-READABILITY-ARCHITECTURE.md.
"""
from __future__ import annotations

import ast
import copy


def _source_nodes(scope):
    """Return source statements by location without descending nested defs."""
    result = {}
    class Scan(ast.NodeVisitor):
        def visit_FunctionDef(self, node):
            if node is scope.ast_node:
                for item in node.body: self.visit(item)
            else:
                # A nested def binds its name in this scope, but its body
                # belongs to a different scope and must not be traversed.
                result[(node.lineno,node.col_offset)] = node
        visit_AsyncFunctionDef = visit_FunctionDef
        def visit_ClassDef(self, node):
            if node is scope.ast_node:
                for item in node.body: self.visit(item)
        def visit_While(self, node):
            result[(node.lineno,node.col_offset)] = node
            for item in (*node.body,*node.orelse):self.visit(item)
        def visit_For(self,node):
            result[(node.lineno,node.col_offset)] = node
            for item in (*node.body,*node.orelse):self.visit(item)
        visit_AsyncFor = visit_For
        def visit_AugAssign(self,node):
            result[(node.lineno,node.col_offset)] = node
        def generic_visit(self,node):
            if isinstance(node,ast.stmt):result[(node.lineno,node.col_offset)]=node
            super().generic_visit(node)
    Scan().visit(scope.ast_node)
    return result


def _written_names(stmt):
    """Names that this statement itself can bind in the current lexical scope.

    This is intentionally conservative and handles source assignments that
    aren't lowered into graph nodes (e.g. tuple unpacking and imports). It
    never scans nested function/class/comprehension bodies.
    """
    targets=[]
    if isinstance(stmt,ast.Assign):
        targets=stmt.targets
    elif isinstance(stmt,ast.AnnAssign):
        if stmt.value is not None:targets=[stmt.target]
    elif isinstance(stmt,ast.AugAssign):
        targets=[stmt.target]
    elif isinstance(stmt,(ast.For,ast.AsyncFor)):
        targets=[stmt.target]
    elif isinstance(stmt,(ast.With,ast.AsyncWith)):
        targets=[item.optional_vars for item in stmt.items if item.optional_vars]
    elif isinstance(stmt,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
        return {stmt.name}
    elif isinstance(stmt,(ast.Import,ast.ImportFrom)):
        return {name.asname or (name.name.split('.')[0] if isinstance(stmt,ast.Import)
                                 else name.name) for name in stmt.names if name.name!='*'}
    names=set()
    for target in targets:
        names.update(n.id for n in ast.walk(target) if isinstance(n,ast.Name) and
                     isinstance(n.ctx,ast.Store))
    return names


def _ports(node, direction):
    return node['draft_ports'][direction]


def _pin(node,direction,suffix):
    return next((p for p in _ports(node,direction) if p['id'].endswith(':'+suffix)),None)


def _node_kind(node):
    return node.get('source_kind','')


def _reference_source(name, nodes, *, before_line=None):
    """One source binding, not a claimed stable *value version*.

    Parameters and closure bindings have stable symbol identity for this
    view. For local variables, a unique preceding assignment is eligible as
    a binding reference, but the edge must remain labeled 'reference'.
    """
    for role,prefix in (('param','PARAMETER '),('capture','CAPTURE '),('global','GLOBAL READ ')):
        for node in nodes:
            if _node_kind(node)==role and node['title']==prefix+name:
                p=_pin(node,'outputs','value')
                if p:return node,p
    # Binding identity is semantic metadata, NEVER a UI title convention.
    # The original analysis IR retains value versions; the readable reference
    # only identifies the symbol, not the value from the first assignment.
    candidates=[(node,_pin(node,'outputs','value')) for node in nodes
                if _node_kind(node)=='assignment' and
                node.get('binding_name')==name and
                node.get('binding_write_mode')=='initial']
    candidates=[x for x in candidates if x[1] is not None and
                (before_line is None or (x[0].get('source_span') or {}).get('line',10**9)<before_line)]
    if candidates:
        return min(candidates,key=lambda pair:(pair[0].get('source_span') or {}).get('line',10**9))
    # A for-loop target has an actual per-iteration binding defined by the
    # loop header; do not invent a separate READ item or LOOP VALUE node.
    for node in nodes:
        if _node_kind(node)!='loop':continue
        line=(node.get('source_span') or {}).get('line',10**9)
        if before_line is not None and line>before_line:continue
        p=next((p for p in _ports(node,'outputs') if p['id'].endswith(':item') and p['label']==name),None)
        if p:return node,p
    return None,None


def _edge(source,port,target,target_port,kind='reference'):
    return {'id':'view:'+source+':'+port+':'+target+':'+target_port,
            'source':source,'sourcePort':port,'target':target,
            'targetPort':target_port,'relation':kind}


def readable_scope_graph(doc,scope,analysis):
    """Create a concise source-backed graph without mutating analysis data."""
    g=copy.deepcopy(analysis)
    if scope.kind!='function':
        g['presentation']='readable'
        return g
    source_by_span=_source_nodes(scope)
    nodes=g['nodes'];edges=g['edges']
    by_id={n['id']:n for n in nodes}
    removed=set()
    added_edges=[]
    consumed=set()

    # A named assignment is a real variable binding, not a second operation
    # called SET. Distinguish an eligible first straight-line local assignment
    # from reassignments. This classification is purely a view of the AST;
    # Python itself has no separate local-variable declaration statement.
    # Nested/conditional first writes are NOT asserted to initialize a name
    # on every execution path.
    source_statements=sorted(source_by_span.values(),key=lambda st:(st.lineno,st.col_offset))
    args=scope.ast_node.args
    parameters={arg.arg for arg in (*args.posonlyargs,*args.args,*args.kwonlyargs)}
    if args.vararg: parameters.add(args.vararg.arg)
    if args.kwarg: parameters.add(args.kwarg.arg)
    direct_stmts={id(stmt) for stmt in scope.ast_node.body}
    assignment_nodes={(n['source_span']['line'],n['source_span']['col'],n['binding_name']):n
                      for n in nodes if _node_kind(n)=='assignment' and
                      n.get('binding_statement_kind')=='assign' and
                      n.get('binding_name') and n.get('source_span')}
    seen_writes=set(parameters)
    for stmt in source_statements:
        if (isinstance(stmt,(ast.Assign,ast.AnnAssign)) and
                (not isinstance(stmt,ast.AnnAssign) or stmt.value is not None)):
            targets=stmt.targets if isinstance(stmt,ast.Assign) else [stmt.target]
            for target in targets:
                if not isinstance(target,ast.Name):continue
                name=target.id
                node=assignment_nodes.get((stmt.lineno,stmt.col_offset,name))
                if node is None:continue
                symbol=None
                try:
                    if scope.table: symbol=scope.table.lookup(name)
                except KeyError:pass
                first=(name not in seen_writes and id(stmt) in direct_stmts and
                       not (symbol and (symbol.is_global() or symbol.is_nonlocal())))
                node['binding_write_mode']='initial' if first else 'reassign'
                if first:
                    node['title']=name
                    node['visual_family']='variable'
                    node['binding_display_role']='local variable initialization'
                    node['subtitle']='Initial binding: '+(ast.get_source_segment(doc.source,stmt) or name)
                else:
                    node['binding_display_role']='variable reassignment'
        seen_writes.update(_written_names(stmt))

    # Constants are an authored value on the target port, not a separate
    # operation. Keep the target's original stable pin ID and original literal
    # span for direct editing and safe graph-to-source rewiring.
    for node in nodes:
        if _node_kind(node)!='literal':continue
        outgoing=[e for e in edges if e['source']==node['id']]
        if not outgoing or any(e.get('relation','data')!='data' for e in outgoing):continue
        span=node.get('source_span')
        if not span:continue
        # Literal node's row contains the exact authored Python token. Parse
        # its value only when it is a genuine Python literal, without eval().
        row=next((r for section in node.get('containers',[]) for r in section.get('rows',[])
                  if r.get('label')=='Value'),None)
        if row is None:continue
        text=str(row.get('value',''))
        try:
            value=ast.literal_eval(text)
        except (ValueError,SyntaxError,TypeError,MemoryError,RecursionError):continue
        if type(value) not in (int,float,str,bool,type(None)):continue
        candidates=[]
        for edge in outgoing:
            target=by_id.get(edge['target'])
            if not target:break
            port=next((p for p in _ports(target,'inputs') if p['id']==edge['targetPort']),None)
            if port is None:break
            candidates.append((port,edge))
        else:
            for port,edge in candidates:
                port['default']=value
                port['source_literal_span']=dict(span)
                port['source_literal_text']=text
                port['binding_mode']='source_literal'
                consumed.add(edge['id'])
            removed.add(node['id'])

    # A control-flow analysis may need an explicit ENTRY/EXIT helper. Those
    # are not Python statements; never put them on the normal authoring view.
    for node in nodes:
        if _node_kind(node) in ('entry','exit'):
            removed.add(node['id'])

    # Render all loop kinds using the same control-boundary contract: normal
    # body completion repeats implicitly; only explicit CONTINUE draws a
    # return-to-header edge. No extra statement/node is invented.
    for loop in nodes:
        if _node_kind(loop)!='loop':continue
        span=loop.get('source_span') or {}
        stmt=source_by_span.get((span.get('line'),span.get('col')))
        if isinstance(stmt,(ast.For,ast.AsyncFor)) and isinstance(stmt.target,ast.Name):
            loop['title']='FOR '+stmt.target.id
            loop['subtitle']='Iterate over '+(ast.get_source_segment(doc.source,stmt.iter) or 'iterable')
        repeat=_pin(loop,'inputs','repeat')
        execute=_pin(loop,'inputs','in')
        if repeat:
            for e in edges:
                if e['target']!=loop['id'] or e['targetPort']!=repeat['id']:continue
                source=by_id.get(e['source'])
                if source is not None and _node_kind(source)=='continue' and execute:
                    e['targetPort']=execute['id']
                    e['flow_role']='continue'
                else:
                    consumed.add(e['id'])
            _ports(loop,'inputs').remove(repeat)
        loop['presentation_repeat']='implicit_normal_completion'

    # The WHILE test's *source* is on the WHILE node. A TEST helper represents
    # per-iteration analysis, not a distinct operator written in Python.
    # Named reads become symbol references; they are NOT snapshot data wires.
    for loop in nodes:
        if _node_kind(loop)!='loop':continue
        span=loop.get('source_span') or {}
        stmt=source_by_span.get((span.get('line'),span.get('col')))
        if not isinstance(stmt,ast.While):continue
        loop['display_condition']=ast.get_source_segment(doc.source,stmt.test) or ast.unparse(stmt.test)
        loop['title']='WHILE '+loop['display_condition']
        loop['subtitle']='Check each iteration'
        loop['visual_family']='control'
        test_edge=next((e for e in edges if e['target']==loop['id'] and
                        e['targetPort'].endswith(':condition') and
                        _node_kind(by_id.get(e['source'],{}))=='loop_test'),None)
        if test_edge:
            removed.add(test_edge['source'])
            consumed.add(test_edge['id'])
            _ports(loop,'inputs')[:]=[p for p in _ports(loop,'inputs') if p['id']!=test_edge['targetPort']]
        reads={x.id for x in ast.walk(stmt.test) if isinstance(x,ast.Name) and
               isinstance(x.ctx,ast.Load)}
        for name in sorted(reads):
            origin,output=_reference_source(name,nodes,before_line=stmt.lineno)
            pid=loop['id']+':inputs:binding:'+name
            binding={'id':pid,'label':name,'type':output['type'] if output else 'py:unknown',
                     'binding_mode':'current_binding'}
            if origin is not None and output is not None:
                added_edges.append(_edge(origin['id'],output['id'],loop['id'],pid))
            else:
                binding['unresolved_binding']=True
            _ports(loop,'inputs').append(binding)
        loop['presentation_semantics']='condition evaluated at every loop iteration'

    # Internal phi/loop-carried nodes are used in analysis to avoid freezing a
    # pre-loop value. In the authoring view, route named reads to the symbol
    # with a DASHED reference edge. Never relabel these as data snapshots.
    for internal in nodes:
        if _node_kind(internal)!='loop_value':continue
        title=internal.get('title','')
        if title.startswith('LOOP VALUE '):name=title[len('LOOP VALUE '):]
        elif title.startswith('UNCERTAIN '):name=title[len('UNCERTAIN '):]
        else:continue
        at=(internal.get('source_span') or {}).get('line')
        origin,output=_reference_source(name,[n for n in nodes if n['id']!=internal['id']],before_line=at)
        for e in edges:
            if e['source']!=internal['id'] or e['target'] in removed:continue
            target=by_id.get(e['target'])
            if not target:continue
            port=next((p for p in _ports(target,'inputs') if p['id']==e['targetPort']),None)
            if not port:continue
            # A source-level name read is a real operation, not a Phi node.
            # Without a unique owner, show the name and uncertainty on the
            # receiving pin but NEVER invent a data edge or source version.
            port['label']=name
            port['binding_mode']='current_binding'
            if _node_kind(target)=='return':
                # `return value` already visibly names the current binding.
                # A long edge from the function parameter would misleadingly
                # suggest the *initial* value is returned after a mutation.
                port['inline_source_name']=name
            elif origin is not None and output is not None:
                added_edges.append(_edge(origin['id'],output['id'],target['id'],port['id']))
            else:
                port['unresolved_binding']=True
        removed.add(internal['id'])

    # Lower control joins as routing, not user-authored executable nodes.
    # Traverse chains of joins until a *real* destination. Doing this once
    # through a control adjacency avoids order-dependent broken edges when
    # nested conditionals have more than one consecutive join.
    joins={n['id'] for n in nodes if _node_kind(n)=='control_join'}
    control_by_source={}
    for edge in edges:
        if edge.get('relation')=='control':
            control_by_source.setdefault(edge['source'],[]).append(edge)
    def real_destinations(join_id, visited=None):
        visited=set() if visited is None else visited
        if join_id in visited:return []
        visited.add(join_id)
        result=[]
        for edge in control_by_source.get(join_id,[]):
            if edge['target'] in joins:
                result.extend(real_destinations(edge['target'],visited.copy()))
            else:result.append((edge['target'],edge['targetPort']))
        return result
    for edge in edges:
        if (edge.get('relation')!='control' or edge['target'] not in joins
                or edge['source'] in joins or edge['source'] in removed):continue
        for target,port in real_destinations(edge['target']):
            if target not in removed:
                added_edges.append(_edge(edge['source'],edge['sourcePort'],target,port,'control'))
    removed.update(joins)

    # A value merge is also version-analysis bookkeeping. Its consumers
    # read an authored variable name. Keep that name and path-dependence on
    # the receiving port, not a fabricated executable MERGE node.
    for helper in nodes:
        if _node_kind(helper)!='value_merge' or not helper['title'].startswith('MERGE '):continue
        name=helper['title'][len('MERGE '):]
        for edge in edges:
            if edge['source']!=helper['id'] or edge['target'] in removed:continue
            target=by_id.get(edge['target'])
            if target is None:continue
            p=next((p for p in _ports(target,'inputs') if p['id']==edge['targetPort']),None)
            if p is not None:
                p['label']=name
                p['binding_mode']='current_binding'
                p['path_dependent']=True
        removed.add(helper['id'])

    # Conditional control is an authored IF/ELIF statement, not an extra
    # programmer-authored BRANCH operation. Preserve source_kind='branch'
    # for the existing detailed analyzer and source-edit contracts; only the
    # readable presentation changes. The region projection below may expose
    # its actual body statements inside this same node.
    for node in nodes:
        if _node_kind(node)!='branch':continue
        span=node.get('source_span') or {}
        stmt=source_by_span.get((span.get('line'),span.get('col')))
        if not isinstance(stmt,ast.If):continue
        first_line=doc.source.splitlines()[stmt.lineno-1].lstrip()
        keyword='ELIF' if first_line.startswith('elif ') else 'IF'
        condition=ast.get_source_segment(doc.source,stmt.test) or ast.unparse(stmt.test)
        node['title']=keyword+' '+condition
        node['display_title']=keyword.lower()+' '+condition+':'
        node['visual_family']='conditional'
        node['source_construct']='conditional'
        node['semantic_role']='control_operation'
        node['conditional_branches']=('true','false')

    # A LOOP is also a control operation. Its body may be shown in a child
    # viewport, but that viewport is never a second authored loop/macro.
    for node in nodes:
        if _node_kind(node)!='loop':continue
        node['semantic_role']='control_operation'
        node['source_construct']='loop'

    # An UPDATE is a real augmented assignment; the same source statement
    # already expresses the operator and target. Do not invent a standalone
    # arithmetic or previous-value operation for `value -= 2`.
    for node in nodes:
        if _node_kind(node)!='assignment':continue
        span=node.get('source_span') or {}
        stmt=source_by_span.get((span.get('line'),span.get('col')))
        if isinstance(stmt,ast.AugAssign) and isinstance(stmt.target,ast.Name):
            operation={ast.Add:'+=',ast.Sub:'-=',ast.Mult:'*=',ast.Div:'/=',
                       ast.FloorDiv:'//=',ast.Mod:'%=',ast.Pow:'**=',
                       ast.BitAnd:'&=',ast.BitOr:'|=',ast.BitXor:'^=',
                       ast.LShift:'<<=',ast.RShift:'>>=',ast.MatMult:'@='}
            symbol=operation.get(type(stmt.op))
            # The compact operation shows the OPERATOR, not an additional
            # variable-named SET. Binding identity stays on the named input
            # pin and its (reference) edge to the source variable.
            node['title']=symbol or 'UPDATE'
            node['display_symbol']=symbol or 'UPDATE'
            node['source_construct']='augmented_assignment'
            node['semantic_role']='binding_write'
            node['binding_name']=stmt.target.id
            node['binding_write_mode']='update'
            node['visual_family']='operator_assignment'
            node['subtitle']=ast.get_source_segment(doc.source,stmt) or ast.unparse(stmt)
            prior=_pin(node,'inputs','previous')
            if prior:
                prior['label']=stmt.target.id
                prior['binding_mode']='current_binding'
                # A named current-binding reference is not a frozen value
                # snapshot, even when the detailed analyzer had a concrete
                # value producer for straight-line flow.
                for ref_edge in edges:
                    if ref_edge['target']==node['id'] and ref_edge['targetPort']==prior['id']:
                        if ref_edge.get('relation')=='data':
                            ref_edge['relation']='reference'
            right=_pin(node,'inputs','operand')
            if right:right['label']='operand'

    # Some nodes are discarded as presentation artifacts. A diagnostic graph
    # remains available through scope_graph(), with its exact original edges.
    nodes[:]=[n for n in nodes if n['id'] not in removed]
    remaining={n['id'] for n in nodes}
    edges[:]=[e for e in edges if e['id'] not in consumed and
              e['source'] in remaining and e['target'] in remaining]
    existing={(e['source'],e['sourcePort'],e['target'],e['targetPort']) for e in edges}
    for e in added_edges:
        # Join bypassing can discover an implicit loop repeat after its port
        # was suppressed. Apply the SAME loop-boundary projection to these
        # derived edges; never reintroduce a dangling presentation pin.
        target=by_id.get(e['target'])
        if (target and target.get('presentation_repeat')=='implicit_normal_completion'
                and e['targetPort'].endswith(':repeat')):
            source=by_id.get(e['source'])
            if source and _node_kind(source)=='continue':
                execute=_pin(target,'inputs','in')
                if not execute:continue
                e['targetPort']=execute['id']
                e['flow_role']='continue'
            else:continue
        key=(e['source'],e['sourcePort'],e['target'],e['targetPort'])
        if e['source'] in remaining and e['target'] in remaining and key not in existing:
            edges.append(e);existing.add(key)

    # Compact readable layout: declarations on left, control regions center,
    # body statements to the right, and successive statements below. This is
    # only presentation state, never a second execution ordering model.
    counts={}
    wired_values={e['target'] for e in edges if e.get('relation','data')=='data'}
    for n in nodes:
        kind=_node_kind(n)
        # Place source bindings / inline literals on the left, calculations
        # and control nodes in the middle, assignment targets to their right,
        # and returns last. This is the same scope graph, not a new layout IR.
        # The connected three-stage "a, b -> + -> c" case stays readable.
        lane=(0 if kind in ('param','capture','global','variable','maybe-unbound local') or
                    (n.get('binding_write_mode')=='initial' and n['id'] not in wired_values) else
              1 if kind in ('loop','branch','nested','operation','compare') else
              2 if kind in ('assignment','break','continue','pass','call','opaque') else 3)
        rank=counts.get(lane,0);counts[lane]=rank+1
        n['x']=(85,420,770,1100)[lane]
        n['y']=120+rank*(92 if lane==0 else 160)
        n['presentation']='source_statement' if n.get('source_span') else 'source_binding'
    g['presentation']='readable'
    g['internal_analysis_node_count']=len(analysis['nodes'])
    g['warnings']=list(dict.fromkeys([*g.get('warnings',[]),
        'Dashed variable references identify the current binding; they are not frozen runtime values.']))
    return g
