#!/usr/bin/env python3
"""Deterministic read-only Python module ownership inventory; does not execute project source."""
import ast
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
for p in sorted((ROOT/'studio_native').glob('*.py')):
 text=p.read_text(encoding='utf-8');t=ast.parse(text);deps=set()
 for node in ast.walk(t):
  if isinstance(node,ast.ImportFrom):
   if node.level or (node.module or '').startswith('studio_native'):deps.add('.'*node.level+(node.module or ''))
  if isinstance(node,ast.Import):
   deps.update(a.name for a in node.names if a.name.startswith('studio_native'))
 print(f'{p.name:30s} {len(text.splitlines()):5} lines | imports: {", ".join(sorted(deps))}')
