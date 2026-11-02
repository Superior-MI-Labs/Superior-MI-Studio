"""Language-neutral description of an adapter-qualified authoring capability.

Contracts advertise qualified source-lowering operations; they are not a
second AST, node renderer, or executable compiler. Language adapters own the
syntax, binding/flow checks and source proposals. No Python imports live here.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class QualifiedOperation:
    id: str
    language: str
    contract_version: int
    title: str
    operation_kinds: tuple[str, ...]
    inputs: tuple[str, ...]
    control_outputs: tuple[str, ...]
    lowering: str
    capability: str



def validate_catalog(definitions):
    """Refuse duplicate or malformed advertised capabilities, independent of language."""
    found=set()
    for definition in definitions:
        if not isinstance(definition,QualifiedOperation):
            raise ValueError('Authoring catalog contains a non-capability')
        if (not definition.language.isidentifier() or definition.contract_version < 1 or
                not definition.id.startswith(definition.language+'.') or
                definition.id in found or not definition.title.strip() or
                not definition.operation_kinds or not definition.lowering or
                definition.capability != 'guarded-source-proposal'):
            raise ValueError('Invalid or duplicate adapter-authoring capability: '+definition.id)
        found.add(definition.id)
    return tuple(definitions)


@dataclass(frozen=True)
class OperandReference:
    """Language-neutral authoring selection, not a second graph or AST.

    A language adapter must resolve `name` in the selected lexical scope and
    independently validate `literal` using the destination language's rules.
    """
    kind: str  # name or literal
    value: str

    def __post_init__(self):
        if self.kind not in ('name', 'literal') or not isinstance(self.value, str) or not self.value or len(self.value) > 150:
            raise ValueError('Invalid visual operand reference')


@dataclass(frozen=True)
class ValueAssignment:
    """Request a new, once-bound local from a qualified existing value or literal.

    The adapter, not this neutral request, proves the lexical scope and
    proposal's source-byte transformation.
    """
    operand: OperandReference
    result_name: str
    feed_return: bool = False

    def __post_init__(self):
        if (not isinstance(self.operand, OperandReference) or
                not isinstance(self.result_name,str) or len(self.result_name)>64 or
                not isinstance(self.feed_return,bool)):
            raise ValueError('Invalid visual local value assignment')


@dataclass(frozen=True)
class CallComposition:
    """A source-qualified call with one operand per declared callee parameter.

    This expresses UI intent only. The language adapter proves binding, lexical
    dominance, source locations, and validity before proposing any bytes.
    """
    callee: str
    arguments: tuple[OperandReference, ...]
    result_name: str
    feed_return: bool = True

    def __post_init__(self):
        if (not isinstance(self.callee,str) or not self.callee or len(self.callee)>64 or
                not isinstance(self.arguments,tuple) or
                not 1<=len(self.arguments)<=4 or
                not all(isinstance(arg,OperandReference) for arg in self.arguments) or
                not isinstance(self.result_name,str) or len(self.result_name)>64 or
                not isinstance(self.feed_return,bool)):
            raise ValueError('Invalid visual function Call composition')


@dataclass(frozen=True)
class BinaryComposition:
    """A request to connect two operands to one operation and a named result.

    This is a UI-to-adapter intent. It does not own source text, node IDs,
    evaluation semantics, or an executable intermediate representation.
    """
    left: OperandReference
    operation: str
    right: OperandReference
    result_name: str
    feed_return: bool = True

    def __post_init__(self):
        if (not isinstance(self.left, OperandReference) or
                not isinstance(self.right, OperandReference) or
                not isinstance(self.operation,str) or len(self.operation)>40 or
                not isinstance(self.result_name,str) or len(self.result_name)>64 or
                not isinstance(self.feed_return,bool)):
            raise ValueError('Invalid visual binary composition')
