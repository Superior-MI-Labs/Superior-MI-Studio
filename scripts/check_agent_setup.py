#!/usr/bin/env python3
"""Read-only checks for Codex guidance/layout, with no imports of application code."""
from pathlib import Path
import re
import sys
import tomllib

ROOT=Path(__file__).resolve().parent.parent
REQUIRED=[
 'AGENTS.md','CODEX-START-HERE.md','docs/agents/REPOSITORY-MAP-v2.52.md',
 'docs/architecture/MASTER-BLUEPRINT-v3.1.md',
 'docs/architecture/SUBSYSTEMS-AND-INTERACTIONS.md',
 'docs/architecture/REFACTOR-AND-CLEANUP.md',
 'docs/architecture/DECISIONS-AND-NON-GOALS.md',
 'docs/architecture/IMPLEMENTATION-AND-TRACEABILITY.md',
 'docs/architecture/ACCEPTANCE-MATRIX.csv',
 '.codex/config.toml',
]
failures=[]
for p in REQUIRED:
 if not (ROOT/p).is_file():failures.append(f'missing: {p}')
for p in sorted((ROOT/'.agents/skills').glob('*/SKILL.md')):
 s=p.read_text(encoding='utf-8')
 if not re.match(r'\A---\n(?:(?!\n---\n).)*\n---\n',s,re.S):
  failures.append(f'invalid YAML frontmatter delimiters: {p.relative_to(ROOT)}')
 if not re.search(r'^name:\s*[\w-]+\s*$',s,re.M) or not re.search(r'^description:\s*\S',s,re.M):
  failures.append(f'missing skill name/description: {p.relative_to(ROOT)}')
if len(list((ROOT/'.agents/skills').glob('*/SKILL.md')))<3:failures.append('fewer than 3 project skills')
for p in [ROOT/'.codex/config.toml',*sorted((ROOT/'.codex/agents').glob('*.toml'))]:
 if p.exists():
  try:
   parsed=tomllib.loads(p.read_text(encoding='utf-8'))
   if p.parent.name=='agents' and any(k not in parsed for k in ('name','description','developer_instructions')):
    failures.append(f'agent role missing required fields: {p.name}')
  except Exception as exc:failures.append(f'bad TOML {p.relative_to(ROOT)}: {exc}')
if (ROOT/'AGENTS.md').exists() and (ROOT/'AGENTS.md').stat().st_size>12000:
 failures.append('root AGENTS.md exceeds concise-context budget')
if failures:
 print('AGENT_SETUP_FAIL\n'+'\n'.join(failures))
 sys.exit(1)
print('AGENT_SETUP_PASS — guides, skills, role TOML and design documents present')
