"""Small, guarded Python source transforms initiated from visual nodes.

No Python code is executed here: parsing and compile() only validate syntax.
Only exact AST spans are touched; unrelated source bytes stay intact.
This is intentionally *not* a general Python refactoring engine.
"""
from __future__ import annotations
import ast
import difflib
import fcntl
import hashlib
import io
import math
import os
import stat
import tempfile
import tokenize
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from .python_graph import PythonDocument, SourceError


@dataclass(frozen=True)
class EditProposal:
    path: Path
    original: bytes
    candidate: bytes
    encoding: str
    description: str

    @property
    def diff(self):
        try:
            old=self.original.decode(self.encoding).splitlines(keepends=True)
            new=self.candidate.decode(self.encoding).splitlines(keepends=True)
        except UnicodeError as exc:raise SourceError(str(exc)) from exc
        return ''.join(difflib.unified_diff(old,new,fromfile=str(self.path),
                                           tofile=str(self.path)+' (proposed)',n=3))


def _spans(raw: bytes, node: ast.AST):
    """AST col_offset is UTF-8 *byte* offset, not a Unicode character index."""
    if any(not isinstance(getattr(node,k,None),int) for k in ('lineno','col_offset','end_lineno','end_col_offset')):
        raise SourceError('Source location unavailable')
    lines=raw.splitlines(keepends=True)
    a,b=node.lineno,node.end_lineno
    if not (1<=a<=b<=len(lines)):raise SourceError('Invalid source location')
    start=sum(map(len,lines[:a-1]))+node.col_offset
    end=sum(map(len,lines[:b-1]))+node.end_col_offset
    if not (0<=start<end<=len(raw)):raise SourceError('Invalid source byte span')
    return start,end


def _require_utf8(doc):
    enc=doc.encoding.lower().replace('_','-')
    if enc not in ('utf-8',):
        raise SourceError('Visual source edits currently require a UTF-8 Python file; inspection is still available')


def _validated_proposal(doc: PythonDocument, result: bytes, description: str) -> EditProposal:
    """One syntax/size/file-identity gate shared by source edits and node creation."""
    _require_utf8(doc)
    if result==doc.raw:raise SourceError('Proposed source does not change the file')
    if len(result)>1_500_000:raise SourceError('Edited file exceeds analysis limit')
    try:
        text=result.decode(doc.encoding)
        parsed=ast.parse(text,filename=str(doc.path),type_comments=True)
        compile(parsed,str(doc.path),'exec',dont_inherit=True)
    except (SyntaxError,ValueError,TypeError,UnicodeError) as exc:
        raise SourceError(f'Generated source is invalid: {exc}') from exc
    return EditProposal(doc.path,doc.raw,result,doc.encoding,description)


def _candidate(doc: PythonDocument, target: ast.AST, replacement: str, description: str):
    _require_utf8(doc)
    start,end=_spans(doc.raw,target)
    original=doc.raw[start:end]
    if not original:raise SourceError('Empty source token')
    try:change=replacement.encode('utf-8')
    except UnicodeError as exc:raise SourceError(str(exc)) from exc
    result=doc.raw[:start]+change+doc.raw[end:]
    return _validated_proposal(doc,result,description)


def change_literal(doc: PythonDocument, span: dict, python_literal: str):
    """Replace an exact Constant's token. Never eval/exec the replacement."""
    target=_find_node(doc,span)
    if not isinstance(target,ast.Constant):
        raise SourceError('Only literal nodes can be changed with this action')
    try:
        expr=ast.parse(python_literal,mode='eval').body
    except (SyntaxError,ValueError) as exc:raise SourceError(f'Not a valid Python literal: {exc}') from exc
    if not isinstance(expr,ast.Constant) or type(expr.value) not in (int,float,bool,str,bytes,type(None)):
        raise SourceError('Expected one safe string/number/bool/None literal (no calls or expressions)')
    return _candidate(doc,target,python_literal,'Change Python literal')


def add_constant_operand(doc: PythonDocument, span: dict, operand: str):
    """For a simple Assign or Return node, wrap its value in '+ constant'."""
    target=_find_node(doc,span)
    if not isinstance(target,(ast.Assign,ast.AnnAssign,ast.Return)) or target.value is None:
        raise SourceError('Select an assignment or return statement with a value')
    try:new=ast.parse(operand,mode='eval').body
    except (SyntaxError,ValueError) as exc:raise SourceError(f'Invalid numeric operand: {exc}') from exc
    if not isinstance(new,ast.Constant) or type(new.value) not in (int,float):
        raise SourceError('Operand must be one numeric literal (no code execution)')
    start,end=_spans(doc.raw,target.value)
    old=doc.raw[start:end].decode(doc.encoding)
    return _candidate(doc,target.value,f'({old}) + {operand}', 'Add constant operand to expression')


def _find_node(doc: PythonDocument, span: dict):
    if not isinstance(span,dict) or set(span)!=set(('line','col','end_line','end_col')):
        raise SourceError('Missing source span')
    matches=[n for n in ast.walk(doc.tree) if getattr(n,'lineno',None)==span['line']
             and getattr(n,'col_offset',None)==span['col']
             and getattr(n,'end_lineno',None)==span['end_line']
             and getattr(n,'end_col_offset',None)==span['end_col']]
    if not matches:raise SourceError('Source changed or the selected node is stale')
    # AST roots with coincident spans are disambiguated via eligible classes
    for n in matches:
        if isinstance(n,(ast.Constant,ast.Assign,ast.AnnAssign,ast.Return)):return n
    return matches[0]



def _straight_line_regions(function):
    """Return executable statement lists that have a single lexical path.

    An individual if/elif/else arm is a region: a source and destination
    *inside the same arm* execute in order whenever that arm is entered. We
    never treat separate arms, the function's outer list, or any loop body as
    equivalent. Unsupported nested constructs remain hard barriers.
    """
    regions=[function.body]
    def visit(statements, depth):
        if depth > 24:
            raise SourceError('Source nesting exceeds safe rewiring depth')
        for statement in statements:
            if isinstance(statement, ast.If):
                # Separate regions with independent execution paths; don't
                # merge a body and an else arm even if names happen to match.
                for arm in (statement.body,statement.orelse):
                    if arm:
                        regions.append(arm)
                        visit(arm,depth+1)
    visit(function.body,0)
    return regions


def _safe_preceding_local_binding(scope, src: dict, target_expr: ast.AST, selected: ast.AST) -> str:
    """Prove a single preceding local binding in the *same straight-line arm*.

    A value defined in an if body can safely be read later in that same body,
    but it cannot be assumed available in a sibling else arm, outside the if,
    or in any loop. This is a small local-dominance proof, NOT general SSA.
    """
    source_span=src.get('source_span')
    if not source_span:
        raise SourceError('Local assignment source span unavailable')
    scope_body=scope.ast_node.body
    regions=_straight_line_regions(scope.ast_node)
    definitions=[]
    for region in regions:
        for index, statement in enumerate(region):
            if (isinstance(statement,(ast.Assign,ast.AnnAssign))
                    and getattr(statement,'lineno',None)==source_span['line']
                    and getattr(statement,'col_offset',None)==source_span['col']):
                definitions.append((region,index,statement))
    if len(definitions)!=1:
        raise SourceError('Local source must be a direct assignment in a straight-line scope or conditional arm')
    region,source_index,definition=definitions[0]
    targets=definition.targets if isinstance(definition,ast.Assign) else [definition.target]
    if len(targets)!=1 or not isinstance(targets[0],ast.Name) or definition.value is None:
        raise SourceError('Local source must be a simple named assignment')
    name=targets[0].id
    if scope.table is None:
        raise SourceError('Missing symbol table for local dominance check')
    try:
        symbol=scope.table.lookup(name)
    except KeyError as exc:
        raise SourceError('Local assignment symbol cannot be resolved') from exc
    if not symbol.is_local() or symbol.is_global() or symbol.is_nonlocal():
        raise SourceError('Global/nonlocal writes are not eligible for local source rewiring')

    target_index=None
    for ix,stmt in enumerate(region):
        if any(n is target_expr for n in ast.walk(stmt)):
            target_index=ix
            break
    if target_index is None:
        raise SourceError('Source and destination are in different control-flow regions')
    statement_owner=region[target_index]
    if not isinstance(statement_owner,(ast.Assign,ast.AnnAssign,ast.Expr,ast.Return)):
        raise SourceError('Local target must be in a straight-line statement')
    if source_index>=target_index:
        raise SourceError('Local value does not precede the destination')
    # A name read is not an abstract side-effect-free edge: in Python, prior
    # argument expressions can run code (including closure/nonlocal writes)
    # before the selected argument is evaluated. Do not certify such a use.
    calls=[n for n in ast.walk(statement_owner) if isinstance(n,ast.Call)]
    if calls:
        if not (len(calls)==1 and calls[0] is target_expr and
                isinstance(target_expr.func,ast.Name)):
            raise SourceError('Effectful expression context prevents stored-value rewiring')
        ordered=[*target_expr.args,*(kw.value for kw in target_expr.keywords)]
        positions=[i for i,node in enumerate(ordered) if node is selected]
        if len(positions)!=1:
            raise SourceError('Stored value cannot be proven at this nested argument')
        if any(not isinstance(value,(ast.Constant,ast.Name))
               for value in ordered[:positions[0]]):
            raise SourceError('Unverified earlier call argument evaluation prevents stored-value rewiring')
    # Calls/mutations/other control-flow between the assignment and target
    # could invalidate a value or alter the relevant environment. We are
    # conservative until a comprehensive effects/dominance IR exists.
    for statement in region[source_index+1:target_index]:
        if not isinstance(statement,(ast.Assign,ast.AnnAssign,ast.Expr)):
            raise SourceError('Branch/loop/effect barrier prevents local rewiring')
        for n in ast.walk(statement):
            if isinstance(n,(ast.NamedExpr,ast.AugAssign,ast.Delete,ast.Call,ast.Yield,ast.Await,
                             ast.Lambda,ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
                raise SourceError('Unverified mutation or effect prevents local rewiring')
            if isinstance(n,ast.Name) and n.id==name and isinstance(n.ctx,(ast.Store,ast.Del)):
                raise SourceError('Local value was rebound before target')
    return name


def _constant_expression_kind(node: ast.AST, depth: int = 0) -> str:
    """Qualify a copyable, bounded, effect-free *syntactic* expression.

    No Name, Call, Attribute, subscription, division, dynamic operator
    overload, lazy Boolean, or chained comparison is accepted. The expression
    cannot change bindings or call user code when copied to another operand.
    This is NOT generic operator-result wiring or a Python evaluator.
    """
    if depth > 4:
        raise SourceError('Constant expression exceeds qualified composition depth')
    if isinstance(node,ast.Constant):
        value=node.value
        if type(value) is bool:return 'bool'
        if type(value) is type(None):return 'none'
        if type(value) is int and abs(value) <= 1_000_000:return 'numeric'
        if type(value) is float and math.isfinite(value) and abs(value) <= 1_000_000:return 'numeric'
        if type(value) is str and len(value) <= 100:return 'str'
        raise SourceError('Expression literal is not a bounded primitive')
    if isinstance(node,ast.BinOp) and isinstance(node.op,(ast.Add,ast.Sub,ast.Mult)):
        left=_constant_expression_kind(node.left,depth+1)
        right=_constant_expression_kind(node.right,depth+1)
        if left==right=='numeric':return 'numeric'
        if left==right=='str' and isinstance(node.op,ast.Add):return 'str'
        raise SourceError('Expression operands are not qualified primitive operations')
    if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.USub,ast.UAdd)):
        if _constant_expression_kind(node.operand,depth+1)=='numeric':return 'numeric'
    if isinstance(node,ast.Compare) and len(node.ops)==len(node.comparators)==1:
        left=_constant_expression_kind(node.left,depth+1)
        right=_constant_expression_kind(node.comparators[0],depth+1)
        if isinstance(node.ops[0],(ast.Eq,ast.NotEq)) and (left==right or {left,right}=={'none','bool'}):
            return 'bool'
        if isinstance(node.ops[0],(ast.Lt,ast.LtE,ast.Gt,ast.GtE)) and (
                left==right=='numeric' or left==right=='str'):
            return 'bool'
    raise SourceError('Only bounded constant-only arithmetic/comparison results can be copied')


def _qualified_source_input(doc: PythonDocument, scope_key: str,
                            target_id: str, target_port: str):
    """Single AST/port authority for edits to one Python input value.

    The port identity comes from the current scope graph; never accept a raw
    text span, renderer-only edge, or guessed Python name as an edit target.
    """
    _require_utf8(doc)
    if scope_key not in doc.scopes or scope_key=='module':
        raise SourceError('Source input editing requires a function scope')
    scope=doc.scopes[scope_key]
    if scope.kind!='function':
        raise SourceError('Source input editing requires a function scope')
    graph=doc.scope_graph(scope_key)
    dst=next((node for node in graph['nodes'] if node['id']==target_id),None)
    if dst is None:
        raise SourceError('Target is missing from current function scope')
    if not any(p['id']==target_port for p in dst['draft_ports']['inputs']):
        raise SourceError('Input port is no longer valid')
    if dst.get('source_kind') not in ('operation', 'compare', 'call', 'return', 'assignment'):
        raise SourceError('Only operator operands, positional call arguments, returns, and simple assignment values support rewiring')
    operand = target_port.rsplit(':', 1)[-1]
    if dst.get('source_kind') in ('return', 'assignment'):
        if operand != 'value':
            raise SourceError('Statement edits can target only the value input')
    elif dst.get('source_kind') == 'call':
        if not ((operand.startswith('arg') and operand[3:].isdigit()) or
                (operand.startswith('kw_') and operand[3:].isidentifier())):
            raise SourceError('Only explicit positional or named keyword call arguments support rewiring')
    elif operand not in ('lhs', 'rhs', 'operand'):
        raise SourceError('Only expression operand ports can be edited')

    span = dst.get('source_span')
    if not span:
        raise SourceError('Target source location is unavailable')
    matches = [n for n in ast.walk(scope.ast_node)
               if getattr(n, 'lineno', None) == span['line']
               and getattr(n, 'col_offset', None) == span['col']
               and getattr(n, 'end_lineno', None) == span['end_line']
               and getattr(n, 'end_col_offset', None) == span['end_col']]
    target = next((n for n in matches if isinstance(n, (ast.BinOp, ast.Compare, ast.UnaryOp, ast.Call, ast.Assign, ast.AnnAssign, ast.Return))), None)
    if isinstance(target, ast.BinOp):
        if operand not in ('lhs', 'rhs'):
            raise SourceError('Binary operation has only A/B operands')
        selected = target.left if operand == 'lhs' else target.right
    elif isinstance(target, ast.Compare) and len(target.ops) == len(target.comparators) == 1:
        if operand not in ('lhs', 'rhs'):
            raise SourceError('Comparison has only A/B operands')
        selected = target.left if operand == 'lhs' else target.comparators[0]
    elif isinstance(target, ast.UnaryOp):
        if operand != 'operand':
            raise SourceError('Unary operation has one operand')
        selected = target.operand
    elif isinstance(target, (ast.Assign, ast.AnnAssign, ast.Return)):
        if operand != 'value' or target.value is None:
            raise SourceError('This statement does not have an editable value input')
        if isinstance(target, ast.Assign) and (len(target.targets)!=1 or not isinstance(target.targets[0],ast.Name)):
            raise SourceError('Multi-target/destructuring assignments require dedicated lowering')
        if isinstance(target, ast.AnnAssign) and not isinstance(target.target, ast.Name):
            raise SourceError('Only simple named assignments can be rewired')
        selected=target.value
    elif isinstance(target, ast.Call):
        # Explicit positional and named keyword values have distinct ports.
        # **kwargs expansion and *args are never rewritten as normal arguments.
        if any(isinstance(arg, ast.Starred) for arg in target.args):
            raise SourceError('Starred call arguments require dedicated lowering')
        if operand.startswith('kw_'):
            name=operand[3:]
            matching=[kw for kw in target.keywords if kw.arg==name]
            if len(matching)!=1 or any(kw.arg is None for kw in target.keywords):
                raise SourceError('Only one explicit keyword without **unpacking can be edited')
            selected=matching[0].value
        else:
            index = int(operand[3:])
            if index >= len(target.args) or index >= 128:
                raise SourceError('Call argument index is out of bounds')
            selected = target.args[index]
    else:
        raise SourceError('Operator is not a supported source-edit target')

    return scope,graph,dst,target,selected


def replace_source_input_literal(doc: PythonDocument, scope_key: str,
                                 target_id: str, target_port: str, literal: str) -> EditProposal:
    """Explicitly disconnect one simple read and supply a primitive default.

    In Python, removing a visual wire without supplying source is meaningless.
    This qualified replacement is a real source transaction, never scene-only
    state. Complex/effectful input expressions are refused, not erased.
    """
    _,_,_,_,selected=_qualified_source_input(doc,scope_key,target_id,target_port)
    if not isinstance(selected,(ast.Constant,ast.Name)):
        raise SourceError('Only primitive literals or simple name reads can be replaced; complex inputs may have effects')
    try:
        expression=ast.parse(literal,mode='eval').body
    except (SyntaxError,ValueError) as exc:
        raise SourceError('Expected a primitive Python literal') from exc
    valid=isinstance(expression,ast.Constant) and type(expression.value) in (
        int,float,bool,str,bytes,type(None))
    if isinstance(expression,ast.UnaryOp) and isinstance(expression.op,(ast.UAdd,ast.USub)):
        valid=(isinstance(expression.operand,ast.Constant) and
               type(expression.operand.value) in (int,float))
    if not valid:
        raise SourceError('Only an explicit primitive literal is allowed, never an expression or call')
    if len(literal)>512:
        raise SourceError('Literal exceeds visual authoring limit')
    return _candidate(doc,selected,literal,'Replace Python input with primitive literal')


def rewire_source_operand(doc: PythonDocument, scope_key: str,
                          source_id: str, source_port: str,
                          target_id: str, target_port: str) -> EditProposal:
    """Propose a *restricted* edge-to-Python rewrite, with no evaluation.

    An output of a literal, current-function parameter, or a conservatively
    proven same-arm straight-line local assignment may replace the A/B
    operand of an ordinary binary expression, a single comparator operand,
    a supported unary expression, a simple assignment or a return value. All IDs/ports are rederived from the current
    AST, never trusted as raw Python text or as permission to edit any file.
    Local and stored-Call sources create a real Python name reference (not
    a duplicated computation); literal and constant-only expression sources
    are explicit copies. This is NOT a general SSA or dataflow editor.
    Unsupported source/target combinations refuse instead of approximating.
    """
    _require_utf8(doc)
    if scope_key not in doc.scopes or scope_key == 'module':
        raise SourceError('Rewiring requires a Python function scope')
    scope = doc.scopes[scope_key]
    if scope.kind != 'function':
        raise SourceError('Rewiring currently requires a function scope')
    graph = doc.scope_graph(scope_key)
    by_id = {node['id']: node for node in graph['nodes']}
    src, dst = by_id.get(source_id), by_id.get(target_id)
    if src is None or dst is None or src['id'] == dst['id']:
        raise SourceError('Rewire endpoints must be distinct nodes in the same current function')
    if not any(p['id'] == source_port for p in src['draft_ports']['outputs']):
        raise SourceError('Source output port is no longer valid')
    input_ = next((p for p in dst['draft_ports']['inputs'] if p['id'] == target_port), None)
    if input_ is None:
        raise SourceError('Target input port is no longer valid')
    if src.get('source_kind') not in ('literal', 'param', 'assignment', 'operation', 'compare', 'call'):
        raise SourceError('Source output must be a primitive, parameter, local binding, stored call, or qualified constant expression')
    scope,graph,dst,target,selected=_qualified_source_input(doc,scope_key,target_id,target_port)

    if src['source_kind'] == 'literal':
        source_span = src.get('source_span')
        if not source_span:
            raise SourceError('Source literal location unavailable')
        constants = [n for n in ast.walk(scope.ast_node)
                     if isinstance(n, ast.Constant)
                     and getattr(n, 'lineno', None) == source_span['line']
                     and getattr(n, 'col_offset', None) == source_span['col']
                     and getattr(n, 'end_lineno', None) == source_span['end_line']
                     and getattr(n, 'end_col_offset', None) == source_span['end_col']]
        if len(constants) != 1 or type(constants[0].value) not in (int, float, bool, str, bytes, type(None)):
            raise SourceError('Only unambiguous primitive source literals may be copied')
        start, end = _spans(doc.raw, constants[0])
        replacement = doc.raw[start:end].decode(doc.encoding)
    elif src['source_kind'] in ('operation','compare'):
        # Graph port identity alone does not authorize arbitrary expression
        # copying. Re-derive the exact AST expression and qualify its leaves.
        if source_port != src['id']+':outputs:result':
            raise SourceError('Only the expression result port is connectable')
        source_span=src.get('source_span')
        if not source_span:raise SourceError('Source expression span unavailable')
        valid_types=((ast.BinOp,ast.UnaryOp) if src['source_kind']=='operation'
                     else (ast.Compare,))
        candidates=[n for n in ast.walk(scope.ast_node) if isinstance(n,valid_types)
                    and getattr(n,'lineno',None)==source_span['line']
                    and getattr(n,'col_offset',None)==source_span['col']
                    and getattr(n,'end_lineno',None)==source_span['end_line']
                    and getattr(n,'end_col_offset',None)==source_span['end_col']]
        if len(candidates)!=1:raise SourceError('Source expression is ambiguous or stale')
        expression=candidates[0]
        _constant_expression_kind(expression)
        a,b=_spans(doc.raw,expression)
        x,y=_spans(doc.raw,selected)
        if a<y and x<b:raise SourceError('Cannot connect an expression into itself')
        replacement='('+doc.raw[a:b].decode(doc.encoding)+')'
    elif src['source_kind'] == 'call':
        # A CALL result is effectful and must NEVER be textually duplicated.
        # The only qualified connection is through an existing local that
        # already stores this exact invocation's result. The destination
        # reads that local, preserving the single original invocation.
        if source_port != src['id']+':outputs:result':
            raise SourceError('Only the stored Call result output is eligible')
        source_span=src.get('source_span')
        if not source_span:
            raise SourceError('Call source location is unavailable')
        calls=[n for n in ast.walk(scope.ast_node)
               if isinstance(n,ast.Call)
               and getattr(n,'lineno',None)==source_span['line']
               and getattr(n,'col_offset',None)==source_span['col']
               and getattr(n,'end_lineno',None)==source_span['end_line']
               and getattr(n,'end_col_offset',None)==source_span['end_col']]
        if len(calls)!=1:
            raise SourceError('Call identity is stale or ambiguous')
        call=calls[0]
        # Never assume an arbitrary nested call is a stored producer.
        # The direct assignment must correspond to a real SET node in the
        # current validated Python graph.
        direct_assignments=[n for n in ast.walk(scope.ast_node)
             if isinstance(n,(ast.Assign,ast.AnnAssign)) and n.value is call]
        if len(direct_assignments)!=1:
            raise SourceError('Call must have an existing single local assignment; implicit re-execution is forbidden')
        assigned=direct_assignments[0]
        target_names=(assigned.targets if isinstance(assigned,ast.Assign)
                      else [assigned.target])
        if len(target_names)!=1 or not isinstance(target_names[0],ast.Name):
            raise SourceError('Only a simple named local may store a Call result')
        assignment_nodes=[n for n in graph['nodes']
             if n.get('source_kind')=='assignment'
             and n.get('binding_name')==target_names[0].id
             and n.get('binding_statement_kind')=='assign'
             and n.get('source_span',{}).get('line')==assigned.lineno
             and n.get('source_span',{}).get('col')==assigned.col_offset]
        if len(assignment_nodes)!=1:
            raise SourceError('Call has no unique validated SET binding')
        replacement=_safe_preceding_local_binding(scope,assignment_nodes[0],target,selected)
    elif src['source_kind'] == 'assignment':
        output=next((p for p in src['draft_ports']['outputs'] if p['id']==source_port),None)
        if output is None or not output['id'].endswith(':value'):
            raise SourceError('Only the assigned-value port may be used for local rewiring')
        replacement=_safe_preceding_local_binding(scope,src,target,selected)
    else:
        # The parameter name is validated against the AST function signature.
        signature = doc.scopes[scope_key].ast_node.args
        arguments = [*signature.posonlyargs, *signature.args, *signature.kwonlyargs]
        if signature.vararg: arguments.append(signature.vararg)
        if signature.kwarg: arguments.append(signature.kwarg)
        name = next((arg.arg for arg in arguments
                     if src['id'] == f'py:{scope_key}|param|{arg.arg}'), None)
        if name is None or not name.isidentifier():
            raise SourceError('Parameter is not from this exact function declaration')
        replacement = name

    original_start, original_end = _spans(doc.raw, selected)
    if doc.raw[original_start:original_end].decode(doc.encoding) == replacement:
        raise SourceError('That operand already has this value')
    description=('Reference existing stored Call result (no re-execution)'
                 if src['source_kind']=='call'
                 else f'Replace expression operand using {src["source_kind"]} output')
    return _candidate(doc, selected, replacement, description)


@contextmanager
def _source_write_lock(path: Path, *, allow_missing: bool = False):
    """Serialize cooperating Studio writers across processes for one real path.

    The sidecar file deliberately persists: deleting a lockfile while another
    process holds it would let a new inode become a competing lock authority.
    This is advisory coordination for Studio writers, NOT a guarantee against
    editors that do not cooperate with our lock protocol.
    """
    if path.is_symlink() or (not allow_missing and not path.is_file()):
        raise SourceError('Refusing a symlink/missing source')
    try:
        identity = ((path.parent.resolve(strict=True) / path.name) if allow_missing
                    else path.resolve(strict=True))
        lock_path=identity.parent/('.'+identity.name+'.smi-lock')
        fd=os.open(lock_path, os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW|os.O_CLOEXEC, 0o600)
    except OSError as exc:
        raise SourceError('Cannot establish source write lock: '+str(exc)) from exc
    try:
        info=os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or
                info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)&0o077):
            raise SourceError('Unsafe source write lock ownership or permissions')
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield identity
    finally:
        os.close(fd)  # Closing releases the flock; the lock file must remain.


def create_source_exclusive(path: Path, candidate: bytes) -> Path:
    """Publish a new generated Python file via the existing source lock owner.

    Never replace a user file, symlink, or partially create a destination.
    The temporary file is private and synced before the hard-link publishes
    the final name with O_EXCL-equivalent semantics across processes.
    """
    if not isinstance(candidate, bytes) or not candidate:
        raise SourceError('Generated source must contain nonempty bytes')
    path=Path(path).expanduser().absolute()
    if path.suffix != '.py':
        raise SourceError('Generated source destination must end in .py')
    with _source_write_lock(path, allow_missing=True) as identity:
        if identity.exists() or identity.is_symlink():
            raise SourceError('Source destination already exists; no overwrite performed')
        temporary = None
        try:
            fd, temporary = tempfile.mkstemp(prefix='.smi-publish-',suffix='.tmp',dir=identity.parent)
            with os.fdopen(fd,'wb') as stream:
                stream.write(candidate); stream.flush(); os.fsync(stream.fileno())
            os.chmod(temporary,0o600)
            # os.link refuses an occupied destination even if it appears after
            # the earlier existence check. No unchecked os.replace here.
            try:
                os.link(temporary, identity, follow_symlinks=False)
            except FileExistsError as exc:
                raise SourceError('Source destination already exists; no overwrite performed') from exc
            directory_fd=os.open(identity.parent,os.O_RDONLY|getattr(os,'O_DIRECTORY',0))
            try:os.fsync(directory_fd)
            finally:os.close(directory_fd)
        finally:
            if temporary is not None:
                os.unlink(temporary)
    return identity


def apply_proposal(proposal: EditProposal):
    """Atomically publish an approved source revision with a shared write lock.

    An exact preimage is required *inside* the process-shared lock. Backup,
    temporary write, and final preimage verification all occur under that same
    lock. External programs that ignore advisory locks can still race; an
    ordinary filesystem has no universal compare-and-swap for path replacement.
    """
    with _source_write_lock(proposal.path) as path:
        original=path.read_bytes()
        if original!=proposal.original:
            raise SourceError('Source changed externally. Reload before editing.')
        directory=path.parent
        backup=directory/(path.name+'.smi-backup')
        # Do not clobber a prior backup; preserve the exact old revision.
        for count in range(1,1000):
            candidate=backup if count==1 else directory/(path.name+f'.smi-backup-{count}')
            if not candidate.exists() and not candidate.is_symlink():
                backup=candidate;break
        else:
            raise SourceError('Backup limit reached')
        backup_fd=None;temp=None
        try:
            backup_fd=os.open(str(backup),os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
            with os.fdopen(backup_fd,'wb') as f:
                backup_fd=None
                f.write(original);f.flush();os.fsync(f.fileno())
            fd,temp=tempfile.mkstemp(prefix='.smi-edit-',suffix='.tmp',dir=str(directory))
            with os.fdopen(fd,'wb') as f:
                f.write(proposal.candidate);f.flush();os.fsync(f.fileno())
            os.chmod(temp, stat.S_IMODE(path.stat().st_mode))
            if path.is_symlink() or path.read_bytes()!=original:
                raise SourceError('Source changed before commit; no overwrite performed')
            os.replace(temp,str(path));temp=None
            # Sync the directory entry so a completed publication survives
            # an abrupt crash on filesystems supporting directory fsync.
            try:
                directory_fd=os.open(directory,os.O_RDONLY|getattr(os,'O_DIRECTORY',0))
            except OSError:
                directory_fd=None
            if directory_fd is not None:
                try:
                    os.fsync(directory_fd)
                except OSError:
                    pass
                finally:
                    os.close(directory_fd)
        finally:
            if backup_fd is not None:os.close(backup_fd)
            if temp is not None:
                try:os.unlink(temp)
                except OSError:pass
        return backup


class SourceEditHistory:
    """Bounded in-process undo/redo for *committed* source transactions.

    Every reversal is itself applied by the existing guarded, backup-producing
    source writer. File bytes, not the graph scene or Qt editor, remain truth.
    Closing the app discards this optional history; backups remain on disk.
    """
    def __init__(self, max_entries: int = 16, max_files: int = 8):
        if max_entries < 1 or max_files < 1:
            raise ValueError('Source history bounds must be positive')
        self.max_entries=max_entries
        self.max_files=max_files
        self._documents={}

    def _key(self,path):
        return Path(path).absolute()

    def _stacks(self,path,create=False):
        key=self._key(path)
        if key not in self._documents and create:
            if len(self._documents)>=self.max_files:
                del self._documents[next(iter(self._documents))]
            self._documents[key]=([],[])
        return self._documents.get(key)

    def apply(self,proposal: EditProposal):
        """Record an edit only after its atomic, preimage-checked commit."""
        backup=apply_proposal(proposal)
        undo,redo=self._stacks(proposal.path,create=True)
        undo.append(proposal)
        del undo[:-self.max_entries]
        redo.clear()
        return backup

    def can_undo(self,path):
        stacks=self._stacks(path)
        return bool(stacks and stacks[0])

    def can_redo(self,path):
        stacks=self._stacks(path)
        return bool(stacks and stacks[1])

    def transition(self, path, *, redo: bool) -> tuple[Path, bytes]:
        """Move committed history once and identify the exact published revision.

        GUI projections must adopt this revision, not silently reload whatever
        happens to be on disk after the guarded write. Failed writes leave both
        history stacks untouched. This is the only undo/redo transition owner.
        """
        stacks=self._stacks(path)
        if not stacks or not stacks[1 if redo else 0]:
            raise SourceError('No committed source edit to '+('redo' if redo else 'undo'))
        undo,redo_stack=stacks
        entry=(redo_stack if redo else undo)[-1]
        publication=(entry if redo else
                     EditProposal(entry.path,entry.candidate,entry.original,
                                  entry.encoding,'Undo: '+entry.description))
        backup=apply_proposal(publication)
        if redo:
            redo_stack.pop()
            undo.append(entry)
        else:
            undo.pop()
            redo_stack.append(entry)
        return backup,publication.candidate

    def undo(self,path):
        return self.transition(path,redo=False)[0]

    def redo(self,path):
        return self.transition(path,redo=True)[0]
