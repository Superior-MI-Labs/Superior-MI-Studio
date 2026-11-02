"""Read-only adapter preflight for a drag connection in a Python source graph.

This is not a second graph authority: it invokes the same AST-backed lowering
as the approved source-edit path. A successful result carries that exact
candidate proposal, and still requires user review and atomic stale-file checks.
The view is responsible only for resolving its boundary mirrors to source IDs.
"""
from __future__ import annotations
from dataclasses import dataclass

from .python_edit import EditProposal, rewire_source_operand
from .python_graph import PythonDocument, SourceError


@dataclass(frozen=True)
class ConnectionCheck:
    allowed: bool
    reason: str
    proposal: EditProposal | None = None
    scope: str | None = None
    mode: str = 'unsupported'  # stored-reference, name-reference, expression-copy


def inspect_connection(doc: PythonDocument | None, source_id: str, source_port: str,
                       target_id: str, target_port: str) -> ConnectionCheck:
    """Determine compatibility by *proposing* the real source edit in memory.

    No color matching, heuristic type matching, raw text substitution, or file
    write can mark a connection compatible. A source/destination must resolve
    to the same exact lexical function and pass the existing AST checks.
    """
    if doc is None:
        return ConnectionCheck(False, 'No Python document is active')
    if not all(isinstance(s,str) and s for s in
               (source_id,source_port,target_id,target_port)):
        return ConnectionCheck(False, 'Missing source or destination identity')
    candidates=(scope for scope,info in doc.scopes.items()
                if scope!='module' and info.kind=='function'
                and source_id.startswith('py:'+scope+'|')
                and target_id.startswith('py:'+scope+'|'))
    scope=max(candidates,key=len,default=None)
    if scope is None:
        return ConnectionCheck(False, 'Both endpoints must belong to the same function scope')
    try:
        proposal=rewire_source_operand(doc,scope,source_id,source_port,
                                       target_id,target_port)
    except (SourceError,ValueError) as exc:
        return ConnectionCheck(False,str(exc),scope=scope)
    source_kind=next((node.get('source_kind')
                      for node in doc.scope_graph(scope)['nodes']
                      if node['id']==source_id),None)
    mode=('stored-reference' if source_kind=='call' else
          'name-reference' if source_kind in ('param','assignment') else
          'expression-copy')
    description={
        'stored-reference':'References the existing stored Call result; does not invoke it again',
        'name-reference':'References the existing Python binding',
        'expression-copy':'Copies the qualified primitive/expression text, not a live dependency',
    }[mode]
    return ConnectionCheck(True,description+'; review the Python diff before saving',
                           proposal=proposal,scope=scope,mode=mode)
