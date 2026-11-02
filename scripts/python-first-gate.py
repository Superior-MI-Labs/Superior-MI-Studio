#!/usr/bin/env python3
"""Read-only Python adapter coverage plus isolated visual-program construction.

Never executes analyzed Python. Never modifies example sources. This gate is a
starting point, NOT final approval for a second language adapter.
"""
from __future__ import annotations
import ast
import json
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from studio_native.python_graph import PythonDocument
from studio_native.semantic_contract import describe_graph
from studio_native.python_edit import apply_proposal
from studio_native.python_authoring import (propose_create_function, propose_create_main_entry,
    propose_return_from_pass, propose_return_parameter_from_pass, propose_add_optional_parameter, eligible_pass_targets,
    eligible_flow_pass_targets, propose_conditional_returns_from_pass,
    propose_for_range_accumulate, propose_while_countdown,
    eligible_composition_targets, propose_compose_binary_local,
    eligible_value_assignment_targets, propose_assign_source_value,
    eligible_composed_call_targets, propose_composed_call,
    propose_rename_function, propose_rename_parameter)
from studio_native.authoring_contract import OperandReference, BinaryComposition, ValueAssignment, CallComposition


def run_gate():
    examples=sorted((ROOT/'examples').glob('*.py'))
    if not examples:raise AssertionError('No Python fixtures found')
    projects=[]
    for source in examples:
        before=source.read_bytes()
        doc=PythonDocument(source)
        count=0
        for scope in doc.scopes:
            desc=describe_graph(doc.scope_graph(scope),origin='source')
            count+=len(desc.nodes)
        if source.read_bytes()!=before:
            raise AssertionError(f'Analyzing {source} mutated its Python source')
        projects.append({'file':source.name,'scopes':len(doc.scopes),'nodes':count})
    with tempfile.TemporaryDirectory(prefix='smi-python-first-gate-') as folder:
        path=Path(folder)/'program.py';path.write_bytes(b'')
        proposal=propose_create_function(PythonDocument(path),'start','')
        assert path.read_bytes()==b''
        apply_proposal(proposal)
        doc=PythonDocument(path)
        scope,anchor=next((key,anchor) for key,anchor in eligible_pass_targets(doc)
                          if doc.scopes[key].title=='start')
        apply_proposal(propose_return_from_pass(doc,scope,'42',anchor))
        apply_proposal(propose_create_main_entry(PythonDocument(path),'start'))
        expected='def start():\n    return 42\n\nif __name__ == "__main__":\n    print(start())\n'
        assert ast.dump(ast.parse(path.read_text()))==ast.dump(ast.parse(expected))
        program=PythonDocument(path)
        assert any(n.get('source_kind')=='branch' for n in program.scope_graph('module')['nodes'])
        # Text-authored and visually produced graphs must have same projection.
        handwritten=Path(folder)/'handwritten.py';handwritten.write_text(expected)
        other=PythonDocument(handwritten)
        for key in program.scopes:
            assert key in other.scopes
            left=program.scope_graph(key);right=other.scope_graph(key)
            assert [(n['source_kind'],n['title']) for n in left['nodes']]==[
                (n['source_kind'],n['title']) for n in right['nodes']]
            assert [(e['relation'],e['sourcePort'].split(':')[-1],e['targetPort'].split(':')[-1])
                    for e in left['edges']]==[
                (e['relation'],e['sourcePort'].split(':')[-1],e['targetPort'].split(':')[-1])
                    for e in right['edges']]
        # Edit a user-created interface; existing direct callers remain valid.
        interface=Path(folder)/'interface.py'
        interface.write_text('def compute(x):\n    return x\n\ndef consumer():\n    return compute(7)\n')
        apply_proposal(propose_add_optional_parameter(PythonDocument(interface),'compute','flag','True'))
        changed=interface.read_text()
        assert 'compute(x, *, flag=True)' in changed
        assert 'compute(7, flag=True)' in changed
        PythonDocument(interface)
        # Multi-function program assembled from blank text through ONLY
        # adapter-qualified visual proposals. No user source is evaluated.
        flow_path=Path(folder)/'visual-flow-program.py'
        flow_path.write_bytes(b'')
        for name,params in (('classify','value'),('sum_to','limit'),
                            ('countdown','limit'),('start','')):
            apply_proposal(propose_create_function(PythonDocument(flow_path),name,params))
        def flow_anchor(name):
            document=PythonDocument(flow_path)
            scope,parameters,anchor=next((key,p,a) for key,p,a in eligible_flow_pass_targets(document)
                      if document.scopes[key].title==name)
            return document,scope,parameters,anchor
        document,scope,parameters,anchor=flow_anchor('classify')
        apply_proposal(propose_conditional_returns_from_pass(document,scope,'value','<',
                                                             '0','-1','1',anchor))
        document,scope,parameters,anchor=flow_anchor('sum_to')
        apply_proposal(propose_for_range_accumulate(document,scope,'limit','index','total',anchor))
        document,scope,parameters,anchor=flow_anchor('countdown')
        apply_proposal(propose_while_countdown(document,scope,'limit','remaining','steps',anchor))
        document=PythonDocument(flow_path)
        scope,anchor=next((key,a) for key,a in eligible_pass_targets(document)
                           if document.scopes[key].title=='start')
        apply_proposal(propose_return_from_pass(document,scope,'42',anchor))
        apply_proposal(propose_create_main_entry(PythonDocument(flow_path),'start'))
        expected_flow=('def classify(value):\n'
                       '    if value < 0:\n        return -1\n    return 1\n\n'
                       'def sum_to(limit):\n    total = 0\n'
                       '    for index in range(limit):\n        total += index\n'
                       '    return total\n\n'
                       'def countdown(limit):\n    remaining = limit\n'
                       '    steps = 0\n    while remaining > 0:\n'
                       '        remaining -= 1\n        steps += 1\n'
                       '    return steps\n\n'
                       'def start():\n    return 42\n\n'
                       'if __name__ == "__main__":\n    print(start())\n')
        assert ast.dump(ast.parse(flow_path.read_text()))==ast.dump(ast.parse(expected_flow))
        handwritten_flow=Path(folder)/'handwritten-flow-program.py'
        handwritten_flow.write_text(expected_flow)
        visual=PythonDocument(flow_path)
        typed=PythonDocument(handwritten_flow)
        assert visual.scopes.keys()==typed.scopes.keys()
        for key in visual.scopes:
            left=visual.scope_graph(key);right=typed.scope_graph(key)
            assert [(n['source_kind'],n['title']) for n in left['nodes']]==[
                (n['source_kind'],n['title']) for n in right['nodes']]
            assert [(e['relation'],e['sourcePort'].split(':')[-1],e['targetPort'].split(':')[-1])
                    for e in left['edges']]==[
                (e['relation'],e['sourcePort'].split(':')[-1],e['targetPort'].split(':')[-1])
                for e in right['edges']]
            describe_graph(visual.scope_graph(key),origin='source')
        # A multi-step dataflow created entirely by qualified visual proposals,
        # reconstructed through exactly the same Python graph as handwritten code.
        composed_path=Path(folder)/'composed.py';composed_path.write_bytes(b'')
        apply_proposal(propose_create_function(PythonDocument(composed_path),'compute','value'))
        document=PythonDocument(composed_path)
        scope,anchor=next((key,a) for key,a in eligible_pass_targets(document)
                          if document.scopes[key].title=='compute')
        apply_proposal(propose_return_parameter_from_pass(document,scope,'value',anchor))
        # Store both a parameter and a primitive literal as separate source
        # producers. Then read those stored values through visual composition.
        for operand,name in ((OperandReference('name','value'),'seed'),
                             (OperandReference('literal','2'),'two')):
            document=PythonDocument(composed_path)
            scope,names,anchor=next((key,n,a) for key,n,a in eligible_value_assignment_targets(document)
                                    if document.scopes[key].title=='compute')
            proposal=propose_assign_source_value(document,scope,
                        ValueAssignment(operand,name,False),anchor)
            assert composed_path.read_bytes()==document.raw
            apply_proposal(proposal)
        for left,op,right,local,connect in (
                ('seed','+','two','step',False),('step','*','3','total',True)):
            document=PythonDocument(composed_path)
            scope,names,anchor=next((key,n,a) for key,n,a in eligible_composition_targets(document)
                                    if document.scopes[key].title=='compute')
            assert left in names
            right_operand=(OperandReference('name',right) if right in names else
                           OperandReference('literal',right))
            req=BinaryComposition(OperandReference('name',left),op,
                                  right_operand,local,connect)
            proposal=propose_compose_binary_local(document,scope,req,anchor)
            assert composed_path.read_bytes()==document.raw
            apply_proposal(proposal)
        expected_composed=('def compute(value):\n    seed = value\n    two = 2\n'
                           '    step = seed + two\n    total = step * 3\n    return total\n')
        assert composed_path.read_text()==expected_composed
        hand_path=Path(folder)/'hand-composed.py';hand_path.write_text(expected_composed)
        imported=PythonDocument(composed_path);typed=PythonDocument(hand_path)
        for key in imported.scopes:
            left=imported.scope_graph(key);right=typed.scope_graph(key)
            assert [(n['source_kind'],n['title']) for n in left['nodes']]==[
                (n['source_kind'],n['title']) for n in right['nodes']]
            assert [(e['relation'],e['sourcePort'].split(':')[-1],e['targetPort'].split(':')[-1])
                    for e in left['edges']]==[
                (e['relation'],e['sourcePort'].split(':')[-1],e['targetPort'].split(':')[-1])
                for e in right['edges']]
            describe_graph(left,origin='source')
        # v2.49 full vertical slice: construct two functions from blank source,
        # bind function call inputs to stored producers, reuse the stored Call
        # result, then refactor the called interface through guarded proposals.
        functions=Path(folder)/'function-workflow.py';functions.write_bytes(b'')
        for name in ('increase','run'):
            apply_proposal(propose_create_function(PythonDocument(functions),name,'value'))
        for name in ('increase','run'):
            doc=PythonDocument(functions)
            scope,anchor=next((k,a) for k,a in eligible_pass_targets(doc)
                              if doc.scopes[k].title==name)
            apply_proposal(propose_return_parameter_from_pass(doc,scope,'value',anchor))
        doc=PythonDocument(functions)
        scope,names,anchor=next((k,n,a) for k,n,a in eligible_composition_targets(doc)
                               if doc.scopes[k].title=='increase')
        apply_proposal(propose_compose_binary_local(doc,scope,
            BinaryComposition(OperandReference('name','value'),'+',OperandReference('literal','1'),
                              'incremented',True),anchor))
        doc=PythonDocument(functions)
        scope,names,anchor,callees=next((k,n,a,c) for k,n,a,c in eligible_composed_call_targets(doc)
                                     if doc.scopes[k].title=='run')
        assert dict(callees)['increase']==('value',)
        proposal=propose_composed_call(doc,scope,CallComposition('increase',
            (OperandReference('name','value'),),'stored',False),anchor)
        assert functions.read_bytes()==doc.raw
        apply_proposal(proposal)
        doc=PythonDocument(functions)
        scope,names,anchor=next((k,n,a) for k,n,a in eligible_composition_targets(doc)
                               if doc.scopes[k].title=='run')
        assert 'stored' in names
        apply_proposal(propose_compose_binary_local(doc,scope,
            BinaryComposition(OperandReference('name','stored'),'*',OperandReference('literal','2'),
                              'output',True),anchor))
        apply_proposal(propose_rename_parameter(PythonDocument(functions),'increase','value','input_value'))
        apply_proposal(propose_rename_function(PythonDocument(functions),'increase','increment'))
        expected_functions=('def increment(input_value):\n    incremented = input_value + 1\n'
                            '    return incremented\n\n'
                            'def run(value):\n    stored = increment(value)\n'
                            '    output = stored * 2\n    return output\n')
        assert ast.dump(ast.parse(functions.read_text()))==ast.dump(ast.parse(expected_functions))
        handwritten_functions=Path(folder)/'handwritten-functions.py'
        handwritten_functions.write_text(expected_functions)
        actual_doc=PythonDocument(functions);hand_doc=PythonDocument(handwritten_functions)
        assert actual_doc.scopes.keys()==hand_doc.scopes.keys()
        for key in actual_doc.scopes:
            visual=actual_doc.scope_graph(key);typed=hand_doc.scope_graph(key)
            assert [(n['source_kind'],n['title']) for n in visual['nodes']]==[
                (n['source_kind'],n['title']) for n in typed['nodes']]
            assert [(e['relation'],e['sourcePort'].split(':')[-1],e['targetPort'].split(':')[-1])
                    for e in visual['edges']]==[
                (e['relation'],e['sourcePort'].split(':')[-1],e['targetPort'].split(':')[-1])
                for e in typed['edges']]
            describe_graph(visual,origin='source')
    return {'status':'PASS','examples_checked':len(projects),
            'source_backed_scope_count':sum(x['scopes'] for x in projects),
            'source_nodes_checked':sum(x['nodes'] for x in projects),
            'visual_program_from_empty_file':True,'text_graph_parity':True,
            'function_interface_and_local_call_migration':True,
            'multi_function_branch_for_while_program_from_blank':True,
            'multi_function_visual_vs_typed_graph_parity':True,
            'chained_binary_composition_from_blank_parity':True,
            'qualified_variable_store_and_get_parity':True,
            'function_call_composition_and_interface_refactor_parity':True,
            'examples':projects}


if __name__=='__main__':
    try:print(json.dumps(run_gate(),indent=2))
    except Exception as exc:
        print('PYTHON_FIRST_GATE_FAILED:',repr(exc),file=sys.stderr)
        raise
