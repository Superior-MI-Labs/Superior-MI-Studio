"""Shared, non-semantic wire appearance for every recursive graph surface.

All relations remain the original source/descriptor relations. Changing line
style, draw priority or alpha never rewrites the canonical graph.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class EdgeStyle:
    color: str
    width: float
    dashed: bool
    z: float
    opacity: float

COLORS = {
    'data':'#64aed9', 'control':'#f1f5fc', 'reference':'#9a91f2',
    'call':'#77cca9', 'imports':'#aa9ae5',
}


def edge_style(relation: str, *, crosses_surface: bool = False) -> EdgeStyle:
    # Cross-region wires are drawn BEHIND cards, not over their title bars.
    return EdgeStyle(COLORS.get(relation, COLORS['data']),
                     2.0 if crosses_surface else 2.8,
                     relation in ('reference','imports'),
                     3.0 if crosses_surface else 1.0,
                     .72 if crosses_surface else 1.0)


def exit_edge_style(facet: str, *, crosses_region: bool = False) -> EdgeStyle:
    if facet not in ('control','value'):
        raise ValueError('Unknown exit facet')
    # A nonlocal exit starts inside another viewport (e.g. IF). Paint over
    # that region's card, otherwise its solid background hides the start.
    return EdgeStyle('#eaf4fb' if facet=='control' else '#e0b36e',
                     2.3 if facet=='control' else 2.0,False,
                     6.0 if crosses_region else 3.0,
                     .85 if crosses_region else 1.0)
