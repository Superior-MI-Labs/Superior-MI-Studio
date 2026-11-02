"""Python adapter-qualified visual *creation* contracts.

An operation definition is a capability with a specific source lowering, not a
painted node template. The source file remains authoritative. Only this adapter
may lower these qualified operations; never emit text by reading arbitrary
source graph presentation labels or drawing connections.
"""
from __future__ import annotations
import ast
import keyword
import math
import builtins
import copy
import re
from .authoring_contract import QualifiedOperation, validate_catalog, OperandReference, BinaryComposition, ValueAssignment, CallComposition

from .python_graph import PythonDocument, SourceError
from .python_edit import EditProposal, _require_utf8, _validated_proposal




def definitions() -> tuple[QualifiedOperation, ...]:
    """Adapter-advertised capabilities; separate from observed occurrences."""
    return validate_catalog((
        QualifiedOperation(
            id='python.branch-early-return.v1', language='python', contract_version=1,
            title='Branch · early return on None',
            operation_kinds=('branch', 'return'),
            inputs=('parameter', 'return_literal', 'before_return'),
            control_outputs=('true', 'false'),
            lowering='source-insert-before-direct-return',
            capability='guarded-source-proposal'),
        QualifiedOperation(
            id='python.local-literal-return.v1', language='python', contract_version=1,
            title='Local value → Return',
            operation_kinds=('assignment', 'return'),
            inputs=('name', 'literal', 'before_return'),
            control_outputs=('next',),
            lowering='source-insert-local-and-replace-direct-return',
            capability='guarded-source-proposal'),
        QualifiedOperation(
            id='python.return-parameter-from-pass.v1', language='python', contract_version=1,
            title='Return parameter · connect value',
            operation_kinds=('return',),
            inputs=('parameter', 'pass_anchor'),
            control_outputs=(),
            lowering='source-replace-placeholder-with-parameter-return',
            capability='guarded-source-proposal'),
        QualifiedOperation(
            id='python.arithmetic-return-from-pass.v1', language='python', contract_version=1,
            title='Arithmetic · parameter → Return',
            operation_kinds=('arithmetic', 'return'),
            inputs=('parameter', 'arithmetic_operator', 'numeric_literal', 'pass_anchor'),
            control_outputs=(),
            lowering='source-replace-placeholder-with-arithmetic-result',
            capability='guarded-source-proposal'),
        QualifiedOperation(
            id='python.comparison-branch-return.v1', language='python', contract_version=1,
            title='Comparison → Branch · early Return',
            operation_kinds=('comparison', 'branch', 'return'),
            inputs=('parameter', 'comparison_operator', 'literal', 'return_literal', 'before_return'),
            control_outputs=('true', 'false'),
            lowering='source-insert-guarded-comparison-before-direct-return',
            capability='guarded-source-proposal'),
        QualifiedOperation(
            id='python.return-from-pass.v1', language='python', contract_version=1,
            title='Return · replace pass',
            operation_kinds=('return',),
            inputs=('literal', 'pass_anchor'),
            control_outputs=(),
            lowering='source-replace-function-placeholder',
            capability='guarded-source-proposal'),
        QualifiedOperation(
            id='python.call-return-from-pass.v1', language='python', contract_version=1,
            title='Function Call → Return', operation_kinds=('invocation','return'),
            inputs=('caller_parameter','callee','literal_arguments','pass_anchor'),
            control_outputs=(),lowering='source-replace-placeholder-with-qualified-call',
            capability='guarded-source-proposal'),
        QualifiedOperation(
            id='python.call-before-return.v1', language='python', contract_version=1,
            title='Function Call → Continue', operation_kinds=('invocation','return'),
            inputs=('caller_parameter','callee','literal_arguments','before_return'),
            control_outputs=('next',),lowering='source-insert-qualified-call-before-return',
            capability='guarded-source-proposal'),
        QualifiedOperation(
            id='python.create-function.v1', language='python', contract_version=1,
            title='Function · create definition',
            operation_kinds=('definition','return'),
            inputs=('name','parameters'), control_outputs=('entry','return'),
            lowering='source-append-function-placeholder',
            capability='guarded-source-proposal'),
        QualifiedOperation(
            id='python.create-main-entry.v1', language='python', contract_version=1,
            title='Program entry · call function',
            operation_kinds=('branch','invocation'),
            inputs=('zero_argument_function',),control_outputs=('true',),
            lowering='source-append-qualified-main-guard',
            capability='guarded-source-proposal'),
        QualifiedOperation(
            id='python.add-optional-keyword-parameter.v1',language='python',contract_version=1,
            title='Function · add optional input',
            operation_kinds=('definition','invocation'),
            inputs=('function','parameter','default_literal','update_local_calls'),
            control_outputs=(), lowering='source-update-signature-and-qualified-calls',
            capability='guarded-source-proposal'),
        QualifiedOperation(
            id='python.conditional-return-from-pass.v1',language='python',contract_version=1,
            title='Branch · True/False Returns', operation_kinds=('comparison','branch','return'),
            inputs=('parameter','comparison_operator','test_literal','true_literal','false_literal','pass_anchor'),
            control_outputs=('true','false'),lowering='source-replace-placeholder-with-branch-returns',
            capability='guarded-source-proposal'),
        QualifiedOperation(
            id='python.for-range-accumulate.v1',language='python',contract_version=1,
            title='For Range · accumulate values', operation_kinds=('assignment','loop','augmented_assignment','return'),
            inputs=('parameter','loop_variable','accumulator','pass_anchor'),
            control_outputs=('body','completed'), lowering='source-replace-placeholder-with-range-accumulator',
            capability='guarded-source-proposal'),
        QualifiedOperation(
            id='python.assign-source-local.v1',language='python',contract_version=1,
            title='Variable · store value / Return',
            operation_kinds=('assignment','return'),
            inputs=('source_operand_or_literal','fresh_local','return_connection'),
            control_outputs=(),lowering='source-insert-qualified-assignment-before-return',
            capability='guarded-source-proposal'),
        QualifiedOperation(
            id='python.compose-binary-local.v1',language='python',contract_version=1,
            title='Compose expression → local / Return',
            operation_kinds=('arithmetic','comparison','assignment','return'),
            inputs=('source_operand','operation','right_operand','fresh_local','return_connection'),
            control_outputs=(),lowering='source-insert-validated-binary-before-return',
            capability='guarded-source-proposal'),
        QualifiedOperation(
            id='python.call-with-values.v1',language='python',contract_version=1,
            title='Function Call · stored inputs → result',
            operation_kinds=('invocation','assignment','return'),
            inputs=('callee','scoped_arguments','fresh_local','return_connection'),
            control_outputs=('next',),lowering='source-insert-verified-local-call-before-return',
            capability='guarded-source-proposal'),
        QualifiedOperation(
            id='python.rename-parameter.v1',language='python',contract_version=1,
            title='Function Input · rename and update callers',
            operation_kinds=('definition','invocation','parameter'),
            inputs=('function','parameter','new_name'),control_outputs=(),
            lowering='source-rename-qualified-input-and-keyword-calls',
            capability='guarded-source-proposal'),
        QualifiedOperation(
            id='python.rename-function.v1',language='python',contract_version=1,
            title='Function · rename and update calls',
            operation_kinds=('definition','invocation'),
            inputs=('function','new_name'),control_outputs=(),
            lowering='source-rename-qualified-local-definition-and-call-sites',
            capability='guarded-source-proposal'),
        QualifiedOperation(
            id='python.while-countdown.v1',language='python',contract_version=1,
            title='While · countdown to zero',operation_kinds=('assignment','loop','augmented_assignment','return'),
            inputs=('parameter','counter','steps','pass_anchor'),
            control_outputs=('body','completed'),lowering='source-replace-placeholder-with-countdown',
            capability='guarded-source-proposal'),
    ))


def eligible_return_targets(doc: PythonDocument) -> tuple[tuple[str, tuple[str, ...], tuple[dict, ...]], ...]:
    """Only direct function returns, never conditional/loop/try nested returns."""
    result=[]
    for key, scope in doc.scopes.items():
        fn=scope.ast_node
        if scope.kind!='function' or not isinstance(fn,(ast.FunctionDef,ast.AsyncFunctionDef)):
            continue
        args=fn.args
        parameters=tuple(arg.arg for arg in (*args.posonlyargs,*args.args,*args.kwonlyargs))
        if args.vararg:parameters+=(args.vararg.arg,)
        if args.kwarg:parameters+=(args.kwarg.arg,)
        returns=[]
        for stmt in fn.body:
            if not isinstance(stmt,ast.Return):continue
            # Only own line at standard indentation. Inline suite statements
            # and semicolon-separated statements cannot be safely inserted.
            if _direct_statement(doc,stmt,b'return') is not None:
                returns.append({'line':stmt.lineno,'col':stmt.col_offset,
                                'end_line':stmt.end_lineno,'end_col':stmt.end_col_offset})
        if returns:
            result.append((key,parameters,tuple(returns)))
    return tuple(result)


def eligible_targets(doc: PythonDocument) -> tuple[tuple[str, tuple[str, ...], tuple[dict, ...]], ...]:
    """Early-return Branch needs at least one declared parameter."""
    return tuple(item for item in eligible_return_targets(doc) if item[1])



_COMPARE_OPS = {'==': ast.Eq, '!=': ast.NotEq, '<': ast.Lt,
                '<=': ast.LtE, '>': ast.Gt, '>=': ast.GtE}
_ARITHMETIC_OPS = {'+': ast.Add, '-': ast.Sub, '*': ast.Mult}


def _declared_parameters(fn: ast.AST) -> tuple[str, ...]:
    args=fn.args
    result=[a.arg for a in (*args.posonlyargs, *args.args, *args.kwonlyargs)]
    if args.vararg:result.append(args.vararg.arg)
    if args.kwarg:result.append(args.kwarg.arg)
    return tuple(result)


def _branch_proposal(doc: PythonDocument, scope_key: str, parameter: str,
                     comparison_operator: str, comparison_literal: str,
                     return_literal: str, before_return: dict) -> EditProposal:
    """Single adapter-owned Branch insertion for both qualified conditions.

    The requested comparison is a syntactic Python operation. Dynamic
    overloads, raises and runtime types are not inferred or guaranteed.
    No existing expression is moved or duplicated by this transformation.
    """
    _require_utf8(doc)
    fn,target=_target_return(doc,scope_key,before_return)
    if parameter not in _declared_parameters(fn):
        raise SourceError("Condition must use this function's declared parameter")
    span=_direct_statement(doc,target,b'return')
    if span is None:
        raise SourceError('Return must be a standalone, space-indented statement')
    ret=_parse_primitive_literal(return_literal)
    if comparison_operator=='is None':
        test=ast.Compare(left=ast.Name(id=parameter,ctx=ast.Load()),
            ops=[ast.Is()],comparators=[ast.Constant(value=None)])
        condition=parameter+' is None'
    else:
        op=_COMPARE_OPS.get(comparison_operator)
        if op is None:raise SourceError('Unsupported comparison operator')
        cmp=_parse_primitive_literal(comparison_literal)
        test=ast.Compare(left=ast.Name(id=parameter,ctx=ast.Load()),
            ops=[op()],comparators=[ast.Constant(value=cmp.value)])
        condition=parameter+' '+comparison_operator+' '+repr(cmp.value)
    prefix=span[2]
    nl=b'\r\n' if b'\r\n' in doc.raw else b'\n'
    # Insert at the beginning of the Return line, not at the token offset.
    line_start=span[0]-len(prefix)
    head=(prefix+b'if '+condition.encode('utf-8')+b':'+nl+
          prefix+b'    return '+repr(ret.value).encode('utf-8')+nl)
    proposal=_validated_proposal(doc,doc.raw[:line_start]+head+doc.raw[line_start:],
                       'Create Branch ('+condition+') with an early Return')
    updated=ast.parse(proposal.candidate.decode('utf-8'),filename=str(doc.path),type_comments=True)
    result=_function_at_path(updated,scope_key,doc)
    ix=fn.body.index(target)
    if len(result.body)!=len(fn.body)+1:
        raise SourceError('Branch insertion changed unrelated statement count')
    expected=ast.If(test=test, body=[ast.Return(value=ast.Constant(value=ret.value))],
                    orelse=[])
    if ast.dump(result.body[ix],include_attributes=False)!=ast.dump(expected,include_attributes=False):
        raise SourceError('New Branch/Return did not preserve requested comparison')
    previous=fn.body
    remaining=result.body[:ix]+result.body[ix+1:]
    if [ast.dump(x,include_attributes=False) for x in previous]!=[
            ast.dump(x,include_attributes=False) for x in remaining]:
        raise SourceError('Branch insertion modified existing code')
    return proposal


def propose_branch_early_return(doc: PythonDocument, scope_key: str,
                                parameter: str, return_literal: str,
                                before_return: dict) -> EditProposal:
    """Source-verified `parameter is None` Branch and early Return."""
    return _branch_proposal(doc,scope_key,parameter,'is None','None',
                            return_literal,before_return)


def propose_comparison_branch_return(doc: PythonDocument, scope_key: str,
                                     parameter: str, comparison_operator: str,
                                     comparison_literal: str, return_literal: str,
                                     before_return: dict) -> EditProposal:
    """Create an explicit comparison operation, Branch and early Return."""
    return _branch_proposal(doc,scope_key,parameter,comparison_operator,
                            comparison_literal,return_literal,before_return)


def _function_at_path(parsed: ast.Module, key: str, doc: PythonDocument):
    # Scope keys contain source declarations/line numbers. Follow the exact
    # parent structure by AST identity instead of resolving a name in an
    # arbitrary module; duplicate names and inner definitions are supported.
    chain=[]
    cursor=key
    while cursor!='module':
        item=doc.scopes.get(cursor)
        if item is None:raise SourceError('Scope no longer exists')
        chain.append(item.ast_node)
        cursor=item.parent
    nodes=parsed.body
    for old in reversed(chain):
        candidates=[n for n in nodes if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))
                    and n.name==old.name and n.lineno==old.lineno and n.col_offset==old.col_offset]
        if len(candidates)!=1:raise SourceError('Cannot uniquely resolve function after generation')
        current=candidates[0]
        nodes=current.body
    return current


# Shared Python-adapter authoring gates. They do not implement another editor,
# parser or write mechanism. All creation routes finish at _validated_proposal.
def _parse_primitive_literal(text: str) -> ast.Constant:
    if not isinstance(text,str) or len(text)>150:
        raise SourceError('A short Python primitive literal is required')
    try:
        node=ast.parse(text,mode='eval').body
    except (SyntaxError,ValueError,TypeError) as exc:
        raise SourceError(f'Invalid literal: {exc}') from exc
    # Python parses negative numeric literals as UnaryOp(Constant), never as
    # Constant. This remains a *single literal*, not arbitrary arithmetic.
    if (isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.USub,ast.UAdd)) and
            isinstance(node.operand,ast.Constant) and
            type(node.operand.value) in (int,float)):
        value = -node.operand.value if isinstance(node.op,ast.USub) else +node.operand.value
        node = ast.Constant(value=value)
    if not isinstance(node,ast.Constant) or type(node.value) not in (int,float,bool,str,bytes,type(None)):
        raise SourceError('Only primitive literals, not expressions or calls, are qualified')
    if isinstance(node.value,(str,bytes)) and len(node.value)>100:
        raise SourceError('Literal exceeds the maximum size')
    if isinstance(node.value,float) and not math.isfinite(node.value):
        raise SourceError('Non-finite float cannot be represented as a standalone literal')
    return node


def _direct_statement(doc: PythonDocument, statement: ast.stmt, word: bytes):
    """Resolve an exact, standalone, space-indented AST statement byte range."""
    lines=doc.raw.splitlines(keepends=True)
    if statement.lineno != statement.end_lineno or not (1<=statement.lineno<=len(lines)):
        return None
    line=lines[statement.lineno-1]
    prefix=line[:statement.col_offset]
    if not prefix or any(c!=0x20 for c in prefix) or statement.col_offset>160:
        return None
    body=line[statement.col_offset:statement.end_col_offset]
    tail=line[statement.end_col_offset:].rstrip(b'\r\n')
    if not body.startswith(word) or tail.strip() or b';' in body:
        return None
    offset=sum(map(len,lines[:statement.lineno-1]))
    return offset+statement.col_offset,offset+statement.end_col_offset,prefix


def _target_return(doc: PythonDocument, scope_key: str, anchor: dict):
    valid={key:returns for key,_,returns in eligible_return_targets(doc)}
    if scope_key not in valid or anchor not in valid[scope_key]:
        raise SourceError('Direct Return anchor is no longer qualified; reload before editing')
    fn=doc.scopes[scope_key].ast_node
    result=next((n for n in fn.body if isinstance(n,ast.Return) and
                 n.lineno==anchor['line'] and n.col_offset==anchor['col'] and
                 n.end_lineno==anchor['end_line'] and n.end_col_offset==anchor['end_col']),None)
    if result is None:
        raise SourceError('Return anchor has changed')
    return fn,result


def _fresh_local_name(fn: ast.AST, name: str):
    if not isinstance(name,str) or len(name)>64 or not name.isidentifier() or keyword.iskeyword(name):
        raise SourceError('New local variable must be a valid Python identifier (up to 64 characters)')
    if name.startswith('__'):
        raise SourceError('Reserved dunder identifiers are not eligible for new locals')
    # This conservative check includes nested definitions and all argument
    # declarations. It refuses ambiguous existing names instead of pretending
    # that a graph connection has proven binding/dominance.
    for node in ast.walk(fn):
        if (isinstance(node,ast.Name) and node.id==name or
            isinstance(node,ast.arg) and node.arg==name or
            isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and node.name==name or
            isinstance(node,(ast.Global,ast.Nonlocal)) and name in node.names or
            isinstance(node,ast.alias) and (node.asname or node.name.split('.')[0])==name or
            isinstance(node,ast.ExceptHandler) and node.name==name):
            raise SourceError('The requested local name already occurs in this function')


def propose_local_literal_return(doc: PythonDocument, scope_key: str,
                                 name: str, literal_text: str,
                                 before_return: dict) -> EditProposal:
    """Create a local assignment and wire the selected Return to its value.

    Only a single, effect-free name/constant original Return is eligible.
    Replacing calls or compound expressions would silently discard their
    effects, so the adapter refuses them. This is a single reviewed transaction.
    """
    _require_utf8(doc)
    fn,old=_target_return(doc,scope_key,before_return)
    if old.value is not None and not isinstance(old.value,(ast.Name,ast.Constant)):
        raise SourceError('Only a simple name, constant, or empty Return can be replaced')
    span=_direct_statement(doc,old,b'return')
    if span is None:
        raise SourceError('Return must be a standalone statement without trailing code/comments')
    _fresh_local_name(fn,name)
    value=_parse_primitive_literal(literal_text)
    beginning,end,prefix=span
    newline=b'\r\n' if b'\r\n' in doc.raw else b'\n'
    assignment=prefix+name.encode('utf-8')+b' = '+repr(value.value).encode('utf-8')+newline
    updated=(doc.raw[:beginning-len(prefix)]+assignment+prefix+
             b'return '+name.encode('utf-8')+doc.raw[end:])
    proposal=_validated_proposal(doc,updated,f'Create local {name!r} and wire its value to Return')
    parsed=ast.parse(proposal.candidate.decode('utf-8'),filename=str(doc.path),type_comments=True)
    changed=_function_at_path(parsed,scope_key,doc)
    index=fn.body.index(old)
    if len(changed.body)!=len(fn.body)+1:
        raise SourceError('Unexpected statement count after creating local binding')
    binding,new_return=changed.body[index:index+2]
    if not (isinstance(binding,ast.Assign) and len(binding.targets)==1 and
            isinstance(binding.targets[0],ast.Name) and binding.targets[0].id==name and
            isinstance(binding.value,ast.Constant) and type(binding.value.value)==type(value.value) and
            binding.value.value==value.value and
            isinstance(new_return,ast.Return) and isinstance(new_return.value,ast.Name) and
            new_return.value.id==name):
        raise SourceError('Assignment-to-Return connection did not round-trip')
    before=fn.body[:index]+fn.body[index+1:]
    after=changed.body[:index]+changed.body[index+2:]
    if [ast.dump(n,include_attributes=False) for n in before]!=[ast.dump(n,include_attributes=False) for n in after]:
        raise SourceError('Existing statements were modified unexpectedly')
    return proposal


def eligible_pass_targets(doc: PythonDocument) -> tuple[tuple[str, dict], ...]:
    """Pass-only function implementations, with optional leading docstring."""
    result=[]
    for key,scope in doc.scopes.items():
        fn=scope.ast_node
        if scope.kind!='function' or not isinstance(fn,(ast.FunctionDef,ast.AsyncFunctionDef)):
            continue
        statements=fn.body
        if (statements and isinstance(statements[0],ast.Expr) and
                isinstance(statements[0].value,ast.Constant) and
                isinstance(statements[0].value.value,str)):
            statements=statements[1:]
        if len(statements)!=1 or not isinstance(statements[0],ast.Pass):
            continue
        target=statements[0]
        if _direct_statement(doc,target,b'pass') is not None:
            result.append((key,dict(line=target.lineno,col=target.col_offset,
                                    end_line=target.end_lineno,end_col=target.end_col_offset)))
    return tuple(result)


def propose_return_from_pass(doc: PythonDocument, scope_key: str,
                             literal_text: str, pass_anchor: dict) -> EditProposal:
    """Replace a function's sole placeholder Pass with a real Return result."""
    _require_utf8(doc)
    if not isinstance(pass_anchor,dict) or (scope_key,pass_anchor) not in eligible_pass_targets(doc):
        raise SourceError('Placeholder function changed or has unsupported statements')
    literal=_parse_primitive_literal(literal_text)
    fn=doc.scopes[scope_key].ast_node
    target=next(n for n in fn.body if isinstance(n,ast.Pass))
    span=_direct_statement(doc,target,b'pass')
    if span is None:
        raise SourceError('Pass placeholder is not a standalone statement')
    beginning,end,_=span
    replacement=b'return '+repr(literal.value).encode('utf-8')
    proposal=_validated_proposal(doc,doc.raw[:beginning]+replacement+doc.raw[end:],
                                'Replace placeholder with Return result')
    parsed=ast.parse(proposal.candidate.decode('utf-8'),filename=str(doc.path),type_comments=True)
    changed=_function_at_path(parsed,scope_key,doc)
    index=fn.body.index(target)
    new=changed.body[index]
    if not (len(fn.body)==len(changed.body) and isinstance(new,ast.Return) and
            isinstance(new.value,ast.Constant) and type(new.value.value)==type(literal.value) and
            new.value.value==literal.value):
        raise SourceError('Placeholder did not round-trip into a Return')
    prior=fn.body[:index]+fn.body[index+1:]
    subsequent=changed.body[:index]+changed.body[index+1:]
    if [ast.dump(n,include_attributes=False) for n in prior]!=[ast.dump(n,include_attributes=False) for n in subsequent]:
        raise SourceError('Non-placeholder statements changed unexpectedly')
    return proposal



def eligible_parameter_returns(doc: PythonDocument):
    """Exact adapter-owned (scope, parameter, placeholder) creation sites."""
    matches=[]
    for scope,anchor in eligible_pass_targets(doc):
        args=doc.scopes[scope].ast_node.args
        declared=[a.arg for a in (*args.posonlyargs,*args.args,*args.kwonlyargs)]
        if args.vararg:declared.append(args.vararg.arg)
        if args.kwarg:declared.append(args.kwarg.arg)
        for name in declared:matches.append((scope,name,anchor))
    return tuple(matches)


def compatible_parameter_pin(doc: PythonDocument, node_id: str, port_id: str):
    """Source-qualified pin -> eligible function placeholder, never a UI guess.

    Match identities generated by the Python adapter and verify the underlying
    function signature and pass anchor. Output is (scope, parameter, anchor).
    Other data/execution pins are not silently converted or autoconnected.
    """
    if not isinstance(node_id, str) or not isinstance(port_id, str):
        return ()
    return tuple((scope,name,anchor) for scope,name,anchor in eligible_parameter_returns(doc)
                 if node_id==f'py:{scope}|param|{name}' and
                 port_id==f'py:{scope}|param|{name}:outputs:{name}')


def propose_return_parameter_from_pass(doc: PythonDocument, scope_key: str,
                                       parameter: str, pass_anchor: dict) -> EditProposal:
    """Make a real data connection from the function's parameter to Return.

    The caller provides a parameter output port and the target Pass, but only
    the Python adapter resolves those into source syntax. This validates the
    parser round trip and preserves every unrelated statement and source byte.
    """
    _require_utf8(doc)
    if not isinstance(pass_anchor, dict) or (scope_key,pass_anchor) not in eligible_pass_targets(doc):
        raise SourceError('No eligible placeholder for this function')
    fn=doc.scopes[scope_key].ast_node
    declared={a.arg for a in (*fn.args.posonlyargs,*fn.args.args,*fn.args.kwonlyargs)}
    if fn.args.vararg:declared.add(fn.args.vararg.arg)
    if fn.args.kwarg:declared.add(fn.args.kwarg.arg)
    if parameter not in declared:
        raise SourceError('Return must connect to a declared parameter of this function')
    anchor=next(n for n in fn.body if isinstance(n,ast.Pass))
    span=_direct_statement(doc,anchor,b'pass')
    if span is None:raise SourceError('Pass placeholder is not a standalone statement')
    beginning,end,_=span
    proposal=_validated_proposal(doc,doc.raw[:beginning]+b'return '+parameter.encode('utf-8')+doc.raw[end:],
                                 'Connect parameter '+parameter+' to function Return')
    parsed=ast.parse(proposal.candidate.decode('utf-8'),filename=str(doc.path),type_comments=True)
    changed=_function_at_path(parsed,scope_key,doc)
    at=fn.body.index(anchor)
    ret=changed.body[at]
    if not (len(changed.body)==len(fn.body) and isinstance(ret,ast.Return)
            and isinstance(ret.value,ast.Name) and ret.value.id==parameter):
        raise SourceError('Parameter Return did not round-trip')
    original=[ast.dump(n,include_attributes=False) for i,n in enumerate(fn.body) if i!=at]
    generated=[ast.dump(n,include_attributes=False) for i,n in enumerate(changed.body) if i!=at]
    if original!=generated:raise SourceError('Unrelated function statements changed')
    return proposal


def propose_arithmetic_return_from_pass(doc: PythonDocument, scope_key: str,
                                        parameter: str, operator: str,
                                        numeric_literal: str, pass_anchor: dict) -> EditProposal:
    """Create `return parameter OP number` from a pass placeholder.

    The AST graph derives the same parameter and literal through a BinOp.
    Python dynamic dispatch/operand type is deliberately *not* inferred from
    annotations. This function edits no existing executable expression.
    """
    _require_utf8(doc)
    if not isinstance(pass_anchor,dict) or (scope_key,pass_anchor) not in eligible_pass_targets(doc):
        raise SourceError('Function placeholder is not an eligible source anchor')
    fn=doc.scopes[scope_key].ast_node
    if parameter not in _declared_parameters(fn):
        raise SourceError('Arithmetic input must be a declared parameter')
    op_type=_ARITHMETIC_OPS.get(operator)
    if op_type is None:
        raise SourceError('Only qualified +, -, * arithmetic operations can be created')
    literal=_parse_primitive_literal(numeric_literal)
    if type(literal.value) not in (int,float):
        raise SourceError('Arithmetic operand must be a finite numeric primitive')
    target=next(n for n in fn.body if isinstance(n,ast.Pass))
    span=_direct_statement(doc,target,b'pass')
    if span is None:raise SourceError('Placeholder must be a standalone statement')
    start,end,_=span
    content=('return '+parameter+' '+operator+' '+repr(literal.value)).encode('utf-8')
    proposal=_validated_proposal(doc,doc.raw[:start]+content+doc.raw[end:],
                                'Create arithmetic expression from parameter to Return')
    parsed=ast.parse(proposal.candidate.decode('utf-8'),filename=str(doc.path),type_comments=True)
    updated=_function_at_path(parsed,scope_key,doc)
    ix=fn.body.index(target)
    expected=ast.Return(value=ast.BinOp(left=ast.Name(id=parameter,ctx=ast.Load()),
                                      op=op_type(),right=ast.Constant(value=literal.value)))
    if len(updated.body)!=len(fn.body) or ast.dump(updated.body[ix],include_attributes=False)!=ast.dump(expected,include_attributes=False):
        raise SourceError('Arithmetic/Return did not round-trip through Python AST')
    if [ast.dump(n,include_attributes=False) for i,n in enumerate(updated.body) if i!=ix]!=[
        ast.dump(n,include_attributes=False) for i,n in enumerate(fn.body) if i!=ix]:
        raise SourceError('Unrelated statements changed during arithmetic creation')
    return proposal


def compatible_parameter_return_pin(doc: PythonDocument, node_id: str, port_id: str):
    """A selected parameter can drive a Branch before a direct Return.

    Same exact identity rules as pass-backed Return creation; never infer
    compatibility from a visually matching pin color or label.
    """
    if not isinstance(node_id,str) or not isinstance(port_id,str):return ()
    return tuple((scope,name,anchor) for scope,parameters,anchors in eligible_targets(doc)
                 for name in parameters for anchor in anchors
                 if node_id==f'py:{scope}|param|{name}' and
                 port_id==f'py:{scope}|param|{name}:outputs:{name}')


# Qualified call construction. A direct lexical name is not proof of runtime
# purity or dispatch; it only proves a non-ambiguous source signature under
# this restricted local adapter. We never execute the function or evaluate
# arguments to offer a builder. Each approved edit is reparsed as Python AST.
def qualified_callees(doc: PythonDocument, caller_scope: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Unambiguous module definitions with 1–4 required positional inputs.

    No default, keyword-only, decorator, import alias, or binding that could
    turn the direct name into an obviously different target is accepted.
    Other runtime rebinding via dynamic Python execution remains unknowable.
    """
    caller=doc.scopes.get(caller_scope)
    if (caller is None or caller.kind!='function' or caller.parent!='module' or
            not isinstance(caller.ast_node,(ast.FunctionDef,ast.AsyncFunctionDef))):
        return ()
    definitions={}
    for node in doc.tree.body:
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
            definitions.setdefault(node.name,[]).append(node)
    results=[]
    for name,items in definitions.items():
        if len(items)!=1 or name==caller.ast_node.name:
            continue
        fn=items[0]
        if not isinstance(fn,ast.FunctionDef) or fn.decorator_list:
            continue
        args=fn.args
        if (args.defaults or args.kw_defaults and any(x is not None for x in args.kw_defaults)
                or args.kwonlyargs or args.vararg or args.kwarg):
            continue
        positional=tuple(a.arg for a in (*args.posonlyargs,*args.args))
        if not 1<=len(positional)<=4:
            continue
        # Explicit rebinding in any visible lexical scope makes the name
        # unsuitable for a source-generated direct-call shorthand.
        if any((isinstance(n,ast.Name) and n.id==name and isinstance(n.ctx,(ast.Store,ast.Del)))
                or (isinstance(n,(ast.Import,ast.ImportFrom)) and any(
                    (alias.asname or alias.name.split('.')[0])==name for alias in n.names))
                for n in ast.walk(doc.tree)):
            continue
        # No caller-local shadowing of the referenced global function.
        if caller.table is None:
            continue
        try:
            symbol=caller.table.lookup(name)
        except KeyError:
            symbol=None  # An unreferenced module name is not a caller-local shadow.
        if symbol and (symbol.is_local() or symbol.is_parameter() or
                       symbol.is_imported() or symbol.is_free()):
            continue
        results.append((name,positional))
    return tuple(sorted(results))


def eligible_call_pass_targets(doc: PythonDocument):
    """One shared qualification query for Palette, pin-drop and lowering."""
    return tuple((scope,anchor,qualified_callees(doc,scope))
                 for scope,anchor in eligible_pass_targets(doc)
                 if _declared_parameters(doc.scopes[scope].ast_node) and qualified_callees(doc,scope))


def eligible_call_return_targets(doc: PythonDocument):
    return tuple((scope,anchor,qualified_callees(doc,scope))
                 for scope,_,anchors in eligible_return_targets(doc)
                 for anchor in anchors
                 if _declared_parameters(doc.scopes[scope].ast_node) and qualified_callees(doc,scope))


def _qualified_call(doc,scope_key,parameter,callee,literal_arguments):
    fn=doc.scopes.get(scope_key)
    if not fn or parameter not in _declared_parameters(fn.ast_node):
        raise SourceError('Call input must be an actual parameter of the target function')
    targets=dict(qualified_callees(doc,scope_key))
    if callee not in targets:
        raise SourceError('Called function is not an unambiguous qualified module definition')
    expected=len(targets[callee])-1
    if not isinstance(literal_arguments,(tuple,list)) or len(literal_arguments)!=expected:
        raise SourceError(f'Call requires exactly {expected} additional literal arguments')
    literals=tuple(_parse_primitive_literal(value) for value in literal_arguments)
    args=[ast.Name(id=parameter,ctx=ast.Load()),*literals]
    call=ast.Call(func=ast.Name(id=callee,ctx=ast.Load()),args=args,keywords=[])
    # Encode the language tokens, not labels from the graph renderer.
    expression=(callee+'('+', '.join([parameter,*(repr(value.value) for value in literals)])+')')
    return call,expression.encode('utf-8')


def propose_call_return_from_pass(doc: PythonDocument,scope_key:str,
                                  parameter:str,callee:str,literal_arguments,
                                  pass_anchor:dict)->EditProposal:
    """Create Call → Return from a standalone placeholder through the one editor."""
    _require_utf8(doc)
    if not any(s==scope_key and a==pass_anchor for s,a,_ in eligible_call_pass_targets(doc)):
        raise SourceError('Call destination is not an eligible pass-only function')
    fn=doc.scopes[scope_key].ast_node
    call,source=_qualified_call(doc,scope_key,parameter,callee,literal_arguments)
    old=next(n for n in fn.body if isinstance(n,ast.Pass))
    span=_direct_statement(doc,old,b'pass')
    if span is None:raise SourceError('Placeholder location is not a standalone Pass')
    start,end,_=span
    proposal=_validated_proposal(doc,doc.raw[:start]+b'return '+source+doc.raw[end:],
                                 f'Create function Call {callee} feeding Return')
    updated=_function_at_path(ast.parse(proposal.candidate.decode('utf-8'),type_comments=True),
                              scope_key,doc)
    position=fn.body.index(old)
    expected=ast.Return(value=call)
    if (len(updated.body)!=len(fn.body) or
        ast.dump(updated.body[position],include_attributes=False)!=ast.dump(expected,include_attributes=False) or
        [ast.dump(n,include_attributes=False) for i,n in enumerate(updated.body) if i!=position]!=
        [ast.dump(n,include_attributes=False) for i,n in enumerate(fn.body) if i!=position]):
        raise SourceError('New Call/Return did not round-trip without modifying unrelated statements')
    return proposal


def propose_call_before_return(doc:PythonDocument,scope_key:str,
                               parameter:str,callee:str,literal_arguments,
                               return_anchor:dict)->EditProposal:
    """Explicitly create an invocation with a subsequent existing Return.

    This is an effectful operation by definition; it is never implicitly
    inserted by a value-wire interaction or assumed safe/pure by the adapter.
    """
    _require_utf8(doc)
    if not any(s==scope_key and a==return_anchor for s,a,_ in eligible_call_return_targets(doc)):
        raise SourceError('Call destination must be a qualified direct Return')
    fn,target=_target_return(doc,scope_key,return_anchor)
    call,source=_qualified_call(doc,scope_key,parameter,callee,literal_arguments)
    span=_direct_statement(doc,target,b'return')
    if span is None:raise SourceError('Return location no longer supports insertion')
    start,_,indent=span
    newline=b'\r\n' if b'\r\n' in doc.raw else b'\n'
    insertion=indent+source+newline
    beginning=start-len(indent)
    proposal=_validated_proposal(doc,doc.raw[:beginning]+insertion+doc.raw[beginning:],
                                 f'Create explicit Call {callee} before Return')
    updated=_function_at_path(ast.parse(proposal.candidate.decode('utf-8'),type_comments=True),
                              scope_key,doc)
    index=fn.body.index(target)
    expected=ast.Expr(value=call)
    if (len(updated.body)!=len(fn.body)+1 or
        ast.dump(updated.body[index],include_attributes=False)!=ast.dump(expected,include_attributes=False) or
        [ast.dump(n,include_attributes=False) for i,n in enumerate(updated.body) if i!=index]!=
        [ast.dump(n,include_attributes=False) for n in fn.body]):
        raise SourceError('Inserted Call changed existing program statements')
    return proposal


# v2.40: Python-only program construction. All transformations are proposals
# into the existing guarded source writer; NONE execute imported Python.
# Inputs remain conservative because Python name binding is dynamic.

def _new_identifier(name: str, *, role: str = 'Identifier') -> str:
    if (not isinstance(name,str) or not 0 < len(name) <= 64 or
            not name.isidentifier() or keyword.iskeyword(name) or
            name.startswith('__')):
        raise SourceError(f'{role} must be a Python identifier (1–64 characters, not reserved)')
    return name


def _parameter_names(spec: str) -> tuple[str, ...]:
    if not isinstance(spec,str) or len(spec)>512:
        raise SourceError('Function parameter list is too long')
    names=tuple(x.strip() for x in spec.split(',')) if spec.strip() else ()
    if len(names)>12 or any(not x for x in names):
        raise SourceError('Use at most twelve comma-separated parameter names')
    for name in names:_new_identifier(name,role='Parameter')
    if len(set(names))!=len(names):raise SourceError('Function parameters must be unique')
    return names


def _global_name_mentioned(tree: ast.Module, name: str) -> bool:
    # Refuse additions that might change the binding of a pre-existing Name
    # reference, including in nested scopes. Conservative is intentional.
    for node in ast.walk(tree):
        if (isinstance(node,ast.Name) and node.id==name or
            isinstance(node,ast.arg) and node.arg==name or
            isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and node.name==name or
            isinstance(node,ast.alias) and (node.asname or node.name.split('.')[0])==name or
            isinstance(node,(ast.Global,ast.Nonlocal)) and name in node.names):
            return True
    return False


def propose_create_function(doc: PythonDocument, name: str, parameters: str = '') -> EditProposal:
    """Append one module-scope function with a real placeholder implementation.

    Existing module statements remain AST-identical. The subsequent existing
    Return/Branch/Call builders fill this function using the same catalog.
    """
    _require_utf8(doc)
    name=_new_identifier(name,role='Function')
    if name in dir(builtins) or _global_name_mentioned(doc.tree,name):
        raise SourceError('Function name shadows an existing source identifier or builtin')
    arguments=_parameter_names(parameters)
    nl=b'\r\n' if b'\r\n' in doc.raw else b'\n'
    separator=b'' if not doc.raw or doc.raw.endswith((b'\n',b'\r')) else nl
    gap=nl if doc.raw.strip() else b''
    addition=(f'def {name}({", ".join(arguments)}):'.encode('utf-8')+
              nl+b'    pass'+nl)
    proposal=_validated_proposal(doc,doc.raw+separator+gap+addition,
                                 f'Create Python function {name} with {len(arguments)} inputs')
    parsed=ast.parse(proposal.candidate.decode('utf-8'),type_comments=True)
    if len(parsed.body)!=len(doc.tree.body)+1:
        raise SourceError('Creating a function altered existing module statements')
    if ast.dump(ast.Module(body=parsed.body[:-1],type_ignores=parsed.type_ignores),include_attributes=False)!=ast.dump(doc.tree,include_attributes=False):
        raise SourceError('Creating a function altered existing Python source')
    fn=parsed.body[-1]
    if (not isinstance(fn,ast.FunctionDef) or fn.name!=name or
            tuple(x.arg for x in fn.args.args)!=arguments or
            len(fn.body)!=1 or not isinstance(fn.body[0],ast.Pass)):
        raise SourceError('Function definition failed AST round-trip')
    return proposal


def eligible_entry_functions(doc: PythonDocument) -> tuple[str,...]:
    """Single unambiguous zero-required-argument direct functions for main."""
    if (any(isinstance(node,ast.If) and isinstance(node.test,ast.Compare) and
            isinstance(node.test.left,ast.Name) and node.test.left.id=='__name__'
            for node in doc.tree.body) or _global_name_mentioned(doc.tree,'print')):
        return ()
    defined=[node for node in doc.tree.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))]
    eligible=[]
    for fn in defined:
        if (not isinstance(fn,ast.FunctionDef) or fn.decorator_list or
                fn.args.posonlyargs or fn.args.args or fn.args.kwonlyargs or
                fn.args.vararg or fn.args.kwarg or fn.args.defaults or fn.args.kw_defaults or
                sum(isinstance(other,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and other.name==fn.name
                    for other in doc.tree.body)!=1):
            continue
        # An assignment/import to the same name would make call dispatch ambiguous.
        if any((isinstance(node,ast.Name) and node.id==fn.name and isinstance(node.ctx,(ast.Store,ast.Del))) or
               (isinstance(node,ast.alias) and (node.asname or node.name.split('.')[0])==fn.name)
               for node in ast.walk(doc.tree)):
            continue
        eligible.append(fn.name)
    return tuple(eligible)


def propose_create_main_entry(doc:PythonDocument, function_name:str)->EditProposal:
    """Append explicit main guard. Only direct zero-argument module functions."""
    _require_utf8(doc)
    if function_name not in eligible_entry_functions(doc):
        raise SourceError('Select an unambiguous zero-argument module function without an existing main guard')
    nl=b'\r\n' if b'\r\n' in doc.raw else b'\n'
    separator=b'' if not doc.raw or doc.raw.endswith((b'\r',b'\n')) else nl
    fragment=(b'if __name__ == "__main__":'+nl+
              b'    print('+function_name.encode('utf-8')+b'())'+nl)
    proposal=_validated_proposal(doc,doc.raw+separator+(nl if doc.raw.strip() else b'')+fragment,
                                  f'Create main entry invoking {function_name}')
    parsed=ast.parse(proposal.candidate.decode('utf-8'),type_comments=True)
    old=doc.tree.body
    if (len(parsed.body)!=len(old)+1 or
            [ast.dump(n,include_attributes=False) for n in parsed.body[:-1]]!=
            [ast.dump(n,include_attributes=False) for n in old]):
        raise SourceError('Adding the program entry modified existing statements')
    guard=parsed.body[-1]
    if (not isinstance(guard,ast.If) or len(guard.body)!=1 or
            not isinstance(guard.body[0],ast.Expr) or
            not isinstance(guard.body[0].value,ast.Call) or
            not isinstance(guard.body[0].value.func,ast.Name) or
            guard.body[0].value.func.id!='print'):
        raise SourceError('Main entry did not reparse as a qualified call')
    return proposal


def eligible_signature_functions(doc:PythonDocument)->tuple[str,...]:
    """Function interfaces for safe one-line keyword-only default insertion."""
    result=[]
    lines=doc.raw.splitlines(keepends=True)
    for fn in doc.tree.body:
        if not isinstance(fn,ast.FunctionDef) or fn.decorator_list or fn.args.kwarg:
            continue
        if sum(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and n.name==fn.name
               for n in doc.tree.body)!=1:
            continue
        line=lines[fn.lineno-1].decode('utf-8') if fn.lineno<=len(lines) else ''
        # Deliberately restrict to signatures with one line and simple header.
        if not re.fullmatch(r'def '+re.escape(fn.name)+r'\([^()\r\n]*\)\s*:\s*(?:#.*)?\r?\n?',line):
            continue
        if len(line)>500 or (';' in line) or fn.body[0].lineno==fn.lineno:
            continue
        result.append(fn.name)
    return tuple(result)


def _shadowed_call_name(tree:ast.Module,callee:str)->bool:
    """Reject local binding that would make a textually matched call ambiguous."""
    for node in ast.walk(tree):
        if ((isinstance(node,ast.Name) and node.id==callee and isinstance(node.ctx,(ast.Store,ast.Del))) or
            (isinstance(node,ast.arg) and node.arg==callee) or
            (isinstance(node,ast.alias) and (node.asname or node.name.split('.')[0])==callee) or
            (isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and
             node.name==callee and node not in tree.body) or
            (isinstance(node,(ast.ExceptHandler,ast.MatchAs,ast.MatchStar)) and
             node.name==callee) or
            (isinstance(node,(ast.Global,ast.Nonlocal)) and callee in node.names)):
            return True
    return False


def propose_add_optional_parameter(doc:PythonDocument,function_name:str,
                                    parameter:str,default_literal:str,
                                    *,update_local_calls:bool=True)->EditProposal:
    """Add a backwards-compatible keyword-only input and update safe direct calls.

    Existing external callers remain valid because the new parameter has a
    primitive default. Qualified direct-name local calls may explicitly receive
    the same default; dynamic calls are not rewritten or falsely certified.
    """
    _require_utf8(doc)
    if function_name not in eligible_signature_functions(doc):
        raise SourceError('Function signature is not a qualified one-line module definition')
    parameter=_new_identifier(parameter,role='New parameter')
    fn=next(n for n in doc.tree.body if isinstance(n,ast.FunctionDef) and n.name==function_name)
    # A new parameter is a local binding. It must not silently capture an
    # existing global read or overwrite a body-local variable of this name.
    _fresh_local_name(fn,parameter)
    default=_parse_primitive_literal(default_literal)
    rendered=repr(default.value).encode('utf-8')
    if update_local_calls and _shadowed_call_name(doc.tree,function_name):
        raise SourceError('Local binding shadows the function name; call-site updates are unsafe')
    lines=doc.raw.splitlines(keepends=True)
    start=sum(map(len,lines[:fn.lineno-1]))
    line=lines[fn.lineno-1]
    closing=line.rfind(b')')
    if closing<0:raise SourceError('Function closing parenthesis cannot be located')
    original=line[line.index(b'(')+1:closing].strip()
    if b'**' in original or b'/' in original:
        raise SourceError('Variadic keyword and positional-only interfaces are not qualified')
    if fn.args.vararg or fn.args.kwonlyargs:
        addition=b', '+parameter.encode()+b'='+rendered
    else:
        addition=(b', ' if original else b'')+b'*, '+parameter.encode()+b'='+rendered
    edits=[(start+closing,start+closing,addition)]
    original_calls=[]
    if update_local_calls:
        for call in ast.walk(doc.tree):
            if not (isinstance(call,ast.Call) and isinstance(call.func,ast.Name) and call.func.id==function_name):
                continue
            if (any(isinstance(arg,ast.Starred) for arg in call.args) or
                    any(kw.arg is None or kw.arg==parameter for kw in call.keywords)):
                raise SourceError('Starred/duplicate call arguments cannot be updated safely')
            # Qualify exact AST call boundary. The call's closing ')' is always
            # the final token for an ordinary Python Call expression.
            from .python_edit import _spans
            a,b=_spans(doc.raw,call)
            if doc.raw[b-1:b]!=b')':
                raise SourceError('Call closing parenthesis is not source-resolvable')
            text=doc.raw[a:b]
            prefix=b', ' if call.args or call.keywords else b''
            edits.append((b-1,b-1,prefix+parameter.encode()+b'='+rendered))
            original_calls.append(call)
    candidate=doc.raw
    for a,b,fragment in sorted(edits,key=lambda item:item[0],reverse=True):
        candidate=candidate[:a]+fragment+candidate[b:]
    proposal=_validated_proposal(doc,candidate,
                  f'Add optional input {parameter} to {function_name}'+
                  (f' and update {len(original_calls)} local calls' if update_local_calls else ''))
    parsed=ast.parse(proposal.candidate.decode('utf-8'),type_comments=True)
    updated=next(n for n in parsed.body if isinstance(n,ast.FunctionDef) and n.name==function_name)
    if (len(updated.args.kwonlyargs)!=len(fn.args.kwonlyargs)+1 or
            updated.args.kwonlyargs[-1].arg!=parameter or
            not isinstance(updated.args.kw_defaults[-1],ast.Constant) or
            type(updated.args.kw_defaults[-1].value)!=type(default.value) or
            updated.args.kw_defaults[-1].value!=default.value):
        raise SourceError('Function interface did not round-trip')
    # AST difference is limited to the new default and explicitly changed calls.
    normalized=copy.deepcopy(parsed)
    normalized_fn=next(n for n in normalized.body if isinstance(n,ast.FunctionDef) and n.name==function_name)
    normalized_fn.args.kwonlyargs.pop()
    normalized_fn.args.kw_defaults.pop()
    if update_local_calls:
        for node in ast.walk(normalized):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id==function_name:
                if not node.keywords or node.keywords[-1].arg!=parameter:
                    raise SourceError('Call-site update did not round-trip')
                node.keywords.pop()
    if ast.dump(normalized,include_attributes=False)!=ast.dump(doc.tree,include_attributes=False):
        raise SourceError('Function edit changed unrelated AST statements')
    return proposal


# v2.41: branch/loop authoring uses the same placeholder, AST and atomic
# proposal authorities as the existing builders. The language-neutral
# capabilities above do not attempt to lower Python or execute user programs.

def _propose_placeholder_suite(doc: PythonDocument, scope_key: str, pass_anchor: dict,
                               lines: tuple[str, ...], description: str) -> EditProposal:
    """Replace one *whole-line* Pass with an adapter-qualified statement suite.

    No other statements, comments or declarations can be changed. Compare the
    parsed replacement against the exact intended syntax, not the visual labels.
    """
    _require_utf8(doc)
    if not isinstance(pass_anchor,dict) or (scope_key,pass_anchor) not in eligible_pass_targets(doc):
        raise SourceError('Placeholder has changed; reload before creating control flow')
    fn=doc.scopes[scope_key].ast_node
    if not isinstance(fn,ast.FunctionDef) or fn.decorator_list:
        raise SourceError('Qualified flow creation requires a plain synchronous function')
    target=next(stmt for stmt in fn.body if isinstance(stmt,ast.Pass))
    span=_direct_statement(doc,target,b'pass')
    if span is None:raise SourceError('Pass must be a standalone space-indented statement')
    beginning,end,prefix=span
    nl=b'\r\n' if b'\r\n' in doc.raw else b'\n'
    try:
        body=nl.join(prefix+line.encode('utf-8') for line in lines)
        # First indentation already exists in the original source.
        candidate=doc.raw[:beginning]+body[len(prefix):]+doc.raw[end:]
        expected_source='def _qualified():\n'+''.join('    '+line+'\n' for line in lines)
        expected_fn=ast.parse(expected_source).body[0]
    except (SyntaxError,UnicodeError) as exc:
        raise SourceError('Generated control suite is invalid') from exc
    proposal=_validated_proposal(doc,candidate,description)
    updated=ast.parse(proposal.candidate.decode('utf-8'),filename=str(doc.path),type_comments=True)
    changed=_function_at_path(updated,scope_key,doc)
    offset=fn.body.index(target)
    created=changed.body[offset:offset+len(expected_fn.body)]
    shape=lambda nodes:[ast.dump(node,include_attributes=False) for node in nodes]
    if (len(changed.body)!=len(fn.body)-1+len(expected_fn.body) or
            shape(created)!=shape(expected_fn.body) or
            shape(fn.body[:offset]+fn.body[offset+1:])!=
            shape(changed.body[:offset]+changed.body[offset+len(expected_fn.body):])):
        raise SourceError('Flow creation failed source-graph structural round trip')
    return proposal


def eligible_flow_pass_targets(doc: PythonDocument):
    """Only top-level Pass-only functions with a declared parameter."""
    return tuple((key,tuple(_declared_parameters(doc.scopes[key].ast_node)),anchor)
                 for key,anchor in eligible_pass_targets(doc)
                 if isinstance(doc.scopes[key].ast_node,ast.FunctionDef) and
                 not doc.scopes[key].ast_node.decorator_list and
                 _declared_parameters(doc.scopes[key].ast_node))


def _flow_parameter(doc,scope_key,parameter,anchor):
    if not isinstance(anchor,dict):
        raise SourceError('A source-backed placeholder anchor is required')
    eligible={(key,anchor['line'],anchor['col']):names
              for key,names,anchor in eligible_flow_pass_targets(doc)}
    if parameter not in eligible.get((scope_key,anchor.get('line'),anchor.get('col')),()):
        raise SourceError('Control-flow input must be a declared parameter in a qualified Pass function')


def propose_conditional_returns_from_pass(doc: PythonDocument, scope_key: str,
        parameter: str, operator: str, test_literal: str, true_literal: str,
        false_literal: str, pass_anchor: dict) -> EditProposal:
    """Create a comparison Branch with distinct True and False Return paths."""
    _flow_parameter(doc,scope_key,parameter,pass_anchor)
    if operator not in _COMPARE_OPS:raise SourceError('Unsupported comparison operator')
    comparison=_parse_primitive_literal(test_literal).value
    true=_parse_primitive_literal(true_literal).value
    false=_parse_primitive_literal(false_literal).value
    condition=parameter+' '+operator+' '+repr(comparison)
    return _propose_placeholder_suite(doc,scope_key,pass_anchor,(
        'if '+condition+':','    return '+repr(true),'return '+repr(false)),
        'Create Branch with two explicit Return paths')


def propose_for_range_accumulate(doc: PythonDocument, scope_key: str,
        parameter: str, loop_variable: str, accumulator: str, pass_anchor: dict) -> EditProposal:
    """Create a bounded, syntactically exact for/range accumulator.

    Runtime types and iteration counts remain Python concerns; no graph
    construction step executes a user function.
    """
    _flow_parameter(doc,scope_key,parameter,pass_anchor)
    fn=doc.scopes[scope_key].ast_node
    _fresh_local_name(fn,loop_variable)
    _fresh_local_name(fn,accumulator)
    if loop_variable==accumulator:raise SourceError('Loop index and accumulator must differ')
    if _global_name_mentioned(doc.tree,'range'):
        raise SourceError('range is referenced or shadowed in the existing module')
    return _propose_placeholder_suite(doc,scope_key,pass_anchor,(
        accumulator+' = 0',
        'for '+loop_variable+' in range('+parameter+'):',
        '    '+accumulator+' += '+loop_variable,
        'return '+accumulator),
        'Create a For loop with accumulator and Return')


def propose_while_countdown(doc: PythonDocument, scope_key: str, parameter: str,
        counter: str, steps: str, pass_anchor: dict) -> EditProposal:
    """Create a countdown loop with fresh locals, preserving the input binding."""
    _flow_parameter(doc,scope_key,parameter,pass_anchor)
    fn=doc.scopes[scope_key].ast_node
    _fresh_local_name(fn,counter)
    _fresh_local_name(fn,steps)
    if counter==steps:raise SourceError('Countdown locals must differ')
    return _propose_placeholder_suite(doc,scope_key,pass_anchor,(
        counter+' = '+parameter,
        steps+' = 0',
        'while '+counter+' > 0:',
        '    '+counter+' -= 1',
        '    '+steps+' += 1',
        'return '+steps),
        'Create a While loop with explicit progression and Return')


# v2.42: A genuinely composable, source-backed binary operation. This can be
# applied repeatedly to build a dataflow without re-evaluating a producer.
# The neutral authoring_contract models UI intent only; Python exclusively
# decides syntax, lexical dominance, legal statements, and source bytes.
_COMPOSITION_BINOPS = {'+': ast.Add, '-': ast.Sub, '*': ast.Mult,
                       '==': ast.Eq, '!=': ast.NotEq, '<': ast.Lt,
                       '<=': ast.LtE, '>': ast.Gt, '>=': ast.GtE}


def _qualified_composition_scope(doc: PythonDocument, scope_key: str, anchor: dict):
    """Prove direct, once-bound local producers in one linear source region.

    Explicitly stored, unambiguous function calls are permitted as *effectful*
    producer statements: subsequent operations read the stored result, never
    re-execute it. No purity, runtime success, or type inference is implied.
    Branch/loop/exception/alias and rebinding boundaries remain ineligible.
    """
    fn, target = _target_return(doc,scope_key,anchor)
    if not isinstance(fn,ast.FunctionDef) or fn.decorator_list:
        raise SourceError('Composition requires a plain synchronous function')
    if not fn.body or fn.body[-1] is not target:
        raise SourceError('Composition requires a final direct Return')
    if _direct_statement(doc,target,b'return') is None:
        raise SourceError('Return must be a standalone source line')
    parameters=_declared_parameters(fn)
    names=list(parameters)
    observed=set(parameters)
    for stmt in fn.body[:-1]:
        if (isinstance(stmt,ast.Expr) and isinstance(stmt.value,ast.Constant)
                and isinstance(stmt.value.value,str) and stmt is fn.body[0]):
            continue  # preserve a function docstring
        if not (isinstance(stmt,ast.Assign) and len(stmt.targets)==1 and
                isinstance(stmt.targets[0],ast.Name) and
                _direct_statement(doc,stmt,b'') is not None):
            raise SourceError('Existing body has unsupported flow or side effects')
        name=stmt.targets[0].id
        if name in observed:
            raise SourceError('Rebinding cannot be treated as an unambiguous data edge')
        # Existing local producers must be simple and effect-free, including
        # references only to earlier resolved operands. No arbitrary calls.
        def pure(node):
            if isinstance(node,ast.Name):return node.id in observed
            if isinstance(node,ast.Constant):
                return type(node.value) in (int,float,bool,str,bytes,type(None))
            if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.USub,ast.UAdd)):
                return pure(node.operand)
            if isinstance(node,ast.BinOp) and type(node.op) in (ast.Add,ast.Sub,ast.Mult):
                return pure(node.left) and pure(node.right)
            if isinstance(node,ast.Compare) and len(node.ops)==1 and type(node.ops[0]) in (
                    ast.Eq,ast.NotEq,ast.Lt,ast.LtE,ast.Gt,ast.GtE):
                return pure(node.left) and pure(node.comparators[0])
            return False
        if isinstance(stmt.value,ast.Call):
            call=stmt.value
            signature=(dict(qualified_callees(doc,scope_key)).get(call.func.id)
                       if isinstance(call.func,ast.Name) else None)
            if (signature is None or len(call.args)!=len(signature) or
                    call.keywords or not all(pure(arg) for arg in call.args)):
                raise SourceError('Only explicitly stored qualified direct Calls may supply later values')
        elif not pure(stmt.value):
            raise SourceError('Only statically inspected local producers qualify')
        observed.add(name);names.append(name)
    return fn,target,tuple(names)


def eligible_composition_targets(doc: PythonDocument):
    """Qualified final Returns and the scope-local names that can feed them."""
    result=[]
    for scope,_,anchors in eligible_return_targets(doc):
        for anchor in anchors:
            try:
                _,_,names=_qualified_composition_scope(doc,scope,anchor)
            except SourceError:
                continue
            if names:
                result.append((scope,names,anchor))
    return tuple(result)



def compatible_composition_pin(doc: PythonDocument, node_id: str, port_id: str):
    """Resolve a visible *parameter or local assignment* value port.

    IDs and ports are looked up in source projections, not decoded from a
    string supplied by the UI. This never permits direct connections to
    unqualified locals, effectful calls, or a foreign function's result.
    """
    matches=[]
    for scope,names,anchor in eligible_composition_targets(doc):
        graph=doc.scope_graph(scope)
        for node in graph['nodes']:
            if node['id']!=node_id or node.get('source_kind') not in ('param','assignment'):
                continue
            if node['source_kind']=='param':
                name=node['title'].removeprefix('PARAMETER ')
            else:
                name=node['title'].removeprefix('SET ')
            if name not in names:continue
            if any(port['id']==port_id and port['id'].endswith(':outputs:value')
                   for port in node['draft_ports']['outputs']):
                matches.append((scope,name,anchor))
    return tuple(matches)


def propose_compose_binary_local(doc: PythonDocument, scope_key: str,
                                 request: BinaryComposition, before_return: dict) -> EditProposal:
    """Compose data producers once, inserting one local and optionally wiring Return.

    This method never copies an existing expression or invokes a function.
    A qualified local reads its original stored value, so repeated composition
    chains form actual source-level producer/consumer dependencies.
    """
    _require_utf8(doc)
    if not isinstance(request,BinaryComposition):
        raise SourceError('Expected a qualified binary composition request')
    fn, target, names=_qualified_composition_scope(doc,scope_key,before_return)
    if request.operation not in _COMPOSITION_BINOPS:
        raise SourceError('Unsupported binary node operation')
    def resolve(operand):
        if operand.kind=='name':
            if operand.value not in names:
                raise SourceError('Operand is not an available, dominating source value')
            return operand.value
        return repr(_parse_primitive_literal(operand.value).value)
    expression_source=f'{resolve(request.left)} {request.operation} {resolve(request.right)}'
    return _insert_fresh_local(doc,scope_key,fn,target,request.result_name,
                               expression_source,request.feed_return,
                               'Compose '+request.result_name+' from two qualified source values')


def _insert_fresh_local(doc: PythonDocument,scope_key: str,fn: ast.FunctionDef,
                        target: ast.Return,name: str,expression_source: str,
                        feed_return: bool,description: str):
    """One guarded source insertion + AST round-trip gate for variable creators.

    Composition and variable reads use the same byte-preserving transaction.
    This is the only owner of how fresh local assignments are inserted.
    """
    _fresh_local_name(fn,name)
    if feed_return and target.value is not None and not isinstance(target.value,(ast.Name,ast.Constant)):
        raise SourceError('Return rewrite would discard an effectful or compound expression')
    span=_direct_statement(doc,target,b'return')
    if span is None:raise SourceError('Return source location is not qualified')
    beginning,end,prefix=span
    nl=b'\r\n' if b'\r\n' in doc.raw else b'\n'
    assignment=name+' = '+expression_source
    # Parse the exact emitted spelling: signed constants are UnaryOp in
    # Python's AST even when the validated literal was normalized to Constant.
    expected=ast.parse(assignment).body[0]
    inserted=prefix+assignment.encode('utf-8')+nl
    replacement=(b'return '+name.encode('utf-8') if feed_return
                 else doc.raw[beginning:end])
    candidate=doc.raw[:beginning-len(prefix)]+inserted+prefix+replacement+doc.raw[end:]
    proposal=_validated_proposal(doc,candidate,description)
    parsed=ast.parse(proposal.candidate.decode('utf-8'),filename=str(doc.path),type_comments=True)
    changed=_function_at_path(parsed,scope_key,doc)
    idx=fn.body.index(target)
    if len(changed.body)!=len(fn.body)+1:
        raise SourceError('Variable creation unexpectedly changed statement count')
    if ast.dump(changed.body[idx],include_attributes=False)!=ast.dump(expected,include_attributes=False):
        raise SourceError('Variable assignment did not round-trip')
    if ([ast.dump(x,include_attributes=False) for x in changed.body[:idx]] !=
            [ast.dump(x,include_attributes=False) for x in fn.body[:idx]]):
        raise SourceError('Variable creation changed preceding source statements')
    changed_return=changed.body[idx+1]
    if feed_return:
        if not (isinstance(changed_return,ast.Return) and
                isinstance(changed_return.value,ast.Name) and
                changed_return.value.id==name):
            raise SourceError('Variable Return wiring did not round-trip')
    elif ast.dump(changed_return,include_attributes=False)!=ast.dump(target,include_attributes=False):
        raise SourceError('Variable creation changed the original Return')
    if changed.body[idx+2:]:
        raise SourceError('Unexpected statements after final Return')
    return proposal


# v2.47: A variable is a qualified source binding, not an independently
# mutable visual cell. The same straight-line source/dominance proof used by
# composition governs storing a value (a local read or primitive literal).
def eligible_value_assignment_targets(doc: PythonDocument):
    """Scopes where a fresh, once-bound assignment can be inserted safely."""
    result=[]
    for scope,_,anchors in eligible_return_targets(doc):
        for anchor in anchors:
            try:
                _,_,names=_qualified_composition_scope(doc,scope,anchor)
            except SourceError:
                continue
            result.append((scope,names,anchor))
    return tuple(result)


def compatible_value_assignment_pin(doc: PythonDocument, node_id: str, port_id: str):
    """Reuse exact qualified producer-port resolution, never a label-based guess."""
    return compatible_composition_pin(doc,node_id,port_id)


def propose_assign_source_value(doc: PythonDocument,scope_key: str,
                                request: ValueAssignment,before_return: dict) -> EditProposal:
    """Create one fresh local without evaluating or copying an existing producer.

    Source bytes and AST round-trip are the authority. No call execution,
    rebinding, cross-scope reference or downstream Return rewrite with effects.
    """
    _require_utf8(doc)
    if not isinstance(request,ValueAssignment):
        raise SourceError('Expected a qualified local value assignment request')
    fn,target,names=_qualified_composition_scope(doc,scope_key,before_return)
    operand=request.operand
    if operand.kind=='name':
        if operand.value not in names:
            raise SourceError('Referenced variable is not a dominating value in this scope')
        source=operand.value
    else:
        source=repr(_parse_primitive_literal(operand.value).value)
    return _insert_fresh_local(doc,scope_key,fn,target,request.result_name,
                               source,request.feed_return,
                               'Create qualified local '+request.result_name)


# v2.49 function milestone. Build on the existing source insert transaction,
# lexical dominance proof, unique function resolution and shared proposal gate.
def eligible_composed_call_targets(doc: PythonDocument):
    """Final direct Returns where a uniquely resolved function may consume values."""
    return tuple((scope,names,anchor,callees)
                 for scope,names,anchor in eligible_value_assignment_targets(doc)
                 if (callees:=qualified_callees(doc,scope)))


def compatible_composed_call_pin(doc: PythonDocument,node_id: str,port_id: str):
    """Only actual source-verified value producer pins qualify for call inputs."""
    targets={(scope,tuple(sorted(anchor.items()))) for scope,_,anchor,_ in eligible_composed_call_targets(doc)}
    return tuple((scope,name,anchor) for scope,name,anchor in compatible_value_assignment_pin(doc,node_id,port_id)
                 if (scope,tuple(sorted(anchor.items()))) in targets)


def propose_composed_call(doc: PythonDocument,scope_key: str,
                          request: CallComposition,before_return: dict) -> EditProposal:
    """Store one explicit (potentially effectful) Call, optionally feed final Return.

    This is never a pure arithmetic edge. Call evaluation is explicitly requested
    by the user and occurs at this exact source location if the script is run.
    """
    _require_utf8(doc)
    if not isinstance(request,CallComposition):
        raise SourceError('Expected a qualified Call composition request')
    fn,target,names=_qualified_composition_scope(doc,scope_key,before_return)
    callees=dict(qualified_callees(doc,scope_key))
    signature=callees.get(request.callee)
    if signature is None or len(signature)!=len(request.arguments):
        raise SourceError('Callee signature is not qualified or argument count has changed')
    rendered=[]
    for operand in request.arguments:
        if operand.kind=='name':
            if operand.value not in names:
                raise SourceError('Call argument is not a proven prior value in this function')
            rendered.append(operand.value)
        else:
            rendered.append(repr(_parse_primitive_literal(operand.value).value))
    expression=request.callee+'('+', '.join(rendered)+')'
    return _insert_fresh_local(doc,scope_key,fn,target,request.result_name,
                expression,request.feed_return,'Call '+request.callee+' using qualified scoped values')


def eligible_rename_functions(doc: PythonDocument) -> tuple[str,...]:
    """Locally unambiguous module functions used only by direct named calls.

    External clients, reflection, package exports, decorators and first-class
    function values cannot be rewritten by this single-file operation.
    """
    if any(isinstance(node,ast.Name) and node.id=='__all__' and isinstance(node.ctx,ast.Store)
           for node in ast.walk(doc.tree)):
        return ()
    if any(isinstance(node,ast.Call) and isinstance(node.func,ast.Name)
           and node.func.id in ('eval','exec','globals','locals','getattr') for node in ast.walk(doc.tree)):
        return ()
    candidates=[]
    for fn in doc.tree.body:
        if (not isinstance(fn,ast.FunctionDef) or fn.decorator_list or
                fn.name.startswith('__') or _shadowed_call_name(doc.tree,fn.name) or
                sum(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and n.name==fn.name
                    for n in doc.tree.body)!=1):
            continue
        lines=doc.raw.splitlines(keepends=True)
        if not (1<=fn.lineno<=len(lines) and lines[fn.lineno-1].startswith(b'def '+fn.name.encode('utf-8')+b'(')):
            continue
        calls={id(node.func) for node in ast.walk(doc.tree)
               if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id==fn.name}
        if any(isinstance(node,ast.Name) and node.id==fn.name and id(node) not in calls
               for node in ast.walk(doc.tree)):
            continue
        candidates.append(fn.name)
    return tuple(candidates)


def propose_rename_function(doc: PythonDocument,old_name: str,new_name: str) -> EditProposal:
    """Rename one source-defined function and every statically direct local call.

    Refuse first-class references, dynamic binding, and destination collisions.
    This is a *file-local* transform, never an assertion that external API
    users or other project files have been migrated.
    """
    from .python_edit import _spans
    _require_utf8(doc)
    if old_name not in eligible_rename_functions(doc):
        raise SourceError('Function has ambiguous references or unsupported source structure')
    new_name=_new_identifier(new_name,role='New function name')
    if new_name in dir(builtins) or _global_name_mentioned(doc.tree,new_name):
        raise SourceError('New name shadows an existing source identifier or builtin')
    fn=next(n for n in doc.tree.body if isinstance(n,ast.FunctionDef) and n.name==old_name)
    line_offset=sum(map(len,doc.raw.splitlines(keepends=True)[:fn.lineno-1]))
    token=b'def '+old_name.encode('utf-8')+b'('
    if not doc.raw[line_offset:].startswith(token):
        raise SourceError('Function header no longer matches its AST declaration')
    edits=[(line_offset+4,line_offset+4+len(old_name.encode('utf-8')),new_name.encode('utf-8'))]
    calls=[]
    for call in ast.walk(doc.tree):
        if isinstance(call,ast.Call) and isinstance(call.func,ast.Name) and call.func.id==old_name:
            a,b=_spans(doc.raw,call.func)
            if doc.raw[a:b]!=old_name.encode('utf-8'):
                raise SourceError('Call target name has no exact source token')
            edits.append((a,b,new_name.encode('utf-8')))
            calls.append(call)
    candidate=doc.raw
    for a,b,value in sorted(edits,reverse=True):
        candidate=candidate[:a]+value+candidate[b:]
    proposal=_validated_proposal(doc,candidate,
                  f'Rename local function {old_name} to {new_name} and update {len(calls)} direct calls')
    expected=copy.deepcopy(doc.tree)
    next_fn=next(n for n in expected.body if isinstance(n,ast.FunctionDef) and n.name==old_name)
    next_fn.name=new_name
    for call in ast.walk(expected):
        if isinstance(call,ast.Call) and isinstance(call.func,ast.Name) and call.func.id==old_name:
            call.func.id=new_name
    observed=ast.parse(candidate.decode('utf-8'),filename=str(doc.path),type_comments=True)
    if ast.dump(expected,include_attributes=False)!=ast.dump(observed,include_attributes=False):
        raise SourceError('Function rename changed unrelated program semantics')
    return proposal


# One module-local source-verified function input refactor. Same source proposal
# transaction and AST normalization gate as function name changes.
def eligible_parameter_renames(doc: PythonDocument):
    """Module function input names with unambiguous local references and callers."""
    functions=set(eligible_rename_functions(doc))
    result=[]
    lines=doc.raw.splitlines(keepends=True)
    for fn in doc.tree.body:
        if not isinstance(fn,ast.FunctionDef) or fn.name not in functions:
            continue
        if not (1<=fn.lineno<=len(lines) and
                lines[fn.lineno-1].startswith(b'def '+fn.name.encode('utf-8')+b'(') and
                fn.body and fn.body[0].lineno>fn.lineno):
            continue
        # Nested binding, comprehension or effectful closure may capture the
        # parameter differently. Refuse those complex scopes instead of guess.
        if any(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef,
                             ast.Lambda,ast.ListComp,ast.SetComp,ast.DictComp,ast.GeneratorExp))
               for stmt in fn.body for n in ast.walk(stmt)):
            continue
        inputs=(*fn.args.posonlyargs,*fn.args.args,*fn.args.kwonlyargs)
        names=[]
        for arg in inputs:
            old=arg.arg
            # A reassigned input cannot be represented by stable source ports.
            if any((isinstance(node,ast.Name) and node.id==old and isinstance(node.ctx,(ast.Store,ast.Del))) or
                    (isinstance(node,(ast.Global,ast.Nonlocal)) and old in node.names)
                   for stmt in fn.body for node in ast.walk(stmt)):
                continue
            # Any unresolved **kwargs at direct call sites may hide a keyword
            # reference to this input. Do not silently break callers.
            if any(isinstance(call,ast.Call) and isinstance(call.func,ast.Name) and call.func.id==fn.name and
                   (any(isinstance(a,ast.Starred) for a in call.args) or
                    any(kw.arg is None for kw in call.keywords))
                   for call in ast.walk(doc.tree)):
                continue
            names.append(old)
        if names:result.append((fn.name,tuple(names)))
    return tuple(result)


def propose_rename_parameter(doc: PythonDocument,function_name: str,
                             old_name: str,new_name: str) -> EditProposal:
    """Rename definition input, body references and direct-call keyword names.

    Existing positional calls retain their positions, local keyword calls are
    adjusted, and any dynamic/ambiguous binding disables the operation.
    """
    from .python_edit import _spans
    _require_utf8(doc)
    qualified=dict(eligible_parameter_renames(doc))
    if old_name not in qualified.get(function_name,()):
        raise SourceError('Function input is not qualified for a source rename')
    new_name=_new_identifier(new_name,role='New function input')
    if new_name in dir(builtins) or new_name==function_name:
        raise SourceError('New input shadows a builtin or its own function')
    fn=next(node for node in doc.tree.body if isinstance(node,ast.FunctionDef) and node.name==function_name)
    if (any(isinstance(node,ast.Name) and node.id==new_name
            for stmt in fn.body for node in ast.walk(stmt)) or
            any(arg.arg==new_name for arg in (*fn.args.posonlyargs,*fn.args.args,*fn.args.kwonlyargs))):
        raise SourceError('New input name collides with an existing source binding')
    # Parameter defaults and annotations are evaluated at definition time;
    # renaming their external references would not have the same semantics.
    if any(isinstance(node,ast.Name) and node.id==old_name
           for node in ast.walk(fn.args)):
        raise SourceError('Function signature contains ambiguous input references')
    edits=[]
    argument=next(arg for arg in (*fn.args.posonlyargs,*fn.args.args,*fn.args.kwonlyargs)
                  if arg.arg==old_name)
    a,_=_spans(doc.raw,argument)
    old_bytes=old_name.encode('utf-8');new_bytes=new_name.encode('utf-8')
    if doc.raw[a:a+len(old_bytes)]!=old_bytes:
        raise SourceError('Function argument has no exact source name token')
    edits.append((a,a+len(old_bytes),new_bytes))
    for stmt in fn.body:
        for node in ast.walk(stmt):
            if isinstance(node,ast.Name) and node.id==old_name:
                a,b=_spans(doc.raw,node)
                if doc.raw[a:b]!=old_bytes:raise SourceError('Body variable reference has no exact name token')
                edits.append((a,b,new_bytes))
    for call in ast.walk(doc.tree):
        if not (isinstance(call,ast.Call) and isinstance(call.func,ast.Name) and
                call.func.id==function_name):
            continue
        for kw in call.keywords:
            if kw.arg!=old_name:continue
            a,_=_spans(doc.raw,kw)
            if doc.raw[a:a+len(old_bytes)]!=old_bytes:
                raise SourceError('Keyword call argument has no exact token')
            edits.append((a,a+len(old_bytes),new_bytes))
    candidate=doc.raw
    for a,b,fragment in sorted(edits,reverse=True):
        candidate=candidate[:a]+fragment+candidate[b:]
    proposal=_validated_proposal(doc,candidate,
                f'Rename function input {function_name}.{old_name} to {new_name} and direct keyword callers')
    expected=copy.deepcopy(doc.tree)
    changed=next(n for n in expected.body if isinstance(n,ast.FunctionDef) and n.name==function_name)
    next(arg for arg in (*changed.args.posonlyargs,*changed.args.args,*changed.args.kwonlyargs)
         if arg.arg==old_name).arg=new_name
    for stmt in changed.body:
        for node in ast.walk(stmt):
            if isinstance(node,ast.Name) and node.id==old_name:node.id=new_name
    for call in ast.walk(expected):
        if isinstance(call,ast.Call) and isinstance(call.func,ast.Name) and call.func.id==function_name:
            for kw in call.keywords:
                if kw.arg==old_name:kw.arg=new_name
    observed=ast.parse(candidate.decode('utf-8'),filename=str(doc.path),type_comments=True)
    if ast.dump(expected,include_attributes=False)!=ast.dump(observed,include_attributes=False):
        raise SourceError('Function input rename modified unrelated program semantics')
    return proposal
