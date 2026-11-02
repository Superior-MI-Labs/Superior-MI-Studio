#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"
echo "== Python Visual Programming Lab $(python3 -c 'from install_linux import VERSION; print(VERSION)') doctor =="
python3 -m compileall -q studio_native
python3 -m unittest discover -s tests -v
python3 scripts/python-first-gate.py > /dev/null
echo PYTHON_FIRST_GATE_PASS
python3 scripts/program-graph-python-gate.py
python3 - <<'PY'
from studio_native.python_graph import PythonDocument
p=PythonDocument('examples/python-scope-demo.py')
print('PYTHON_SOURCE', p.path.name, 'sha256', p.sha256)
for scope in p.scopes:
    graph=p.scope_graph(scope)
    print('SCOPE',graph['title'],len(graph['nodes']),'nodes',len(graph['edges']),'edges')
whole=p.whole_file_graph()
print('WHOLE_FILE', len(whole['nodes']), 'nodes', len(whole['edges']), 'edges',len(whole['scope_regions']), 'scope regions')
assert len(whole['nodes'])>=len(p.scope_graph('module')['nodes'])
composite=p.composite_file_graph(set(p.scopes)-{'module'},detail='readable')
assert not composite['scope_regions']
assert {n['id'] for n in composite['nodes']}=={n['id'] for n in p.whole_file_graph(set(p.scopes)-{'module'},detail='readable')['nodes']}
assert any(n.get('embedded_region') for n in composite['nodes'])
print('COMPOSITE_SOURCE_PASS', len(composite['nodes']), 'nodes', len(composite['edges']),'edges')
cf=PythonDocument('examples/python-control-flow-demo.py')
branch_scope=next(k for k,v in cf.scopes.items() if v.title=='adjusted_count')
branch=cf.scope_graph(branch_scope)
assert any(n['source_kind']=='branch' for n in branch['nodes'])
assert any(n['source_kind']=='compare' for n in branch['nodes'])
loop_source=PythonDocument('examples/python-v07-branch-and-loops.py')
loop_key=next(k for k,v in loop_source.scopes.items() if v.title=='count_high')
loop_graph=loop_source.scope_graph(loop_key)
assert any(n['source_kind']=='loop' for n in loop_graph['nodes'])
assert not any(n['title'].endswith(' BODY') for n in loop_graph['nodes'])
assert any(e['targetPort'].endswith(':repeat') and e['relation']=='control'
           for e in loop_graph['edges'])
v08=PythonDocument('examples/python-v08-loop-control.py')
for name in ('scan','countdown','nested_loops'):
    key=next(k for k,v in v08.scopes.items() if v.title==name)
    graph=v08.scope_graph(key)
    assert not any(n['title'].endswith(' BODY') for n in graph['nodes'])
    print('LOOP_CONTROL',name,len(graph['nodes']),'nodes',len(graph['edges']),'edges')
print('LOOP_CONTROL_PASS')
extra=PythonDocument('examples/python-v09-loop-values.py')
for label in ('countdown','accumulate','conditional_countdown'):
    key=next(k for k,v in extra.scopes.items() if v.title==label)
    graph=extra.scope_graph(key)
    print('LOOP_VALUES',label,len(graph['nodes']),'nodes',len(graph['edges']),'edges')
# User graph is intentionally less complex than internal analysis.
key=next(k for k,v in loop_source.scopes.items() if v.title=='reduce_until_small')
readable=loop_source.presentation_graph(key)
assert len(readable['nodes'])==4
assert {n['title'] for n in readable['nodes']}=={'PARAMETER value','WHILE value > 10','-=','RETURN'}
assert all(n['source_kind'] not in ('entry','exit','loop_test','loop_value','control_join') for n in readable['nodes'])
assert len(readable['edges'])==4
print('READABLE_SOURCE_PASS', len(readable['nodes']),'nodes',len(readable['edges']),'edges')
# v1.1: the first source assignment is a visible variable binding;
# explicit reassignments still remain write operations.
v11=PythonDocument('examples/python-v11-bindings-and-returns.py')
for name, expected in [('combine_strings',['a','b','ADD','c','RETURN']),
                       ('sum_items',['PARAMETER items','total','FOR item','+=','RETURN'])]:
    key=next(k for k,scope in v11.scopes.items() if scope.title==name)
    graph=v11.presentation_graph(key)
    assert [n['title'] for n in graph['nodes']]==expected, (name,[n['title'] for n in graph['nodes']])
    assert not any(e['targetPort'].endswith(':repeat') for e in graph['edges'])
    print('BINDINGS',name,len(graph['nodes']),'nodes',len(graph['edges']),'edges')
print('BINDINGS_PASS')
print('SOURCE_PROJECTION_PASS')
PY
if /usr/bin/python3 -c 'import PyQt6' >/dev/null 2>&1 || python3 -c 'import PyQt6' >/dev/null 2>&1; then
  echo 'PyQt6 available. Optional native test: ./test-qt-offscreen.sh'
else
  echo 'PyQt6 unavailable. Install: sudo apt install python3-pyqt6'
fi

python3 - <<'PYICON'
from studio_native.external_icons import ExternalIconAtlas, default_icon_atlas_directory
location=default_icon_atlas_directory()
pack=ExternalIconAtlas.discover(location)
if pack:
    print('OPTIONAL_ICON_ATLAS',pack.version,len(pack.entries),'icons',pack.root)
else:
    print('OPTIONAL_ICON_ATLAS not installed (built-in and OS icons work)',location)
PYICON
