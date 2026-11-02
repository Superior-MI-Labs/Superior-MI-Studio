#!/usr/bin/env python3
"""Read-only acceptance: complete persisted graph -> typed Python preview."""
from pathlib import Path
import ast
import sys
import tempfile

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from studio_native.program_graph import ProgramGraph, validate
from studio_native.python_lowering import preview_python, publish_python

source=ROOT/'examples'/'qualified-integer-program.smi-graph'
document=ProgramGraph.open(source)
original=document.state
validate(original)
preview=preview_python(original)
assert preview.source is not None and not preview.issues,preview.issues
assert len(preview.node_lines)==8
assert [fn.name for fn in ast.parse(preview.source).body]==['compose','increment']
compile(preview.source,'<program-graph-gate>','exec')  # no code execution
assert document.state==original
assert preview_python(ProgramGraph.open(source).state).source==preview.source
assert source.read_bytes()==document._base  # exact untouched on-disk bytes
with tempfile.TemporaryDirectory() as temporary:
    output=Path(temporary)/'qualified.py'
    receipt=publish_python(document,output,expected_revision=document.revision)
    assert output.read_text(encoding='utf-8')==preview.source
    assert receipt.node_lines==preview.node_lines
    assert document.state==original and source.read_bytes()==document._base
# A real, separately persisted pure data-selection graph. No runtime Branch
# claim: producers evaluate eagerly and the AST is only compiled, not run.
conditional_path=ROOT/'examples'/'qualified-conditional-program.smi-graph'
conditional_document=ProgramGraph.open(conditional_path)
conditional_original=conditional_document.state
selection=preview_python(conditional_original)
assert selection.source and not selection.issues, selection.issues
assert len(selection.node_lines)==len(conditional_original['nodes'])
assert any(isinstance(n,ast.IfExp) for n in ast.walk(ast.parse(selection.source)))
compile(selection.source,'<program-graph-conditional-gate>','exec')
assert selection.source==preview_python(ProgramGraph.open(conditional_path).state).source
assert conditional_document.state==conditional_original
with tempfile.TemporaryDirectory() as temporary:
    output=Path(temporary)/'conditional.py'
    receipt=publish_python(conditional_document,output,expected_revision=conditional_document.revision)
    assert receipt.node_lines==selection.node_lines
    assert output.read_text(encoding='utf-8')==selection.source
    assert conditional_document.state==conditional_original
# A qualified execution Branch is not an eager Select node: the generated AST
# must use a real If with Return on both paths. Opening/preview never executes.
branch_path=ROOT/'examples'/'qualified-structured-branch.smi-graph'
branch_document=ProgramGraph.open(branch_path)
branch_before=branch_path.read_bytes()
branch_preview=preview_python(branch_document.state)
assert branch_preview.source and not branch_preview.issues, branch_preview.issues
branch_ast=ast.parse(branch_preview.source)
flow=next(n for n in branch_ast.body[0].body if isinstance(n,ast.If))
assert isinstance(flow.body[-1],ast.Return) and isinstance(flow.orelse[-1],ast.Return)
assert len(branch_preview.node_lines)>=len(branch_document.state['nodes'])
compile(branch_preview.source,'<program-graph-execution-branch>','exec')
with tempfile.TemporaryDirectory() as temporary:
    destination=Path(temporary)/'branch.py'
    receipt=publish_python(branch_document,destination,
                           expected_revision=branch_document.revision)
    assert receipt.node_lines==branch_preview.node_lines
    assert destination.read_text(encoding='utf-8')==branch_preview.source
assert branch_path.read_bytes()==branch_before
# Nested execution branches form a bounded single-entry tree, without joins,
# loops, mutation, or arbitrary side-effect semantics. Source mapping must be
# exact even when Branches/Returns occur at multiple AST depths.
nested_path=ROOT/'examples'/'qualified-nested-branches.smi-graph'
nested_document=ProgramGraph.open(nested_path)
nested_before=nested_path.read_bytes()
nested_preview=preview_python(nested_document.state)
assert nested_preview.source and not nested_preview.issues,nested_preview.issues
assert len({node for node,_ in nested_preview.node_lines})==len(nested_document.state['nodes'])
assert len([n for n in ast.walk(ast.parse(nested_preview.source)) if isinstance(n,ast.If)])==2
lines=dict(nested_preview.node_lines)
source_lines=nested_preview.source.splitlines()
assert 'if ' in source_lines[lines['outer']-1] and 'if ' in source_lines[lines['inner']-1]
for leaf in ('a','b','c'):
    assert 'return ' in source_lines[lines[leaf]-1]
compile(nested_preview.source,'<program-graph-nested-execution-branches>','exec')
with tempfile.TemporaryDirectory() as temporary:
    destination=Path(temporary)/'nested.py'
    receipt=publish_python(nested_document,destination,expected_revision=nested_document.revision)
    assert receipt.node_lines==nested_preview.node_lines
    assert destination.read_text(encoding='utf-8')==nested_preview.source
assert nested_path.read_bytes()==nested_before
# Sequential effect gate: a guarded execution path is not a pure expression.
# The preview must contain an actual unconditional-on-failure exception, not
# Python `assert`, which can disappear under -O. This gate never executes it.
guard_path=ROOT/'examples'/'qualified-guarded-branches.smi-graph'
guard_document=ProgramGraph.open(guard_path)
guard_before=guard_path.read_bytes()
guard_preview=preview_python(guard_document.state)
assert guard_preview.source and not guard_preview.issues,guard_preview.issues
guard_tree=ast.parse(guard_preview.source)
assert len([n for n in ast.walk(guard_tree) if isinstance(n,ast.Raise)])==1
assert not any(isinstance(n,ast.Assert) for n in ast.walk(guard_tree))
guard_lines=dict(guard_preview.node_lines)
assert set(guard_lines)=={n['id'] for n in guard_document.state['nodes']}
assert guard_lines['guard']<guard_lines['outer']
compile(guard_preview.source,'<program-graph-require-gate>','exec')
with tempfile.TemporaryDirectory() as temporary:
    destination=Path(temporary)/'guarded.py'
    receipt=publish_python(guard_document,destination,
        expected_revision=guard_document.revision)
    assert receipt.node_lines==guard_preview.node_lines
    assert destination.read_text(encoding='utf-8')==guard_preview.source
assert guard_path.read_bytes()==guard_before
# Execution-ordered capture gate: the same persisted graph is used by the
# native ProgramGraph preview/publication stage. This captures a typed value
# *after* its explicit exec input and cannot be moved across Branch paths.
ordered_path=ROOT/'examples'/'qualified-ordered-bindings.smi-graph'
ordered_document=ProgramGraph.open(ordered_path)
ordered_before=ordered_path.read_bytes()
ordered_preview=preview_python(ordered_document.state)
assert ordered_preview.source and not ordered_preview.issues,ordered_preview.issues
ordered_lines=dict(ordered_preview.node_lines)
assert set(ordered_lines)=={node['id'] for node in ordered_document.state['nodes']}
assert ordered_lines['store']<ordered_lines['addition']<ordered_lines['out']
compile(ordered_preview.source,'<program-graph-ordered-binding>','exec')
with tempfile.TemporaryDirectory() as temporary:
    destination=Path(temporary)/'capture.py'
    receipt=publish_python(ordered_document,destination,
        expected_revision=ordered_document.revision)
    assert receipt.node_lines==ordered_preview.node_lines
    assert destination.read_text(encoding='utf-8')==ordered_preview.source
assert ordered_path.read_bytes()==ordered_before
# Execution-local state gate: read snapshots must not change when the slot
# is reassigned later. Persist, generate, map, and explicitly publish.
mutable_path=ROOT/'examples'/'qualified-mutable-locals.smi-graph'
mutable_document=ProgramGraph.open(mutable_path)
mutable_before=mutable_path.read_bytes()
mutable_preview=preview_python(mutable_document.state)
assert mutable_preview.source and not mutable_preview.issues,mutable_preview.issues
mutable_ast=ast.parse(mutable_preview.source)
mutable_lines=dict(mutable_preview.node_lines)
assert set(mutable_lines)=={n['id'] for n in mutable_document.state['nodes']}
assert mutable_lines['local']<mutable_lines['read_before']<mutable_lines['assign']<mutable_lines['read_after']
assert any(isinstance(n,ast.Assign) and n.targets[0].id.startswith('_smi_slot_')
           for n in ast.walk(mutable_ast))
compile(mutable_preview.source,'<program-graph-mutable-locals>','exec')
with tempfile.TemporaryDirectory() as temporary:
    destination=Path(temporary)/'mutable.py'
    receipt=publish_python(mutable_document,destination,
        expected_revision=mutable_document.revision)
    assert receipt.node_lines==mutable_preview.node_lines
    assert destination.read_text(encoding='utf-8')==mutable_preview.source
assert mutable_path.read_bytes()==mutable_before

# A bounded counted loop reuses the same AST lowerer and guarded publication.
# The saved graph retains explicit Body/After control paths and a terminating
# Repeat End; no arbitrary back-edge or implicit loop body is fabricated.
repeat_path=ROOT/'examples'/'qualified-bounded-repeat.smi-graph'
repeat_document=ProgramGraph.open(repeat_path)
repeat_before=repeat_path.read_bytes()
repeat_preview=preview_python(repeat_document.state)
assert repeat_preview.source and not repeat_preview.issues, repeat_preview.issues
repeat_ast=ast.parse(repeat_preview.source)
assert len([n for n in ast.walk(repeat_ast) if isinstance(n,ast.For)])==1
repeat_lines=dict(repeat_preview.node_lines)
assert len(repeat_preview.node_lines)==len(repeat_document.state['nodes'])
assert set(repeat_lines)=={n['id'] for n in repeat_document.state['nodes']}
assert repeat_lines['repeat']<=repeat_lines['snapshot']<=repeat_lines['end']<repeat_lines['final_snapshot']
compile(repeat_preview.source,'<program-graph-repeat-gate>','exec')
with tempfile.TemporaryDirectory() as temporary:
    output=Path(temporary)/'repeat.py'
    receipt=publish_python(repeat_document,output,expected_revision=repeat_document.revision)
    assert receipt.node_lines==repeat_preview.node_lines
    assert output.read_text(encoding='utf-8')==repeat_preview.source
assert repeat_path.read_bytes()==repeat_before
# A qualified *execution-ordered* call may invoke a function with Require or
# Repeat effects, unlike the older pure data-only Call node. This fixture is
# a saved document; preview never executes it and publication cannot overwrite.
call_path=ROOT/'examples'/'qualified-execution-call.smi-graph'
call_document=ProgramGraph.open(call_path)
call_before=call_path.read_bytes()
call_preview=preview_python(call_document.state)
assert call_preview.source and not call_preview.issues,call_preview.issues
assert set(dict(call_preview.node_lines))=={n['id'] for n in call_document.state['nodes']}
assert any(isinstance(node,ast.Call) for node in ast.walk(ast.parse(call_preview.source)))
compile(call_preview.source,'<program-graph-execution-call>','exec')
with tempfile.TemporaryDirectory() as temporary:
    output=Path(temporary)/'ordered-call.py'
    receipt=publish_python(call_document,output,expected_revision=call_document.revision)
    assert receipt.node_lines==call_preview.node_lines
    assert output.read_text(encoding='utf-8')==call_preview.source
assert call_path.read_bytes()==call_before
print('PROGRAM_GRAPH_EXECUTION_CALL_GATE_PASS',len(call_preview.node_lines),'mapped graph nodes')

print('PROGRAM_GRAPH_BOUNDED_REPEAT_GATE_PASS',len(repeat_lines),'mapped graph nodes')

print('PROGRAM_GRAPH_MUTABLE_LOCAL_GATE_PASS',len(mutable_lines),'mapped graph nodes')
print('PROGRAM_GRAPH_ORDERED_BINDING_GATE_PASS',len(ordered_lines),'mapped graph nodes')
print('PROGRAM_GRAPH_REQUIRE_GATE_PASS',len(guard_lines),'mapped graph nodes')
print('PROGRAM_GRAPH_NESTED_BRANCH_GATE_PASS',len(nested_preview.node_lines),'mapped graph nodes')
print('PROGRAM_GRAPH_BRANCH_GATE_PASS',len(branch_preview.node_lines),'mapped graph nodes')
print('PROGRAM_GRAPH_CONDITIONAL_GATE_PASS',len(selection.node_lines),'pure eager selection operations')
print('PROGRAM_GRAPH_PYTHON_GATE_PASS',len(preview.node_lines),'stable source mappings and guarded publication')
