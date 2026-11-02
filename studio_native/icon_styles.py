"""Semantic icon hints shared by graph producers (no Qt or source mutation).

IDs are the canonical manifest vocabulary. UI never manufactures a fallback
resource node when a semantic icon is absent: it paints the existing placeholder.
"""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class IconHint:
    icon_id: str
    tint: str

ROLE_COLORS = {
    'function':'#8bc5ef', 'class':'#9eb5ed', 'if':'#94c2d8',
    'loop':'#8edaca', 'return':'#e9b96e', 'file':'#b1c8dd',
    'directory':'#ecc16f', 'operator':'#c5d6e6', 'resource':'#b1c8dd',
    'variable':'#dfba7e', 'call':'#a7c9ed', 'assignment':'#79d4c2',
}

ICON_BY_ROLE = {
    'function':'icons.programming.oop.function_definition',
    'class':'icons.programming.oop.class',
    'if':'icons.programming.control.if',
    'return':'icons.programming.control.return',
    'loop':'icons.programming.control.while_loop',
    'operator':'icons.programming.structure.expression',
    'variable':'icons.programming.structure.declaration',
    'assignment':'icons.programming.structure.assignment',
    'call':'icons.programming.oop.function_call',
}

SOURCE_KIND_ROLE = {
    'function':'function', 'class':'class', 'if':'if', 'loop':'loop',
    'return':'return', 'assignment':'assignment',
    'operation':'operator', 'compare':'operator', 'loop_test':'operator',
    'param':'variable', 'global':'variable','capture':'variable',
    'literal':'variable', 'call':'call', 'call_expr':'call',
}


def icon_hint(role: str, icon_id: str | None = None,
              accent: str | None = None, *, source_line: str = '') -> IconHint:
    role = SOURCE_KIND_ROLE.get(role, role)
    role = role if role in ROLE_COLORS else 'resource'
    if not icon_id:
        from .external_icons import icon_id_for_resource
        if role in ('file','directory'):
            icon_id=icon_id_for_resource(role)
        elif role=='loop':
            line=source_line.lstrip()
            icon_id=('icons.programming.control.for_loop' if line.startswith(('for ','async for '))
                     else 'icons.programming.control.while_loop')
        else:
            icon_id=ICON_BY_ROLE.get(role,'icons.programming.structure.file')
    color=(accent if isinstance(accent,str) and len(accent)==7 and accent.startswith('#')
           and all(c in '0123456789abcdefABCDEF' for c in accent[1:])
           else ROLE_COLORS[role])
    return IconHint(icon_id,color)
