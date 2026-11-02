"""Read-only Python AST/symbol-table projection into Native Node Lab view data.

The .py file is authoritative. This adapter never imports or executes it.
It generates transient nodes/edges for the existing Qt renderer; source
editing lives separately in python_edit.py. Python types are *not* i32/u32:
Python ints are arbitrary precision, annotations are not runtime guarantees.
"""
from __future__ import annotations
import ast
import hashlib
import symtable
from dataclasses import dataclass
from pathlib import Path

MAX_SOURCE = 1_500_000
MAX_VIEW_NODES = 220
MAX_DEPTH = 24


class SourceError(ValueError):
    pass


def decode_python_source(raw: bytes) -> tuple[str, str]:
    """Decode source once using Python's declared-encoding rules, without parsing.

    Incomplete Python documents are still legitimate text documents. Keep
    decoding independent from AST qualification so the editor can retain them.
    """
    import io, tokenize
    if not isinstance(raw, bytes):
        raise SourceError('Expected Python source bytes')
    if len(raw) > MAX_SOURCE:
        raise SourceError('File exceeds 1.5 MB analysis limit')
    try:
        encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
        return raw.decode(encoding), encoding
    except (SyntaxError, UnicodeError, LookupError, ValueError) as exc:
        raise SourceError(f'Python source decoding failed: {exc}') from exc


def _identifier(prefix, *parts):
    return prefix + ':' + '|'.join(str(x) for x in parts)


def _short(s, limit=100):
    return s[:limit] + ('…' if len(s) > limit else '')


def _ann(expr):
    if expr is None:
        return 'py:unknown'
    try:
        t = ast.unparse(expr)
    except (TypeError, ValueError):
        return 'py:unknown'
    return {'int': 'py:int', 'str': 'py:str', 'float': 'py:float',
            'bool': 'py:bool', 'None': 'py:None'}.get(t, f'py:{_short(t, 36)}')


def _type(expr, types=None):
    if isinstance(expr, ast.Constant):
        v = expr.value
        if v is None: return 'py:None'
        if type(v) is bool: return 'py:bool'
        if type(v) is int: return 'py:int'
        if type(v) is float: return 'py:float'
        if type(v) is str: return 'py:str'
        if type(v) is bytes: return 'py:bytes'
    if isinstance(expr, ast.Name):
        return (types or {}).get(expr.id, 'py:unknown')
    if isinstance(expr, ast.BinOp):
        a, b = _type(expr.left, types), _type(expr.right, types)
        if a == b and a in ('py:int', 'py:float') and not isinstance(expr.op, ast.Div):
            return a
        if a == b == 'py:str' and isinstance(expr.op, ast.Add):
            return 'py:str'
        if isinstance(expr.op, ast.Div) and a in ('py:int','py:float') and b in ('py:int','py:float'):
            return 'py:float'
    if isinstance(expr, ast.Compare):return 'py:bool'
    if isinstance(expr, ast.BoolOp):
        # Python and/or return an operand, not necessarily a bool.
        types_={_type(v,types) for v in expr.values}
        return next(iter(types_)) if len(types_)==1 else 'py:unknown'
    if isinstance(expr, ast.UnaryOp):return 'py:bool' if isinstance(expr.op, ast.Not) else _type(expr.operand, types)
    return 'py:unknown'


def _signature(node):
    args = node.args
    result = []
    for a in (*args.posonlyargs, *args.args, *args.kwonlyargs):
        result.append((a.arg, _ann(a.annotation)))
    if args.vararg:result.append(('*' + args.vararg.arg, _ann(args.vararg.annotation)))
    if args.kwarg:result.append(('**' + args.kwarg.arg, _ann(args.kwarg.annotation)))
    return result, _ann(node.returns)


def _symbols(table):
    if table is None:return [], []
    try:
        values = table.get_symbols()
    except AttributeError:
        return [], []
    frees = [s.get_name() for s in values if s.is_free()]
    globals_ = [s.get_name() for s in values if s.is_global() and s.is_referenced()]
    return sorted(frees), sorted(globals_)


def _runtime_reads(statement_body):
    """Names read by executable statements in a scope, excluding nested bodies.

    Annotations/decorators/defaults have their own evaluation phases and must
    not be presented as function-body data inputs. Dynamic reads are not
    inferred by this static visitor.
    """
    found=set()
    class Reads(ast.NodeVisitor):
        def visit_Name(self, node):
            if isinstance(node.ctx, ast.Load):found.add(node.id)
        def visit_FunctionDef(self, node):pass
        def visit_AsyncFunctionDef(self, node):pass
        def visit_ClassDef(self, node):pass
        def visit_Lambda(self, node):pass
        def visit_AnnAssign(self, node):
            if node.value is not None:self.visit(node.value)
        def visit_arg(self, node):pass
    visitor=Reads()
    for statement in statement_body:visitor.visit(statement)
    return found


OPERATOR_NAMES = {
    ast.Add: '+', ast.Sub: '−', ast.Mult: '×', ast.Div: '÷',
    ast.FloorDiv: '//', ast.Mod: '%', ast.Pow: '**',
    ast.BitAnd: '&', ast.BitOr: '|', ast.BitXor: '^',
    ast.LShift: '<<', ast.RShift: '>>', ast.MatMult: '@',
    ast.Eq: '==', ast.NotEq: '!=', ast.Lt: '<', ast.LtE: '<=',
    ast.Gt: '>', ast.GtE: '>=', ast.Is: 'is', ast.IsNot: 'is not',
    ast.In: 'in', ast.NotIn: 'not in', ast.USub: '−',
    ast.UAdd: '+', ast.Invert: '~', ast.Not: 'not',
}


def _loop_body_writes(statements):
    """Bindings written in this function scope, not nested definitions.

    A nested def/class binds its own NAME in the current scope; its body
    belongs to another scope. Comprehension targets are likewise local to
    the comprehension and must not invent loop-carried function locals.
    """
    class Visitor(ast.NodeVisitor):
        def __init__(self): self.names=set()
        def visit_Name(self,node):
            if isinstance(node.ctx,(ast.Store,ast.Del)):self.names.add(node.id)
        def visit_FunctionDef(self,node):self.names.add(node.name)
        def visit_AsyncFunctionDef(self,node):self.names.add(node.name)
        def visit_ClassDef(self,node):self.names.add(node.name)
        def visit_Lambda(self,node):pass
        def visit_ListComp(self,node):pass
        def visit_SetComp(self,node):pass
        def visit_DictComp(self,node):pass
        def visit_GeneratorExp(self,node):pass
        def visit_ExceptHandler(self,node):
            if node.name:self.names.add(node.name)
            for statement in node.body:self.visit(statement)
    visitor=Visitor()
    for statement in statements:visitor.visit(statement)
    return visitor.names


def _child_table(table, node):
    if table is None:return None
    for child in table.get_children():
        if child.get_lineno() == node.lineno and child.get_name() == node.name:
            return child
    return None


def _source_label(source, node, default='source'):
    value = ast.get_source_segment(source, node) or default
    return _short(' '.join(value.split()), 110)


def _row(label, value, id_):
    return {'id': id_, 'kind':'label', 'label':_short(str(label),35), 'value':_short(str(value),180), 'tags':[]}


def _node(id_, title, kind, subtitle, x, y, *, inputs=(), outputs=(), rows=(), accent='#2fc9f0', source=None, scope=None):
    data = {'id':id_, 'kind':kind, 'title':_short(title,45), 'subtitle':_short(subtitle,65),
            'accent':accent, 'x':float(x), 'y':float(y),
            'draft_ports':{'inputs':[], 'outputs':[]},
            'containers':[{'id':id_+':detail', 'title':'SOURCE DETAILS',
                           'collapsed':False, 'page':0, 'visible_rows':7, 'rows':list(rows)}],
            'source_kind':kind, 'source_scope':scope}
    for direction, values in (('inputs',inputs),('outputs',outputs)):
        for label,typ,key in values:
            data['draft_ports'][direction].append({'id':f'{id_}:{direction}:{key}', 'label':label,'type':typ})
    if source is not None:
        data['source_span']={'line':source.lineno, 'col':source.col_offset,
                             'end_line':source.end_lineno,'end_col':source.end_col_offset}
    return data


@dataclass
class Scope:
    key: str
    title: str
    kind: str
    parent: str | None
    ast_node: object
    table: object
    children: list[str]


@dataclass(frozen=True)
class SourceSymbol:
    """Read-only navigation target; never a qualified source creation action."""
    kind: str
    name: str
    scope: str
    line: int
    column: int


@dataclass
class LoopContext:
    """The nearest enclosing Python loop's explicit control destinations.

    This is analysis state, NOT a graph node or a runtime interpreter.
    Break and continue bind to this context and remain ordinary statements.
    """
    node_id: str
    repeat_input: str
    break_input: str
    break_count: int = 0
    continue_count: int = 0


class PythonDocument:
    """One Python parser/projection for either disk bytes or an in-memory revision.

    In-memory snapshots are analysis-only: they neither read the current source
    file nor modify it. Saving remains the separate guarded edit transaction.
    """
    def __init__(self, path: str | Path):
        self.path=self._validated_path(path)
        if self.path.stat().st_size > MAX_SOURCE:
            raise SourceError('File exceeds 1.5 MB analysis limit')
        self._parse_bytes(self.path.read_bytes())

    @classmethod
    def from_bytes(cls, path: str | Path, raw: bytes) -> 'PythonDocument':
        """Parse an unsaved revision using the same AST and symbol-table owner.

        Keep the original absolute file identity for routes and diagnostics.
        An invalid revision raises SourceError without changing the file.
        """
        document=cls.__new__(cls)
        document.path=cls._validated_path(path)
        document._parse_bytes(raw)
        return document

    @staticmethod
    def _validated_path(path: str | Path) -> Path:
        original=Path(path).expanduser()
        if original.is_symlink():raise SourceError('Symlink source paths are not supported')
        resolved=original.resolve(strict=True)
        if not resolved.is_file():
            raise SourceError('Select a regular Python file, not a symlink')
        if resolved.suffix.lower() != '.py':raise SourceError('Expected a .py file')
        return resolved

    def _parse_bytes(self, raw: bytes) -> None:
        if not isinstance(raw,bytes):raise SourceError('Expected Python source bytes')
        if len(raw)>MAX_SOURCE:raise SourceError('File exceeds 1.5 MB analysis limit')
        self.raw=raw
        self.sha256=hashlib.sha256(raw).hexdigest()
        try:
            self.source,self.encoding=decode_python_source(raw)
        except SourceError as exc:
            raise SourceError(f'Python analysis failed: {exc}') from exc
        # No imports, dynamic evaluation, or user-source execution occurs.
        try:
            self.tree=ast.parse(self.source, filename=str(self.path),type_comments=True)
            self.symtab=symtable.symtable(self.source,str(self.path),'exec')
        except (SyntaxError,IndentationError,UnicodeError,LookupError,ValueError) as exc:
            raise SourceError(f'Python analysis failed: {exc}') from exc
        self.scopes={}
        self.scopes['module']=Scope('module',self.path.name,'module',None,self.tree,self.symtab,[])
        self._index(self.tree,'module',self.symtab,0)

    def _index(self, container, parent, table, depth):
        if depth >= MAX_DEPTH:return
        for item in getattr(container,'body',[]):
            if isinstance(item,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
                kind = 'class' if isinstance(item,ast.ClassDef) else 'function'
                key=f'{parent}/{kind}:{item.name}:{item.lineno}:{item.col_offset}'
                child=Scope(key,item.name,kind,parent,item,_child_table(table,item),[])
                self.scopes[key]=child;self.scopes[parent].children.append(key)
                self._index(item,key,child.table,depth+1)

    def browse_symbols(self, *, limit=350) -> tuple[SourceSymbol, ...]:
        """Describe lexical definitions and bindings already owned by this parser.

        Symbol tables determine *whether* a name is local; the original AST
        supplies its first binding location. Comprehension and nested scopes
        must not leak names into the containing function. This inventory is
        for navigation only, not a Python type/execution or creation catalog.
        """
        if not isinstance(limit,int) or isinstance(limit,bool) or limit<1:
            raise ValueError('Symbol browser limit must be a positive integer')
        result=[]
        for key, scope in self.scopes.items():
            if key!='module':
                node=scope.ast_node
                result.append(SourceSymbol(scope.kind,scope.title,key,
                                           node.lineno,node.col_offset))
                if len(result)>=limit:break
            bindings={}
            class BindingLocations(ast.NodeVisitor):
                def visit_Name(self,node):
                    if isinstance(node.ctx,ast.Store):
                        bindings.setdefault(node.id,(node.lineno,node.col_offset))
                def visit_arg(self,node):
                    bindings.setdefault(node.arg,(node.lineno,node.col_offset))
                def visit_FunctionDef(self,node):pass
                def visit_AsyncFunctionDef(self,node):pass
                def visit_ClassDef(self,node):pass
                def visit_Lambda(self,node):pass
                def visit_ListComp(self,node):pass
                def visit_SetComp(self,node):pass
                def visit_DictComp(self,node):pass
                def visit_GeneratorExp(self,node):pass
            visitor=BindingLocations()
            if scope.kind=='function':
                # Parameters belong to this scope, unlike its own definition.
                for arg in (*scope.ast_node.args.posonlyargs,*scope.ast_node.args.args,
                            *scope.ast_node.args.kwonlyargs):
                    visitor.visit(arg)
                if scope.ast_node.args.vararg:visitor.visit(scope.ast_node.args.vararg)
                if scope.ast_node.args.kwarg:visitor.visit(scope.ast_node.args.kwarg)
            for statement in scope.ast_node.body:visitor.visit(statement)
            if scope.table is None:continue
            for symbol in scope.table.get_symbols():
                name=symbol.get_name()
                if (name not in bindings or symbol.is_imported() or
                        not (symbol.is_parameter() or
                             (symbol.is_assigned() and symbol.is_local() and
                              not symbol.is_namespace()))):
                    continue
                line,col=bindings[name]
                kind='parameter' if symbol.is_parameter() else 'variable'
                result.append(SourceSymbol(kind,name,key,line,col))
                if len(result)>=limit:break
            if len(result)>=limit:break
        return tuple(result)

    def scope_graph(self,key='module'):
        if key not in self.scopes:raise SourceError('Unknown source scope')
        return self._module_graph() if key == 'module' else self._body_graph(self.scopes[key])

    @staticmethod
    def _bounded_module_call(call):
        """Can the view prove direct-call evaluation order without missing effects?

        Dynamic dispatch is *never* proven, even here. This only qualifies
        ordering: a direct-name callee and plain values or recursively direct
        positional/keyword calls. Opaque attribute lookup, unpacking,
        generators and arbitrary expressions stay outside modeled exec flow.
        """
        if not isinstance(call,ast.Call) or not isinstance(call.func,ast.Name):
            return False
        def simple(expr):
            if isinstance(expr,(ast.Constant,ast.Name)):return True
            if (isinstance(expr,ast.UnaryOp) and isinstance(expr.op,(ast.UAdd,ast.USub))
                    and isinstance(expr.operand,ast.Constant) and
                    type(expr.operand.value) in (int,float,complex)):
                return True
            return PythonDocument._bounded_module_call(expr) if isinstance(expr,ast.Call) else False
        return (all(simple(arg) for arg in call.args) and
                all(kw.arg is not None and simple(kw.value) for kw in call.keywords))

    def _module_graph(self):
        nodes=[];edges=[];variables={};definitions={}
        for item in self.tree.body:
            if len(nodes)>=MAX_VIEW_NODES:break
            ix=len(nodes);x=140+(ix%3)*485;y=110+(ix//3)*245
            if isinstance(item,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
                is_func = not isinstance(item,ast.ClassDef)
                params,ret=_signature(item) if is_func else ([], 'py:object')
                child_key=next((c for c in self.scopes['module'].children if self.scopes[c].ast_node is item),None)
                frees,glob=_symbols(self.scopes[child_key].table if child_key else None)
                if is_func:
                    direct_reads=_runtime_reads(item.body)
                    glob=[name for name in glob if name in direct_reads and name!='__name__']
                inputs=[(n,t,n) for n,t in params] + [(f'env: {n}','py:unknown','env:'+n) for n in glob if n!='__name__']
                outputs=[('return',ret,'result'),('callable','py:callable','callable')] if is_func else [('class','py:object','class')]
                kind='function' if is_func else 'class'
                rows=[_row('Signature',_source_label(self.source,item).split(':')[0],_identifier('row',ix,'sig')),
                      _row('Scope',kind,_identifier('row',ix,'scope'))]
                if glob:rows.append(_row('Global reads',', '.join(glob),_identifier('row',ix,'globals')))
                n=_node(_identifier('py',kind,item.name,item.lineno),item.name.upper(),kind,
                        'Double-click to enter definition' if child_key else 'Declaration',x,y,
                        inputs=inputs,outputs=outputs,rows=rows,
                        accent='#8aa7ff' if is_func else '#b38bec',source=item,scope=child_key)
                n['semantic_role']='definition'
                nodes.append(n);definitions[item.name]=n
            elif isinstance(item,(ast.Assign,ast.AnnAssign)):
                targets=item.targets if isinstance(item,ast.Assign) else [item.target]
                value=item.value
                for target in targets:
                    if not isinstance(target,ast.Name):continue
                    typ=_ann(item.annotation) if isinstance(item,ast.AnnAssign) else _type(value)
                    id_=_identifier('py','global',target.id,item.lineno)
                    rows=[_row('Value',_source_label(self.source,value) if value else 'uninitialized',id_+':v'),
                          _row('Scope','module global',id_+':s')]
                    n=_node(id_,target.id, 'variable','Module binding',x,y,
                        outputs=[('value',typ,'value')],rows=rows,accent='#e8ad62',source=item)
                    nodes.append(n);variables[target.id]=n
            elif isinstance(item,(ast.Import,ast.ImportFrom)):
                label='import ' + (item.module or '') if isinstance(item,ast.ImportFrom) else 'import'
                id_=_identifier('py','import',item.lineno)
                names=', '.join(a.name for a in item.names)
                nodes.append(_node(id_,label,'import',names,x,y,
                    outputs=[('module','py:module','module')],
                    rows=[_row('Source',_source_label(self.source,item),id_+':r')],
                    accent='#67c49e',source=item))
            elif isinstance(item,(ast.Expr,ast.If,ast.For,ast.While,ast.Try,ast.With,ast.AsyncFor,ast.AsyncWith)):
                id_=_identifier('py','top',item.lineno)
                # Call links will be derived from the syntax in a second pass.
                label=('IF '+_source_label(self.source,item.test)+':' if isinstance(item,ast.If)
                       else type(item).__name__.upper())
                called=sorted({call.func.id for call in ast.walk(item) if isinstance(call,ast.Call) and isinstance(call.func,ast.Name)})
                # Only a simple suite of direct call statements is lowered
                # to a module-level Branch. Unsupported suites stay opaque:
                # a visual True wire must never skip unknown source effects.
                simple_guard=(isinstance(item,ast.If) and not item.orelse and
                              bool(item.body) and all(isinstance(st,ast.Expr) and
                              self._bounded_module_call(st.value) for st in item.body))
                inputs=[(f'calls {name}','py:callable','call:'+name) for name in called[:16]]
                outputs=[]
                if simple_guard:
                    inputs=[('condition','py:bool','predicate'),('flow','execution','in')]+inputs
                    outputs=[('True','execution','true'),('False','execution','false')]
                n=_node(id_,label,'branch' if simple_guard else 'opaque','Source-backed; inspect before editing',x,y,
                    inputs=inputs,outputs=outputs,
                    rows=[_row('Source',_source_label(self.source,item),id_+':r')],source=item,accent='#b39d83')
                if simple_guard:
                    n['source_construct']='conditional'
                    n['semantic_role']='control_operation'
                    n['source_guard_test']=_source_label(self.source,item.test)
                    n['draft_ports']['inputs'][0]['source_expression_preview']=n['source_guard_test']
                nodes.append(n)
        # Actual module-level call expressions, including calls inside IF
        # bodies and RHS expressions of assignments. The AST owns identity;
        # the separate call node is a real source construct, not a compiler
        # bookkeeping operation or an assertion of runtime dispatch.
        class ModuleCalls(ast.NodeVisitor):
            def __init__(self):self.matches=[]
            def visit_Call(self,call):
                self.matches.append(call);self.generic_visit(call)
            def visit_FunctionDef(self,stmt):pass
            visit_AsyncFunctionDef=visit_FunctionDef
            def visit_ClassDef(self,stmt):pass
            def visit_Lambda(self,stmt):pass
        for statement in self.tree.body:
            if isinstance(statement,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
                continue
            calls=ModuleCalls();calls.visit(statement)
            owner_id=(_identifier('py','top',statement.lineno)
                if isinstance(statement,(ast.Expr,ast.If,ast.For,ast.While,ast.Try,
                                         ast.With,ast.AsyncFor,ast.AsyncWith)) else None)
            produced={}
            for call in calls.matches[:32]:
                if len(nodes)>=MAX_VIEW_NODES:break
                name=(call.func.id if isinstance(call.func,ast.Name) else
                      _source_label(self.source,call.func))
                cid=_identifier('py','module','call',call.lineno,call.col_offset,
                                 call.end_lineno,call.end_col_offset)
                n=_node(cid,'CALL '+_short(name,28),'call',
                    _source_label(self.source,call),0,0,
                    inputs=[('flow','execution','exec-in'),('callable','py:callable','callable')]+
                           [(f'arg {i+1}',_type(arg),f'arg:{i}') for i,arg in enumerate(call.args)]+
                           [(f'kw {kw.arg}' if kw.arg else 'kw **',_type(kw.value),f'kw:{i}')
                            for i,kw in enumerate(call.keywords)],
                    outputs=[('result','py:unknown','result'),('next','execution','exec-out')],
                    rows=[_row('Source',_source_label(self.source,call),cid+':src'),
                          _row('Evaluation','Arguments evaluated in Python source order',cid+':evaluation')],
                    source=call,accent='#57bfa6')
                n.update(call_expression=True,semantic_role='invocation',
                         effect_verification='unverified',
                         call_direct_name=name if isinstance(call.func,ast.Name) else None,
                         enclosing_statement_id=owner_id,containing_scope='module')
                # Every syntactic argument has one stable input identity. The
                # source expression is a preview, NOT a proven data binding.
                # Only a direct nested Call gets a source-backed value edge.
                for i,arg in enumerate(call.args):
                    port=next(p for p in n['draft_ports']['inputs'] if p['id'].endswith(':arg:'+str(i)))
                    port['source_expression_preview']=_source_label(self.source,arg)
                    if isinstance(arg,ast.Constant):
                        port['source_literal_text']=_source_label(self.source,arg)
                        port['binding_mode']='source_literal'
                        port['default']=arg.value
                    elif not isinstance(arg,ast.Call):
                        port['unresolved_binding']=True
                for i,kw in enumerate(call.keywords):
                    port=next(p for p in n['draft_ports']['inputs'] if p['id'].endswith(':kw:'+str(i)))
                    port['source_expression_preview']=_source_label(self.source,kw.value)
                    if isinstance(kw.value,ast.Constant):
                        port['source_literal_text']=_source_label(self.source,kw.value)
                        port['binding_mode']='source_literal';port['default']=kw.value.value
                    elif not isinstance(kw.value,ast.Call):
                        port['unresolved_binding']=True
                nodes.append(n);produced[id(call)]=n
            # AST-directed dependencies. These are exact expression evaluation
            # relationships; they do NOT assert that calls are pure or that
            # dynamic Python names resolve to a particular function.
            for outer in calls.matches:
                parent=produced.get(id(outer))
                if parent is None:continue
                previous=None
                for kind,ix,arg in ([('arg',i,a) for i,a in enumerate(outer.args)]+
                                    [('kw',i,k.value) for i,k in enumerate(outer.keywords)]):
                    if not isinstance(arg,ast.Call) or id(arg) not in produced:continue
                    child=produced[id(arg)]
                    pid=parent['id']+':inputs:'+kind+':'+str(ix)
                    edges.append(self._edge(child['id'],child['id']+':outputs:result',
                                            parent['id'],pid,'data'))
                    if previous is not None and self._bounded_module_call(outer):
                        # Only bounded direct nested call arguments are
                        # sequenced. Complex non-call arguments remain opaque.
                        edges.append(self._edge(previous['id'],previous['id']+':outputs:exec-out',
                                                child['id'],child['id']+':inputs:exec-in','control'))
                    previous=child
                if previous is not None and self._bounded_module_call(outer):
                    edges.append(self._edge(previous['id'],previous['id']+':outputs:exec-out',
                                            parent['id'],parent['id']+':inputs:exec-in','control'))
            # Sequential module expression-statements in an explicit suite:
            # their direct outer calls follow source order. A conditional's
            # guard is retained as a distinct source-backed owner; we never
            # invent an execution edge from an opaque predicate.
            suite=(statement.body if isinstance(statement,ast.If) else [statement])
            previous=None
            guard=next((n for n in nodes if n['id']==owner_id and
                       n.get('semantic_role')=='control_operation'),None)
            for statement_expr in suite:
                if not isinstance(statement_expr,ast.Expr) or not self._bounded_module_call(statement_expr.value):
                    previous=None;continue
                call_node=produced.get(id(statement_expr.value))
                if call_node is None:previous=None;continue
                # Reach the earliest direct nested argument call before the
                # outer call. All visible control edges follow exact AST
                # evaluation ordering; complex arguments are left unmodeled.
                first=statement_expr.value
                while True:
                    nested=next((a for a in first.args if isinstance(a,ast.Call)
                                 and id(a) in produced),None)
                    if nested is None:break
                    first=nested
                begin=produced.get(id(first),call_node)
                if previous is not None:
                    edges.append(self._edge(previous['id'],previous['id']+':outputs:exec-out',
                                            begin['id'],begin['id']+':inputs:exec-in','control'))
                elif guard is not None:
                    edges.append(self._edge(guard['id'],guard['id']+':outputs:true',
                                            begin['id'],begin['id']+':inputs:exec-in','control'))
                previous=call_node

            # A direct call used to initialize a module binding is a real
            # value input to that binding. Don't invent a new SET operation.
            rhs=(statement.value if isinstance(statement,(ast.Assign,ast.AnnAssign)) else None)
            if isinstance(rhs,ast.Call) and id(rhs) in produced:
                targets=statement.targets if isinstance(statement,ast.Assign) else [statement.target]
                for target in targets:
                    if not isinstance(target,ast.Name):continue
                    binding=variables.get(target.id)
                    if binding is None:continue
                    pid=binding['id']+':inputs:initializer'
                    if not any(p['id']==pid for p in binding['draft_ports']['inputs']):
                        binding['draft_ports']['inputs'].append({'id':pid,
                            'label':'value','type':'py:unknown'})
                    producer=produced[id(rhs)]
                    edges.append(self._edge(producer['id'],producer['id']+':outputs:result',
                                            binding['id'],pid,'data'))
        # Call expressions previously all appeared at (0, 0). Give each
        # source statement its own visible evaluation row and place nested
        # invocations to the LEFT of their consuming call. Pure presentation;
        # stable source IDs and adapter-owned edges remain unchanged.
        module_calls=[n for n in nodes if n.get('call_expression')]
        if module_calls:
            base_y=max((n['y'] for n in nodes if not n.get('call_expression')),default=110)+280
            lines=sorted({n['source_span']['line'] for n in module_calls})
            for n in module_calls:
                own=n['source_span']
                enclosing=sum(1 for outer in module_calls if outer is not n and
                    outer['source_span']['line'] <= own['line'] <= outer['source_span']['end_line'] and
                    outer['source_span']['col'] < own['col'] and
                    (outer['source_span']['end_line'] > own['end_line'] or
                     outer['source_span']['end_col'] > own['end_col']))
                n['x']=1040-min(enclosing,3)*350
                n['y']=base_y+lines.index(own['line'])*270
                n['presentation_call_depth']=enclosing
            # Keep an explicit module guard near the calls it controls,
            # instead of drawing it over the function definition row.
            for n in nodes:
                if n.get('semantic_role')=='control_operation' and n['id'].startswith('py:top|'):
                    first=next((c for c in module_calls if c.get('enclosing_statement_id')==n['id']),None)
                    if first is not None:
                        n['x']=140;n['y']=first['y']-110

        # Reference edges between module values and functions reading globals.
        for n in nodes:
            if n['source_kind']!='function':continue
            for p in n['draft_ports']['inputs']:
                if not p['id'].split(':inputs:')[-1].startswith('env:'):continue
                name=p['id'].split('env:',1)[-1]
                var=variables.get(name)
                if var:
                    edges.append(self._edge(var['id'],var['draft_ports']['outputs'][0]['id'],n['id'],p['id'],'reference'))
        for n in nodes:
            # Top-level calls are exact syntax references, not sequential flow.
            if n['source_kind'] in ('opaque','branch'):
                for port in n['draft_ports']['inputs']:
                    key=port['id'].split(':inputs:')[-1]
                    if not key.startswith('call:'):continue
                    definition=definitions.get(key[5:])
                    if definition:
                        output=definition['draft_ports']['outputs'][-1]
                        edges.append(self._edge(definition['id'],output['id'],n['id'],port['id'],'call'))
        # Exact syntactic call-site references to local definitions. Dynamic
        # rebinding means these edges must not be interpreted as proven
        # runtime dispatch; the GUI does not draw them as value/execution wires.
        for call_node in [n for n in nodes if n.get('call_expression')]:
            definition=definitions.get(call_node.get('call_direct_name'))
            if definition is None:continue
            callable_port=next((p for p in definition['draft_ports']['outputs']
                                if p['label']=='callable'),None)
            if callable_port is None:continue
            link=self._edge(definition['id'],callable_port['id'],
                            call_node['id'],call_node['id']+':inputs:callable','call')
            link['certainty']='syntactic-name-match'
            link['provenance']=[{'source':str(self.path),
                'line':call_node['source_span']['line'],
                'syntax':call_node.get('subtitle','')}]
            edges.append(link)
        # Transitive nested global reads are shown as qualified dependencies
        # of a containing function, never as direct reads/parameter inputs.
        for n in nodes:
            if n['source_kind'] != 'function' or not n.get('source_scope'):continue
            scope=n['source_scope']
            descendants=[key for key in self.scopes if key.startswith(scope+'/')]
            transitive=set()
            for key in descendants:
                nested=self.scopes[key]
                if nested.kind != 'function':continue
                _,globals_=_symbols(nested.table)
                transitive.update(set(globals_) & _runtime_reads(nested.ast_node.body))
            for name in sorted(transitive):
                var=variables.get(name)
                if not var:continue
                pin={'id':n['id']+':inputs:transitive:'+name,'label':'nested reads '+name,'type':'py:unknown'}
                n['draft_ports']['inputs'].append(pin)
                e=self._edge(var['id'],var['draft_ports']['outputs'][0]['id'],n['id'],pin['id'],'reference')
                e['indirect']=True;edges.append(e)
        return {'scope':'module','title':self.path.name,'nodes':nodes,'edges':edges,
                'warnings':['Solid call edges indicate source-level callable references; dashed reference edges can be indirect.',
                            'Annotations are not inferred to be runtime value reads.',
                            'Opening source never executes module statements.',
                            'Module execution wiring is limited to AST-ordered direct calls; unknown dispatch remains unverified.']}

    def presentation_graph(self, key='module', *, detail='readable'):
        """Generate a disposable presentation of one authoritative analysis."""
        analysis=self.scope_graph(key)
        if detail=='analysis' or key=='module':return analysis
        if detail!='readable':raise SourceError('Unknown Python presentation detail')
        from .python_presentation import readable_scope_graph
        return readable_scope_graph(self,self.scopes[key],analysis)

    def whole_file_graph(self, expanded=None, *, max_nodes=240, detail='analysis'):
        """One read-only projection with source scopes as separate visual lanes.

        Containment is drawn by frames, never invented as executable edges.
        Expansion is UI state and does not change the program or its graph IDs.
        Each expanded scope has the same internal edges as its focused view.
        """
        if expanded is None:
            expanded=set(self.scopes)-{'module'}
        else:
            expanded=set(expanded)
        unknown=expanded-set(self.scopes)
        if unknown:raise SourceError('Unknown expanded scope')
        # Descendants cannot be shown if their ancestor is collapsed.
        expanded={k for k in expanded if all(parent in expanded for parent in self._ancestors(k))}
        module=self._module_graph()
        nodes=[dict(n) for n in module['nodes']]
        edges=[dict(e) for e in module['edges']]
        groups=[]
        root_end=max((n['y'] for n in nodes),default=0)+235
        groups.append({'scope':'module','label':self.path.name+' · module',
                       'x':55,'y':65,'w':1625,'h':max(240,root_end-55),'depth':0})
        y=root_end+135
        warnings=list(module['warnings'])
        truncated=False
        for key,scope in self.scopes.items():
            if key=='module' or key not in expanded:continue
            projection=self.presentation_graph(key,detail=detail)
            scoped=projection['nodes']
            if len(nodes)+len(scoped)>max_nodes:
                truncated=True
                break
            # Use a bounded column grid based on role. This is a presentation
            # layout, not a second program representation or an edge-order model.
            buckets={k:0 for k in range(5)}
            for node in scoped:
                kind=node.get('source_kind')
                col=(0 if kind in ('param','capture','global','variable','loop_value') else
                     1 if kind in ('literal','nested') else
                     2 if kind in ('operation','compare','call','opaque','loop_test') else
                     3 if kind in ('assignment','branch','loop','break','continue','pass') else 4)
                ix=buckets[col];buckets[col]+=1
                node['x']=150+col*300
                node['y']=y+85+ix*126
                node['containing_scope']=key
            height=max(230,120+max(buckets.values(),default=0)*126)
            breadcrumb=' / '.join(self.scopes[parent].title for parent in reversed(list(self._ancestors(key))))
            label=(breadcrumb+' / ' if breadcrumb else '')+scope.title
            groups.append({'scope':key,'label':label+'  ·  '+scope.kind+
                           '  ['+str(len(scoped))+' nodes]',
                           'x':82,'y':y+25,'w':1550,'h':height,'depth':key.count('/')})
            nodes.extend(scoped);edges.extend(projection['edges'])
            warnings.extend(projection.get('warnings',[]))
            y+=height+110
        if truncated:
            warnings.append(f'Whole-file visualization capped at {max_nodes} nodes. Collapse scopes to see others.')
        # Where an external binding has one unambiguous source, connect the
        # whole-file environment read to its owner. This *reference* wire does
        # not expose a new callable parameter or imply execution sequencing.
        declarations={}
        for node in nodes:
            scope_key=node.get('containing_scope','module')
            if node['source_kind'] not in ('variable','param','assignment','capture','global'):
                continue
            for output in node['draft_ports']['outputs']:
                name=node['title'] if node['source_kind']=='variable' else output['label']
                declarations.setdefault((scope_key,name),[]).append((node,output))
        for node in nodes:
            if node['source_kind'] not in ('capture','global') or not node.get('containing_scope'):
                continue
            scope_key=node['containing_scope']
            # Anchor title is generated by _body_graph, not user-authored text.
            prefix='CAPTURE ' if node['source_kind']=='capture' else 'GLOBAL READ '
            if not node['title'].startswith(prefix):continue
            name=node['title'][len(prefix):]
            if node['source_kind']=='global':
                owners=['module']
            else:
                owners=list(self._ancestors(scope_key))
                parent=self.scopes[scope_key].parent
                if parent and parent!='module':owners=[parent]+[x for x in owners if x!=parent]
            for owner in owners:
                candidates=declarations.get((owner,name),[])
                if len(candidates)!=1:continue
                declaration,output=candidates[0]
                port_id=node['id']+':inputs:environment'
                node['draft_ports']['inputs'].append({'id':port_id,'label':'from '+name,'type':output['type']})
                edges.append(self._edge(declaration['id'],output['id'],node['id'],port_id,'reference'))
                break
        ids={node['id'] for node in nodes}
        edges=[e for e in edges if e['source'] in ids and e['target'] in ids]
        return {'scope':'whole','title':self.path.name+' · Whole File',
                'nodes':nodes,'edges':edges,'scope_regions':groups,
                'warnings':list(dict.fromkeys(warnings))}

    def composite_file_graph(self, expanded=None, *, max_nodes=240, detail='readable', collapsed_regions=None, focus_scope=None):
        """One semantic graph, recursively projected through reusable regions.

        Language adapters select which source constructs own child regions;
        their surface, ownership and port rendering are entirely generic Qt.
        Neither nodes nor edges are synthesized for containment or layout.
        """
        from .graph_layout import arrange
        # Focus changes the ROOT of the SAME recursive source presentation,
        # never which operation/branch/loop model an adapter emits. A focused
        # function has no enclosing definition card, so its PARAMETER and
        # RETURN operations remain visible instead of boundary-folded.
        if focus_scope is None:
            graph=self.whole_file_graph(expanded,max_nodes=max_nodes,detail=detail)
            root_scope='module'
        else:
            if focus_scope not in self.scopes:
                raise SourceError('Focus needs an existing lexical scope')
            graph=self.presentation_graph(focus_scope,detail=detail)
            if len(graph['nodes']) > max_nodes:
                raise SourceError('Focused source graph exceeds the visible node limit')
            # This local ownership is only view containment, never lexical scope.
            for node in graph['nodes']:
                node['containing_scope']=focus_scope
            root_scope=focus_scope
            expanded={focus_scope} if focus_scope != 'module' else set()
        graph['presentation']='composite'
        graph['scope_regions']=[]
        nodes=graph['nodes'];edges=graph['edges']
        collapsed_regions=set(collapsed_regions or ())
        owners={n['source_scope']:n for n in nodes if n.get('source_scope')}
        # Branch and loop are ordinary source-backed control operations in
        # their lexical function graph, not presentation containers.  Their
        # True/False and Body/Completed pins already carry the adapter's
        # verified control paths.  Body statements retain their existing
        # source identities and flow edges in that same function surface.
        # `collapsed_regions` is accepted for migration of old saved view
        # preferences but cannot suppress operations or change this model.
        # Python module guards remain conservatively source-backed opaque
        # statements until the module adapter qualifies their branch edges.
        # An expanded function already has the same parameter at its graph
        # boundary. Keep the PARAMETER symbol/edge IDs in analysis, but use the
        # boundary as the visible source instead of drawing a duplicate card.
        for node in nodes:
            if node.get('source_kind')!='param':continue
            owner=owners.get(node.get('containing_scope'))
            if owner is None or not owner.get('source_scope'):continue
            output=next(iter(node['draft_ports']['outputs']),None)
            if output and any(p['label']==output['label'] for p in owner['draft_ports']['inputs']):
                node['presentation_hidden']=True
        # A simple terminal `return value` is the function's EXISTING output
        # boundary. Keep its exact source-backed node and data edges in the
        # analysis graph; the readable projection uses the matching boundary
        # port instead of a redundant full RETURN card.
        for scope_key, scope in self.scopes.items():
            if scope.kind != 'function' or scope_key not in owners:
                continue
            if not scope.ast_node.body or not isinstance(scope.ast_node.body[-1], ast.Return):
                continue
            # A return nested in an if/loop is an early exit, even when the
            # function ends with another return. Never fold that situation
            # into a single boundary output in the readable projection.
            returns=[n for n in nodes if n.get('source_kind')=='return'
                     and n['id'].startswith('py:'+scope_key+'|return|')]
            if len(returns)!=1:
                continue
            ret=returns[0]
            if ret.get('containing_scope')!=scope_key:
                continue
            span=ret.get('source_span') or {}
            last=scope.ast_node.body[-1]
            if span.get('line')!=last.lineno or span.get('col')!=last.col_offset:
                continue
            owner=owners[scope_key]
            if not any(p['label']=='return' for p in owner['draft_ports']['outputs']):
                continue
            ret['presentation_hidden']=True
            ret['terminal_boundary_owner']=scope_key
            owner['terminal_return_span']=span
            owner['terminal_return_label']='return'+(' '+_source_label(self.source,last.value) if last.value else '')

        # Canonical exits: a function's normal-return boundary consists of
        # control completion AND an optional value channel. These describe a
        # single semantic exit, not a duplicated RETURN node or two new edges.
        # IF/FOR/WHILE regions have their own control outputs; a RETURN inside
        # any such region still targets its enclosing FUNCTION boundary.
        for scope_key, scope in self.scopes.items():
            if scope.kind!='function' or scope_key not in owners:continue
            owner=owners[scope_key]
            return_port=next((p['id'] for p in owner['draft_ports']['outputs']
                              if p.get('label')=='return'),None)
            sites=[n for n in nodes if n.get('source_kind')=='return' and
                   n['id'].startswith('py:'+scope_key+'|return|')]
            sites.sort(key=lambda n:(n.get('source_span') or {}).get('line',0))
            for site in sites:
                site['exit_target_owner']=owner['id']
                site['exit_kind']='return'
            owner['graph_interface']={
                'category':'function',
                'inputs':[p['id'] for p in owner['draft_ports']['inputs']],
                'outputs':[p['id'] for p in owner['draft_ports']['outputs']],
                'exits':[{'id':owner['id']+':normal_return', 'kind':'return',
                          'value_port':return_port,'control_port':None,
                          'sites':[site['id'] for site in sites]}]}
        # Control interfaces are intrinsic to the operation.  Expansion,
        # collapse and focus MUST NOT control whether the interface exists.
        for node in nodes:
            kind=node.get('source_kind')
            if kind not in ('branch','loop'):continue
            if node.get('graph_interface'):continue
            outputs=node['draft_ports']['outputs']
            exit_kinds=('true','false') if kind=='branch' else ('body','completed')
            declared=[]
            for port in outputs:
                label=port.get('label','').lower()
                if label in exit_kinds:
                    declared.append({'id':node['id']+':'+label,
                                     'kind':label if label in ('true','false','body') else 'normal',
                                     'control_port':port['id'],'value_port':None,'sites':[]})
            node['graph_interface']={
                'category':'conditional' if kind=='branch' else 'loop',
                'inputs':[p['id'] for p in node['draft_ports']['inputs']],
                'outputs':[p['id'] for p in outputs],
                'exits':declared}
        children={}
        for node in nodes:
            children.setdefault(node.get('containing_scope','module'),[]).append(node)

        def layout(scope,stack):
            if scope in stack:raise SourceError('Recursive visual ownership detected')
            direct=children.get(scope,[])
            for node in direct:
                subkey=node.get('child_region_key') or node.get('source_scope')
                if subkey and subkey!=scope and subkey in children:
                    layout(subkey,stack | {scope})
            scope_ids={n['id'] for n in direct}
            local_edges=[e for e in edges if e['source'] in scope_ids and e['target'] in scope_ids]
            content_w,content_h=arrange(direct,local_edges,root=(scope=='module' and focus_scope is None))
            if scope!='module':
                owner=owners.get(scope)
                if owner is not None:
                    count=max(len(owner['draft_ports']['inputs']),len(owner['draft_ports']['outputs']))
                    # All pins remain on the OUTER node boundary, with inner
                    # port mirrors on the child surface. No vertical pin band.
                    surface_top=31.0
                    max_h=max(88.,24.0*count+24.)
                    view_w=min(810.,max(220.,content_w))
                    view_h=min(425.,max(max_h,content_h))
                    owner['embedded_region']={
                        'scope':scope,
                        'role':owner.get('region_role','definition'),
                        'width':view_w+12.,
                        'height':surface_top+view_h+6.,
                        'surface_top':surface_top,
                        'viewport_width':view_w,
                        'viewport_height':view_h,
                        'content_width':content_w,
                        'content_height':content_h,
                    }
                    if owner.get('source_scope') and owner.get('source_span'):
                        line_no=owner['source_span']['line']
                        source_line=self.source.splitlines()[line_no-1].strip()
                        # Show useful signature inline, not repeated SOURCE
                        # DETAILS. Full text remains in the inspector/tooltip.
                        owner['display_title']=source_line.split('#',1)[0].strip()
                    elif owner.get('region_role') in ('loop_body','conditional_body'):
                        line_no=(owner.get('source_span') or {}).get('line')
                        if line_no:
                            owner['display_title']=self.source.splitlines()[line_no-1].strip()
            return content_w,content_h

        layout(root_scope,set())
        for node in nodes:node['presentation_density']='compact'
        return graph

    def _ancestors(self, key):
        ancestor=self.scopes[key].parent
        while ancestor is not None and ancestor!='module':
            yield ancestor
            ancestor=self.scopes[ancestor].parent

    @staticmethod
    def _edge(a,p,b,q,kind='data'):
        return {'id':_identifier('edge',a,p,b,q,kind), 'source':a,'sourcePort':p,
                'target':b,'targetPort':q,'relation':kind}

    def _body_graph(self,scope):
        if scope.kind=='class':return self._class_graph(scope)
        node=scope.ast_node
        nodes=[];edges=[];bindings={};known={};control_prev=None
        params,ret=_signature(node)
        free,glob=_symbols(scope.table)
        live_reads=_runtime_reads(node.body)
        env_names=sorted((set(free+glob) & live_reads)-{n.replace('*','') for n,_ in params})
        def add(n):
            if len(nodes)>=MAX_VIEW_NODES:raise SourceError('Function graph exceeds 220 nodes; use a smaller scope')
            nodes.append(n);return n
        arg_nodes=[*node.args.posonlyargs,*node.args.args,*node.args.kwonlyargs]
        if node.args.vararg:arg_nodes.append(node.args.vararg)
        if node.args.kwarg:arg_nodes.append(node.args.kwarg)
        parameter_source={arg.arg:arg for arg in arg_nodes}
        def anchor(name,typ,role,idx):
            id_=_identifier('py',scope.key,role,name)
            title={'param':'PARAMETER','capture':'CAPTURE','global':'GLOBAL READ'}.get(role,role.upper())
            n=add(_node(id_,title+' '+name,role,'Source binding',75,105+idx*175,
                        outputs=[(name,typ,'value')],rows=[_row('Variable',name,id_+':n'),
                           _row('Source',role,id_+':s')],accent='#e5ac61',
                        source=parameter_source.get(name) if role=='param' else None))
            bindings[name]=(id_,n['draft_ports']['outputs'][0]['id'],typ)
            known[name]=typ
        for ix,(name,typ) in enumerate(params):anchor(name.replace('*',''),typ,'param',ix)
        for ix,name in enumerate(env_names,len(params)):
            anchor(name,'py:unknown','capture' if name in free else 'global',ix)

        # Expression builder emits exact operand/value edges; unsupported
        # expression shapes stay source-backed and opaque, never approximated.
        column=0;line=0
        def expr_id(role,expr):
            # Nested AST expressions may share (lineno,col_offset):
            # ((a + b) + c) and (a + b) start at the same token. Full spans
            # keep separate operations distinct while remaining source-stable.
            return _identifier('py',scope.key,role,expr.lineno,expr.col_offset,
                               expr.end_lineno,expr.end_col_offset)
        def expression(expr,depth=0):
            nonlocal column,line
            if depth>MAX_DEPTH:raise SourceError('Expression nesting too deep')
            if isinstance(expr,ast.Name) and isinstance(expr.ctx,ast.Load):
                if expr.id in bindings:return bindings[expr.id]
                role='global'
                if scope.table is not None:
                    try:
                        symbol=scope.table.lookup(expr.id)
                        if symbol.is_local():role='maybe-unbound local'
                        elif symbol.is_free():role='capture'
                    except KeyError:pass
                anchor(expr.id,known.get(expr.id,'py:unknown'),role,len(bindings))
                return bindings[expr.id]
            if isinstance(expr,ast.Constant):
                id_=expr_id('constant',expr)
                typ=_type(expr)
                text=_source_label(self.source,expr)
                n=add(_node(id_,'LITERAL', 'literal',text,440+column*345,120+line*148,
                    outputs=[('value',typ,'value')],rows=[_row('Value',text,id_+':value'),
                     _row('Python type',typ,id_+':type')],accent='#d1aa78',source=expr))
                line+=1
                return n['id'],n['draft_ports']['outputs'][0]['id'],typ
            if isinstance(expr,ast.BinOp):
                l=expression(expr.left,depth+1);r=expression(expr.right,depth+1)
                op=type(expr.op).__name__
                typ=_type(expr,known)
                id_=expr_id('binary',expr)
                n=add(_node(id_,op.upper(),'operation',_source_label(self.source,expr),770+column*345,150+line*140,
                    inputs=[('A',l[2],'lhs'),('B',r[2],'rhs')],outputs=[('result',typ,'result')],
                    rows=[_row('Expression',_source_label(self.source,expr),id_+':expr')],source=expr))
                n['visual_family']='operator';n['display_symbol']=OPERATOR_NAMES.get(type(expr.op),op)
                edges.extend([self._edge(l[0],l[1],id_,n['draft_ports']['inputs'][0]['id']),
                              self._edge(r[0],r[1],id_,n['draft_ports']['inputs'][1]['id'])])
                line+=1;return id_,n['draft_ports']['outputs'][0]['id'],typ
            if isinstance(expr,ast.Compare) and len(expr.ops)==1:
                lhs=expression(expr.left,depth+1);rhs=expression(expr.comparators[0],depth+1)
                op=type(expr.ops[0]).__name__;id_=expr_id('compare',expr)
                n=add(_node(id_,op.upper(),'compare',_source_label(self.source,expr),770+column*345,160+line*140,
                    inputs=[('A',lhs[2],'lhs'),('B',rhs[2],'rhs')],outputs=[('bool','py:bool','result')],
                    rows=[_row('Expression',_source_label(self.source,expr),id_+':expr')],source=expr,accent='#dc788a'))
                n['visual_family']='operator';n['display_symbol']=OPERATOR_NAMES.get(type(expr.ops[0]),op)
                for source,port in zip((lhs,rhs),n['draft_ports']['inputs']):
                    edges.append(self._edge(source[0],source[1],id_,port['id']))
                line+=1;return id_,n['draft_ports']['outputs'][0]['id'],'py:bool'
            if isinstance(expr,ast.UnaryOp) and isinstance(expr.op,(ast.Not,ast.USub,ast.UAdd,ast.Invert)):
                operand=expression(expr.operand,depth+1)
                id_=expr_id('unary',expr)
                typ=_type(expr,known)
                n=add(_node(id_,type(expr.op).__name__.upper(),'operation',_source_label(self.source,expr),770,180+line*140,
                    inputs=[('operand',operand[2],'operand')],outputs=[('result',typ,'result')],
                    rows=[_row('Expression',_source_label(self.source,expr),id_+':expr')],source=expr))
                n['visual_family']='operator';n['display_symbol']=OPERATOR_NAMES[type(expr.op)]
                edges.append(self._edge(operand[0],operand[1],id_,n['draft_ports']['inputs'][0]['id']))
                line+=1;return id_,n['draft_ports']['outputs'][0]['id'],typ
            if isinstance(expr,(ast.BoolOp,ast.IfExp)) or (isinstance(expr,ast.Compare) and len(expr.ops)>1):
                # Cannot turn lazy operands or chained comparisons into eagerly
                # evaluated independent wires without changing Python behavior.
                id_=expr_id('lazy-expr',expr)
                n=add(_node(id_,type(expr).__name__.upper(),'opaque',_source_label(self.source,expr),770,180+line*140,
                    outputs=[('result',_type(expr,known),'result')],
                    rows=[_row('Source',_source_label(self.source,expr),id_+':expr'),
                          _row('Evaluation','Ordered / short-circuit: source-backed',id_+':note')],source=expr,
                    accent='#ad9480'))
                line+=1;return id_,n['draft_ports']['outputs'][0]['id'],_type(expr,known)
            if isinstance(expr,ast.Call):
                # Python evaluates positional arguments followed by keyword
                # VALUES in lexical order. Their values are distinct typed
                # inputs, not anonymous details hidden inside CALL.
                args=[expression(a,depth+1) for a in expr.args]
                keywords=[expression(kw.value,depth+1) for kw in expr.keywords]
                name=_source_label(self.source,expr.func)
                callee=(bindings.get(expr.func.id) if isinstance(expr.func,ast.Name) else None)
                id_=expr_id('call',expr)
                call_inputs=([('callee','py:callable','callee')] if callee and callee[2]=='py:callable' else [])
                positional=[(f'arg {i+1}',v[2],f'arg{i}') for i,v in enumerate(args)]
                named=[(f'{kw.arg}=',v[2],f'kw_{kw.arg}') if kw.arg is not None
                       else ('** unpack',v[2],f'kw_unpack{i}')
                       for i,(kw,v) in enumerate(zip(expr.keywords,keywords))]
                n=add(_node(id_,f'CALL {name}','call',_source_label(self.source,expr),790,190+line*148,
                    inputs=call_inputs+positional+named,
                    outputs=[('result','py:unknown','result')],
                    rows=[_row('Callable',name,id_+':call'), _row('Effect','unverified',id_+':effect')],
                    accent='#8c9ce8',source=expr))
                n.update(semantic_role='invocation',effect_verification='unverified')
                if call_inputs:
                    edges.append(self._edge(callee[0],callee[1],id_,n['draft_ports']['inputs'][0]['id'],'call'))
                for src,port in zip(args+keywords,n['draft_ports']['inputs'][len(call_inputs):]):
                    edges.append(self._edge(src[0],src[1],id_,port['id']))
                line+=1;return id_,n['draft_ports']['outputs'][0]['id'],'py:unknown'
            # All other AST expressions are preserved as a single source-backed node.
            id_=expr_id('opaque-expr',expr)
            n=add(_node(id_,type(expr).__name__.upper(),'opaque',_source_label(self.source,expr),700,200+line*148,
                outputs=[('value',_type(expr,known),'result')],
                rows=[_row('Source',_source_label(self.source,expr),id_+':expr')],
                accent='#aa9b82',source=expr))
            line+=1;return id_,n['draft_ports']['outputs'][0]['id'],_type(expr,known)

        # Control-flow projection. Edges are constructed only for statements
        # we understand. Unknown regions are source-backed and stop inferred
        # sequencing rather than generating deceptively executable wires.
        warnings=[]
        def flow_pin(n,side,name):
            return next((p['id'] for p in n['draft_ports'][side]
                         if p['id'].split(':')[-1]==name),None)
        def link_flows(incoming,node,input_key='in'):
            pin=flow_pin(node,'inputs',input_key)
            if pin:
                for a,port in incoming:
                    edges.append(self._edge(a,port,node['id'],pin,'control'))
        def qualified_direct_call_control(call_expr,producer,incoming):
            """One existing CALL node supplies both its result and normal flow.

            A direct call with eager Name/Constant positional args has a
            source-backed normal evaluation order. Nested/lazy/keyword or
            starred expressions are not lowered into invented ordering.
            This does not claim purity or that Python cannot raise.
            """
            if not (isinstance(call_expr,ast.Call) and isinstance(call_expr.func,ast.Name)
                    and not call_expr.keywords and all(isinstance(a,(ast.Name,ast.Constant))
                                                      for a in call_expr.args)):
                return incoming
            call=next(n for n in nodes if n['id']==producer[0])
            if not any(p['id'].endswith(':in') for p in call['draft_ports']['inputs']):
                call['draft_ports']['inputs'].append({
                    'id':call['id']+':inputs:in','label':'flow','type':'execution'})
                call['draft_ports']['outputs'].append({
                    'id':call['id']+':outputs:out','label':'next','type':'execution'})
            link_flows(incoming,call)
            call['statement_invocation']=True
            return [(call['id'],flow_pin(call,'outputs','out'))] if incoming else []

        def emit_sequence(statements,incoming,depth=0,loop_ctx=None):
            nonlocal bindings,known
            if depth>MAX_DEPTH:raise SourceError('Statement nesting exceeds supported depth')
            flows=list(incoming)
            for idx,stmt in enumerate(statements):
                if not flows and loop_ctx is not None:
                    warnings.append('Unreachable loop-body statements have no executable control path.')
                    break
                if isinstance(stmt,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
                    key=next((c for c in scope.children if self.scopes[c].ast_node is stmt),None)
                    params_,return_=_signature(stmt) if not isinstance(stmt,ast.ClassDef) else ([], 'py:object')
                    freed,_=_symbols(self.scopes[key].table if key else None)
                    id_=_identifier('py',scope.key,'nested',stmt.name,stmt.lineno)
                    n=add(_node(id_,stmt.name.upper(),'nested','Double-click to open scope',350,480+idx*175,
                        inputs=[('flow','execution','in')]+[(name,typ,name) for name,typ in params_] +
                               [(f'capture: {name}', known.get(name,'py:unknown'),'env:'+name) for name in freed],
                        outputs=([('callable','py:callable','fn'),('next','execution','out')]+
                                 ([('return',return_,'result')] if not isinstance(stmt,ast.ClassDef) else [])),
                        rows=[_row('Scope','nested definition',id_+':scope')],
                        accent='#a393e8',source=stmt,scope=key))
                    n['semantic_role']='definition'
                    for pin in n['draft_ports']['inputs']:
                        if ':env:' not in pin['id']:continue
                        name=pin['id'].split('env:',1)[-1]
                        if name in bindings:
                            edges.append(self._edge(bindings[name][0],bindings[name][1],id_,pin['id'],'reference'))
                    bindings[stmt.name]=(id_,n['draft_ports']['outputs'][0]['id'],'py:callable')
                    known[stmt.name]='py:callable'
                    link_flows(flows,n)
                    flows=[(id_,flow_pin(n,'outputs','out'))]
                    # Function definition runtime effects (decorators/defaults)
                    # aren't modeled as pure flow here.
                    if stmt.decorator_list or (isinstance(stmt,(ast.FunctionDef,ast.AsyncFunctionDef)) and
                        (stmt.args.defaults or any(v is not None for v in stmt.args.kw_defaults))):
                        warnings.append('Definition-time decorators/default arguments are not yet lowered.')
                    continue
                if isinstance(stmt,(ast.Assign,ast.AnnAssign)) and stmt.value is not None:
                    producer=expression(stmt.value)
                    targets=stmt.targets if isinstance(stmt,ast.Assign) else [stmt.target]
                    if not all(isinstance(t,ast.Name) for t in targets):
                        # Assignment target effects (attributes, subscripts,
                        # destructuring) require a separate validated lowering.
                        id_=_identifier('py',scope.key,'complex-assignment',stmt.lineno,stmt.col_offset)
                        n=add(_node(id_,'ASSIGNMENT','opaque','Unsupported target · source-backed',1180,180+len(nodes)*40,
                            inputs=[('flow','execution','in')],outputs=[],
                            rows=[_row('Source',_source_label(self.source,stmt),id_+':source')],source=stmt,accent='#ad9480'))
                        link_flows(flows,n);flows=[]
                        warnings.append('Complex assignment targets are left source-backed.')
                        continue
                    for target in targets:
                        name=target.id
                        typ=_ann(stmt.annotation) if isinstance(stmt,ast.AnnAssign) else producer[2]
                        id_=_identifier('py',scope.key,'assign',name,stmt.lineno,stmt.col_offset)
                        symbol=None
                        if scope.table:
                            try:symbol=scope.table.lookup(name)
                            except KeyError:pass
                        ownership=('module/global write' if symbol and symbol.is_global() else
                                   'enclosing nonlocal write' if symbol and symbol.is_nonlocal() else 'function local')
                        n=add(_node(id_,'SET '+name,'assignment',f'{name} ← value',1180,150+len(nodes)*38,
                            inputs=[('value',producer[2],'value'),('flow','execution','in')],
                            outputs=[(name,typ,'value'),('next','execution','out')],
                            rows=[_row('Source',_source_label(self.source,stmt),id_+':source'),
                                  _row('Scope',ownership,id_+':scope')],source=stmt,accent='#51bcac'))
                        # Stable source-level binding metadata. Presentation
                        # must not infer variable identity from a node title.
                        n['binding_name']=name
                        n['binding_ownership']=ownership
                        n['binding_statement_kind']='assign'
                        edges.append(self._edge(producer[0],producer[1],id_,n['draft_ports']['inputs'][0]['id']))
                        link_flows(flows,n)
                        flows=[(id_,flow_pin(n,'outputs','out'))]
                        bindings[name]=(id_,n['draft_ports']['outputs'][0]['id'],typ);known[name]=typ
                    continue
                if depth==0 and loop_ctx is None and isinstance(stmt,ast.Expr) and isinstance(stmt.value,ast.Call) and (
                    isinstance(stmt.value.func,ast.Name) and not stmt.value.keywords and
                    all(isinstance(arg,(ast.Name,ast.Constant)) for arg in stmt.value.args)):
                    # One canonical invocation: expression() builds the actual
                    # CALL and its data inputs. A standalone statement gives
                    # that SAME node execution pins, not an extra wrapper.
                    # Only simple eager positional inputs are qualified for
                    # sequential control flow in a function's direct body.
                    # Conditional/loop arms and complex/nested calls retain
                    # the old source-backed effects barrier below.
                    output=expression(stmt.value)
                    flows=qualified_direct_call_control(stmt.value,output,flows)
                    continue
                if isinstance(stmt,ast.Return):
                    source=expression(stmt.value) if stmt.value is not None else None
                    # A direct CALL feeding RETURN is evaluated before RETURN
                    # in actual Python. Its data and execution facets belong
                    # to one node, not a phantom separate call-site.
                    arrival=(qualified_direct_call_control(stmt.value,source,flows)
                             if source is not None else flows)
                    id_=_identifier('py',scope.key,'return',stmt.lineno,stmt.col_offset)
                    n=add(_node(id_,'RETURN','return',_source_label(self.source,stmt),1180,190+len(nodes)*38,
                        inputs=([('value',source[2],'value')] if source else [])+[('flow','execution','in')],
                        outputs=[],rows=[_row('Source',_source_label(self.source,stmt),id_+':source')],
                        source=stmt,accent='#e2b266'))
                    if source:
                        if isinstance(stmt.value,ast.Name):
                            n['return_binding']=stmt.value.id
                            n['draft_ports']['inputs'][0]['label']=stmt.value.id
                        edges.append(self._edge(source[0],source[1],id_,n['draft_ports']['inputs'][0]['id']))
                    link_flows(arrival,n)
                    flows=[]
                    continue
                if isinstance(stmt,ast.Pass):
                    pid=_identifier('py',scope.key,'pass',stmt.lineno,stmt.col_offset)
                    n=add(_node(pid,'PASS','pass','No operation',1150,180+len(nodes)*36,
                        inputs=[('execute','execution','in')],outputs=[('next','execution','out')],
                        rows=[],source=stmt,accent='#8dabbf'))
                    link_flows(flows,n)
                    flows=[(pid,flow_pin(n,'outputs','out'))] if flows else []
                    continue
                if isinstance(stmt,(ast.Break,ast.Continue)) and loop_ctx is not None:
                    # Break exits the nearest loop; continue resumes its test/
                    # iterator. Both are real control transfers, NOT extra
                    # statement-body wrapper nodes.
                    is_break=isinstance(stmt,ast.Break)
                    name='BREAK' if is_break else 'CONTINUE'
                    cid=_identifier('py',scope.key,name.lower(),stmt.lineno,stmt.col_offset)
                    control=add(_node(cid,name,name.lower(),
                        'Exit nearest loop' if is_break else 'Start next iteration',
                        1200,185+len(nodes)*43,
                        inputs=[('execute','execution','in')],outputs=[('transfer','execution','out')],
                        rows=[],source=stmt,accent='#d9b985'))
                    link_flows(flows,control)
                    if flows:
                        target='break' if is_break else 'repeat'
                        edges.append(self._edge(cid,flow_pin(control,'outputs','out'),
                            loop_ctx.node_id,loop_ctx.break_input if is_break else loop_ctx.repeat_input,'control'))
                        if is_break:loop_ctx.break_count+=1
                        else:loop_ctx.continue_count+=1
                    flows=[]
                    continue
                if isinstance(stmt,ast.AugAssign) and isinstance(stmt.target,ast.Name):
                    # Read-modify-write with explicit previous-value and RHS.
                    # For a loop-carried variable the previous value is a
                    # conservative unknown, NEVER the initial assignment.
                    name=stmt.target.id
                    previous=bindings.get(name)
                    if previous is None:
                        anchor(name,known.get(name,'py:unknown'),'maybe-unbound local',len(bindings))
                        previous=bindings[name]
                    operand=expression(stmt.value)
                    uid=_identifier('py',scope.key,'update',name,stmt.lineno,stmt.col_offset)
                    opname=OPERATOR_NAMES.get(type(stmt.op),type(stmt.op).__name__)
                    update=add(_node(uid,'UPDATE '+name,'assignment',f'{name} {opname}= value',
                        1180,170+len(nodes)*39,
                        inputs=[('previous',previous[2],'previous'),('operand',operand[2],'operand'),
                                ('execute','execution','in')],
                        outputs=[(name,'py:unknown','value'),('next','execution','out')],
                        rows=[_row('Source',_source_label(self.source,stmt),uid+':source'),
                              _row('Operation','Read-modify-write; exceptions/effects not fully analyzed',uid+':note')],
                        source=stmt,accent='#51bcac'))
                    update['binding_name']=name
                    update['binding_statement_kind']='augassign'
                    edges.append(self._edge(previous[0],previous[1],uid,update['draft_ports']['inputs'][0]['id']))
                    edges.append(self._edge(operand[0],operand[1],uid,update['draft_ports']['inputs'][1]['id']))
                    link_flows(flows,update)
                    flows=[(uid,flow_pin(update,'outputs','out'))] if flows else []
                    bindings[name]=(uid,flow_pin(update,'outputs','value'),'py:unknown')
                    known[name]='py:unknown'
                    continue
                if isinstance(stmt,ast.If):
                    condition=expression(stmt.test)
                    id_=_identifier('py',scope.key,'if',stmt.lineno,stmt.col_offset)
                    n=add(_node(id_,'BRANCH','branch',_source_label(self.source,stmt.test),1170,160+len(nodes)*38,
                        inputs=[('condition',condition[2],'condition'),('execute','execution','in')],
                        outputs=[('true','execution','true'),('false','execution','false')],
                        rows=[_row('Condition',_source_label(self.source,stmt.test),id_+':condition')],
                        source=stmt,accent='#e0b1bb'))
                    edges.append(self._edge(condition[0],condition[1],id_,n['draft_ports']['inputs'][0]['id']))
                    link_flows(flows,n)
                    snapshot=dict(bindings);types_snapshot=dict(known)
                    # Each path is analyzed in its own binding environment.
                    path_results=[]
                    for arm,body in (('true',stmt.body),('false',stmt.orelse)):
                        bindings=dict(snapshot);known=dict(types_snapshot)
                        prev_warnings=len(warnings)
                        path_flows=emit_sequence(body,[(id_,flow_pin(n,'outputs',arm))],depth+1,loop_ctx) if body else [(id_,flow_pin(n,'outputs',arm))]
                        unresolved=any('source-backed' in message or 'not yet lowered' in message
                                       for message in warnings[prev_warnings:])
                        path_results.append((path_flows,dict(bindings),dict(known),unresolved))
                    bindings=dict(snapshot);known=dict(types_snapshot)
                    if any(r[3] for r in path_results):
                        flows=[]
                        warnings.append('Branch has unresolved effects/control flow; its successor and value merge are not inferred.')
                        continue
                    reachable=[result for result in path_results if result[0]]
                    endpoints=[flow for result in reachable for flow in result[0]]
                    if len(endpoints)>1:
                        jid=_identifier('py',scope.key,'join',stmt.lineno,stmt.col_offset)
                        j=add(_node(jid,'MERGE','control_join','Join reachable control paths',1450,180+len(nodes)*40,
                            inputs=[(f'path {i+1}','execution',f'path{i}') for i in range(len(endpoints))],
                            outputs=[('next','execution','out')],rows=[],source=stmt,accent='#b9bcd6'))
                        for i,(start,pin) in enumerate(endpoints):
                            edges.append(self._edge(start,pin,jid,j['draft_ports']['inputs'][i]['id'],'control'))
                        flows=[(jid,flow_pin(j,'outputs','out'))]
                    else:flows=endpoints
                    if len(reachable)==1:
                        # One surviving path (e.g. the other returned) governs
                        # bindings after the branch.
                        bindings.update(reachable[0][1]);known.update(reachable[0][2])
                    elif len(reachable)>1:
                        # Merge values only when every reachable branch supplies
                        # a known value. Unknown/unbound cases remain unresolved.
                        names=set.intersection(*(set(r[1]) for r in reachable))
                        for name in sorted(names):
                            values=[r[1][name] for r in reachable]
                            if len({(v[0],v[1]) for v in values}) == 1:
                                bindings[name]=values[0];known[name]=values[0][2];continue
                            pid=_identifier('py',scope.key,'value-merge',name,stmt.lineno,stmt.col_offset)
                            types={v[2] for v in values};typ=next(iter(types)) if len(types)==1 else 'py:unknown'
                            merge=add(_node(pid,'MERGE '+name,'value_merge','Conditional value · path-dependent',1450,260+len(nodes)*38,
                                inputs=[(f'path {i+1}',v[2],f'path{i}') for i,v in enumerate(values)],
                                outputs=[(name,typ,'value')],
                                rows=[_row('Value','Selected by preceding control path',pid+':v')],
                                source=stmt,accent='#b0a6ee'))
                            for i,(start,port,_) in enumerate(values):
                                edges.append(self._edge(start,port,pid,merge['draft_ports']['inputs'][i]['id'],'data'))
                            bindings[name]=(pid,merge['draft_ports']['outputs'][0]['id'],typ);known[name]=typ
                    continue
                if isinstance(stmt,(ast.For,ast.AsyncFor,ast.While)):
                    # A loop is a control operation with body/completed flow
                    # ports. Its body is a sequence of ORDINARY statements.
                    # No synthetic 'WHILE BODY'/'FOR BODY' operation exists.
                    is_while=isinstance(stmt,ast.While)
                    condition=stmt.test if is_while else stmt.iter
                    for_target=(stmt.target if not is_while else None)
                    # Destructuring/attribute targets and async iteration need
                    # additional language semantics, so keep these source-
                    # backed rather than fabricating an incorrect item binding.
                    supported=(is_while or (isinstance(stmt,ast.For) and
                                           isinstance(for_target,ast.Name)))
                    lid=_identifier('py',scope.key,'loop',stmt.lineno,stmt.col_offset)
                    word='WHILE' if is_while else ('ASYNC FOR' if isinstance(stmt,ast.AsyncFor) else 'FOR')
                    if is_while:
                        # Test is evaluated ON EACH entry/re-entry, not a
                        # snapshot of the initial value. Never link stale
                        # pre-loop assignments into a fake constant condition.
                        tid=_identifier('py',scope.key,'loop-test',stmt.lineno,stmt.col_offset)
                        t=add(_node(tid,'TEST','loop_test',_source_label(self.source,condition),
                            765,175+len(nodes)*40,
                            outputs=[('truth','py:bool','result')],
                            rows=[_row('Source',_source_label(self.source,condition),tid+':source'),
                                  _row('Evaluation','Re-evaluated for every loop entry',tid+':note')],
                            source=condition,accent='#a9a1d6'))
                        t['visual_family']='operator';t['display_symbol']='?'
                        producer=(tid,flow_pin(t,'outputs','result'),'py:bool')
                    else:
                        producer=expression(condition)  # iterable evaluated once
                    inputs=[('condition' if is_while else 'iterable',producer[2],
                             'condition' if is_while else 'iterable'),
                            ('execute','execution','in'),('repeat','execution','repeat'),
                            ('break','execution','break')]
                    outputs=[('body','execution','body'),('completed','execution','complete'),
                             ('broken','execution','broken')]
                    if not is_while and supported:
                        outputs.append((for_target.id,'py:unknown','item'))
                    loop=add(_node(lid,word,'loop',_source_label(self.source,condition),
                        1150,155+len(nodes)*42,inputs=inputs,outputs=outputs,
                        rows=[_row('Source',_source_label(self.source,stmt),lid+':source'),
                              _row('Control','Body repeats; completed on exhaustion/false; break exits',lid+':flow')],
                        source=stmt,accent='#b4a6ed'))
                    loop['visual_family']='control'
                    loop['loop_semantics']={'condition_evaluation':'per_iteration' if is_while else 'once_at_entry',
                                            'body':'statements', 'normal_exit':'complete',
                                            'break_exit':'broken', 'repeat_input':'repeat',
                                            'source_backed':not supported}
                    edges.append(self._edge(producer[0],producer[1],lid,flow_pin(loop,'inputs',
                        'condition' if is_while else 'iterable')))
                    link_flows(flows,loop)
                    if not supported:
                        # Keep the loop's source text and visible ports, but
                        # refuse executable body/backedges for unsupported
                        # async/complex targets.
                        loop['loop_semantics']['source_backed']=True
                        loop['subtitle']='Source-backed loop: body not lowered'
                        loop['draft_ports']['inputs']=[p for p in loop['draft_ports']['inputs']
                            if not p['id'].endswith((':repeat',':break'))]
                        loop['draft_ports']['outputs']=[p for p in loop['draft_ports']['outputs']
                            if not p['id'].endswith((':body',':broken'))]
                        flows=[]
                        warnings.append(word+' iteration/target semantics unsupported; no fabricated body flow.')
                        continue
                    # Every body iteration can read a value left by a prior
                    # iteration. Seed that binding with an explicit uncertain
                    # loop-carried value; old pre-loop SETs are NOT reused.
                    previous_bindings=dict(bindings);previous_known=dict(known)
                    never_enters=(is_while and isinstance(condition,ast.Constant) and
                                  condition.value is False)
                    written=(_loop_body_writes(stmt.body) if not never_enters else set())
                    if for_target is not None and not never_enters:written.add(for_target.id)
                    # Only a single unconditional, simple write in the body
                    # can prove a recurrence. Complex paths retain unknowns.
                    single_write=(len(stmt.body)==1 and
                        ((isinstance(stmt.body[0],ast.AugAssign) and
                          isinstance(stmt.body[0].target,ast.Name)) or
                         (isinstance(stmt.body[0],ast.Assign) and
                          len(stmt.body[0].targets)==1 and
                          isinstance(stmt.body[0].targets[0],ast.Name))))
                    recurrence_name=(stmt.body[0].target.id if single_write and
                        isinstance(stmt.body[0],ast.AugAssign) else
                        stmt.body[0].targets[0].id if single_write else None)
                    recurrences={};original_binding=dict(previous_bindings)
                    for name in sorted(written):
                        if not is_while and name==for_target.id:
                            bindings[name]=(lid,flow_pin(loop,'outputs','item'),'py:unknown')
                        else:
                            vid=_identifier('py',scope.key,'loop-carried',name,stmt.lineno,stmt.col_offset)
                            proven=(name==recurrence_name and name in previous_bindings)
                            v=add(_node(vid,'LOOP VALUE '+name,'loop_value',
                                'Entry / next iteration' if proven else 'Iteration-dependent, unresolved',
                                610,195+len(nodes)*42,
                                inputs=([('initial',previous_bindings[name][2],'initial'),
                                         ('next', 'py:unknown','next')] if proven else []),
                                outputs=[(name,'py:unknown','value')],
                                rows=[_row('Source','Entry and next-iteration versions' if proven
                                           else 'Loop entry / previous iteration',vid+':v')],
                                accent='#b8947d',source=stmt))
                            bindings[name]=(vid,flow_pin(v,'outputs','value'),'py:unknown')
                            if proven:
                                initial=previous_bindings[name]
                                edges.append(self._edge(initial[0],initial[1],vid,
                                    flow_pin(v,'inputs','initial'),'data'))
                                recurrences[name]=v
                        known[name]='py:unknown'
                    # WHILE tests run on entry AND every backedge. Their
                    # named reads must use iteration-state bindings, not an
                    # accidentally frozen pre-loop value. Read-dependency
                    # edges do not claim the test is an eagerly evaluated op.
                    if is_while:
                        for name in sorted(_runtime_reads([ast.Expr(value=condition)])):
                            if name not in bindings:
                                name_node=next(n for n in ast.walk(condition)
                                    if isinstance(n,ast.Name) and n.id==name and
                                    isinstance(n.ctx,ast.Load))
                                expression(name_node)  # shared scope-aware resolution
                            src=bindings[name]
                            port_id=f'{tid}:inputs:read:{name}'
                            t['draft_ports']['inputs'].append({
                                'id':port_id,'label':name,'type':src[2]})
                            edges.append(self._edge(src[0],src[1],tid,port_id,'data'))
                        t['loop_test_semantics']='reevaluate_after_repeat'
                    ctx=LoopContext(lid,flow_pin(loop,'inputs','repeat'),
                                    flow_pin(loop,'inputs','break'))
                    if never_enters:
                        # while False has no reachable body. Preserve the
                        # source text on the loop node, but don't invent a
                        # body or a repeat connection that can execute.
                        loop['subtitle']='Condition is always false; body unreachable'
                        loop['draft_ports']['outputs']=[p for p in loop['draft_ports']['outputs']
                            if not p['id'].endswith(':body')]
                        loop['draft_ports']['inputs']=[p for p in loop['draft_ports']['inputs']
                            if not p['id'].endswith(':repeat')]
                        body_flows=[]
                    else:
                        incoming_body=[(lid,flow_pin(loop,'outputs','body'))]
                        body_flows=emit_sequence(stmt.body,incoming_body,depth+1,ctx)
                    for end_node,end_port in body_flows:
                        edges.append(self._edge(end_node,end_port,lid,ctx.repeat_input,'control'))
                    # A one-statement unconditional recurrence has a proven
                    # next-iteration source. This is a value-version merge,
                    # not an additional executable graph operation.
                    for name,merge in list(recurrences.items()):
                        latest=bindings.get(name)
                        if (body_flows and latest is not None and
                                latest[0]!=merge['id']):
                            edges.append(self._edge(latest[0],latest[1],merge['id'],
                                flow_pin(merge,'inputs','next'),'data'))
                            merge['loop_value_semantics']='initial_or_previous_iteration'
                        else:
                            # Do not expose an unwired phantom "next" pin.
                            merge['draft_ports']['inputs']=[p for p in merge['draft_ports']['inputs']
                                if not p['id'].endswith(':next')]
                            recurrences.pop(name,None)
                            merge['loop_value_semantics']='unresolved'

                    # Remove visually useless break pins when no reachable
                    # break path exists in this loop. The body's control flow
                    # is still represented by actual statements and backedges.
                    if not ctx.break_count:
                        loop['draft_ports']['inputs']=[p for p in loop['draft_ports']['inputs']
                            if p['id']!=ctx.break_input]
                        loop['draft_ports']['outputs']=[p for p in loop['draft_ports']['outputs']
                            if not p['id'].endswith(':broken')]
                    loop['loop_semantics']['break_paths']=ctx.break_count
                    loop['loop_semantics']['continue_paths']=ctx.continue_count
                    loop['loop_semantics']['normal_backedges']=len(body_flows)
                    # After any number of iterations an assigned variable may
                    # have changed; for targets may be unbound after zero runs.
                    bindings=dict(previous_bindings);known=dict(previous_known)
                    for name in sorted(written):
                        if name in recurrences and not ctx.break_count and not stmt.orelse:
                            merge=recurrences[name]
                            bindings[name]=(merge['id'],flow_pin(merge,'outputs','value'),'py:unknown')
                            known[name]='py:unknown'
                            continue
                        uid=_identifier('py',scope.key,'loop-unknown',name,stmt.lineno,stmt.col_offset)
                        unresolved=add(_node(uid,'UNCERTAIN '+name,'loop_value',
                            'Post-loop value depends on iteration count and exits',
                            1550,215+len(nodes)*37,
                            outputs=[(name,'py:unknown','value')],
                            rows=[_row('Reason','Zero/many iterations or break; value not proven',uid+':reason')],
                            accent='#b8947d',source=stmt))
                        bindings[name]=(uid,flow_pin(unresolved,'outputs','value'),'py:unknown')
                        known[name]='py:unknown'
                    # The loop's normal completion executes its ELSE block
                    # (if any); BREAK bypasses ELSE. A while True loop has no
                    # test-false completion path, only a break/return exit.
                    normally_completes=not (is_while and isinstance(condition,ast.Constant)
                                             and condition.value is True)
                    if not normally_completes:
                        loop['draft_ports']['outputs']=[p for p in loop['draft_ports']['outputs']
                            if not p['id'].endswith(':complete')]
                    completed=[(lid,flow_pin(loop,'outputs','complete'))] if normally_completes else []
                    if stmt.orelse and completed:
                        completed=emit_sequence(stmt.orelse,completed,depth+1,loop_ctx)
                    broken=[(lid,flow_pin(loop,'outputs','broken'))] if ctx.break_count else []
                    endpoints=completed+broken
                    if len(endpoints)>1:
                        jid=_identifier('py',scope.key,'loop-exit-join',stmt.lineno,stmt.col_offset)
                        join=add(_node(jid,'MERGE','control_join','Join loop completion and break paths',
                            1450,180+len(nodes)*37,
                            inputs=[(f'path {i+1}','execution',f'path{i}') for i in range(len(endpoints))],
                            outputs=[('next','execution','out')],rows=[],source=stmt,accent='#b9bcd6'))
                        for i,(start,pin) in enumerate(endpoints):
                            edges.append(self._edge(start,pin,jid,join['draft_ports']['inputs'][i]['id'],'control'))
                        flows=[(jid,flow_pin(join,'outputs','out'))]
                    else:flows=endpoints
                    warnings.append(word+' control paths projected; simple recurrences are explicit, other iteration values remain uncertain.')
                    continue
                id_=_identifier('py',scope.key,'statement',stmt.lineno,stmt.col_offset)
                n=add(_node(id_,type(stmt).__name__.upper(),'opaque','Source-backed; flow not yet lowered',1180,180+len(nodes)*40,
                    inputs=[('flow','execution','in')],outputs=[],
                    rows=[_row('Source',_source_label(self.source,stmt),id_+':src'),
                          _row('Status','Control/effects not yet decomposed',id_+':note')],
                    accent='#ad9480',source=stmt))
                link_flows(flows,n)
                flows=[]
                warnings.append(type(stmt).__name__+' remains source-backed; subsequent control flow not inferred.')
            return flows
        entry_id=_identifier('py',scope.key,'entry')
        entry=add(_node(entry_id,'ENTRY','entry','Function entry',140,90,
            outputs=[('execute','execution','out')],
            rows=[_row('Scope',scope.title,entry_id+':scope')],accent='#f0f4fa'))
        outgoing=emit_sequence(node.body,[(entry_id,flow_pin(entry,'outputs','out'))])
        if outgoing:
            exit_id=_identifier('py',scope.key,'implicit-exit')
            exit_node=add(_node(exit_id,'EXIT','exit','Implicit return None on fallthrough',1550,180,
                inputs=[('flow','execution','in')],outputs=[],rows=[],accent='#e6edf8'))
            link_flows(outgoing,exit_node)
        return {'scope':scope.key,'title':f'{scope.title}(…)','nodes':nodes,'edges':edges,
                'warnings':['Static source projection; Python annotations are not runtime type guarantees.',
                            'Straightforward branches and loop control paths are projected; loop value merges are resolved only for one-statement recurrences.',
                            'Values at branch joins are path-dependent, not eagerly evaluated.']+sorted(set(warnings))}

    def _class_graph(self,scope):
        nodes=[]
        for ix,child_key in enumerate(scope.children):
            child=self.scopes[child_key];stmt=child.ast_node
            params,ret=_signature(stmt) if child.kind=='function' else ([], 'py:object')
            id_=_identifier('py','class-child',child_key)
            declaration=_node(id_,child.title.upper(),child.kind,'Double-click to enter',150+(ix%3)*480,110+(ix//3)*220,
                    inputs=[(p,t,p) for p,t in params],outputs=[('return',ret,'return')],
                    rows=[_row('Source',_source_label(self.source,stmt).split(':')[0],id_+':src')],
                    source=stmt,scope=child_key,accent='#9b9fff')
            declaration['semantic_role']='definition'
            nodes.append(declaration)
        for stmt in scope.ast_node.body:
            if isinstance(stmt,(ast.AnnAssign,ast.Assign)):
                targets=stmt.targets if isinstance(stmt,ast.Assign) else [stmt.target]
                for target in targets:
                    if isinstance(target,ast.Name):
                        id_=_identifier('py','class-attr',target.id,stmt.lineno)
                        nodes.append(_node(id_,target.id,'attribute','Class scope binding',110+(len(nodes)%3)*480,
                            130+(len(nodes)//3)*230,outputs=[('value','py:unknown','value')],
                            rows=[_row('Source',_source_label(self.source,stmt),id_+':source')],
                            source=stmt,accent='#dba978'))
        return {'scope':scope.key,'title':scope.title,'nodes':nodes[:MAX_VIEW_NODES], 'edges':[],
                'warnings':['Class attributes/method declarations; inheritance and descriptor behavior are not evaluated.']}
