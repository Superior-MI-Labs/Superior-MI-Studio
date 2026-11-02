"""One adapter-authorized action list for library, graph search and pin-drop.

No GUI or graph renderer independently decides whether a source operation is
creatable. Observed nodes are never automatically executable templates.
"""
from __future__ import annotations
from dataclasses import dataclass
from .operation_catalog import qualified_operations
from .python_authoring import (eligible_targets, eligible_return_targets,
                               eligible_pass_targets, eligible_parameter_returns, compatible_parameter_pin,
                               compatible_parameter_return_pin, eligible_call_pass_targets,
                               eligible_call_return_targets, eligible_entry_functions, eligible_signature_functions, eligible_flow_pass_targets,
                               eligible_composition_targets, compatible_composition_pin,
                               eligible_value_assignment_targets, compatible_value_assignment_pin,
                               eligible_composed_call_targets, compatible_composed_call_pin, eligible_rename_functions, eligible_parameter_renames)


@dataclass(frozen=True)
class CreationAction:
    id: str
    title: str
    category: str
    description: str
    source_scope: str | None = None
    parameter: str | None = None
    anchor: dict | None = None


def qualified_composition_anchors(doc, operation_id: str):
    """One GUI-facing (scope, available values, source anchor) contract.

    The adapter's Call eligibility includes a fourth field of verified callee
    signatures. This is intentionally excluded from the anchor picker: after
    choosing a scope, the Call form resolves the current signatures again.
    The source adapter remains the sole authority for eligibility.
    """
    if doc is None:return ()
    if operation_id=='python.call-with-values.v1':
        return tuple((scope,names,anchor) for scope,names,anchor,_
                     in eligible_composed_call_targets(doc))
    if operation_id=='python.compose-binary-local.v1':
        return eligible_composition_targets(doc)
    if operation_id=='python.assign-source-local.v1':
        return eligible_value_assignment_targets(doc)
    return ()


def available_actions(doc, *, pin: tuple[str,str] | None = None) -> tuple[CreationAction, ...]:
    """Show only qualified source lowerings and actually eligible anchors.

    A pin-drop exposes only actions whose adapter can create the connection
    through a source change. Never display unrelated source builders as if
    they were compatible with a typed output.
    """
    if doc is None:return ()
    available={definition.id:definition for definition in qualified_operations('python')}
    if pin is not None:
        # Both source patterns are independently proven against exact port IDs:
        # a Pass can become an arithmetic result, while a direct Return can
        # receive a preceding comparison Branch. These are not generic edges.
        pass_targets=compatible_parameter_pin(doc,*pin)
        return_targets=compatible_parameter_return_pin(doc,*pin)
        actions=[]
        for scope,name,anchor in pass_targets:
            for ident,category,description in (
                    ('python.return-parameter-from-pass.v1','Data / Return',
                     'Connect this parameter to Return (replaces pass)'),
                    ('python.arithmetic-return-from-pass.v1','Data / Arithmetic',
                     'Create a parameter arithmetic expression feeding Return')):
                definition=available[ident]
                actions.append(CreationAction(ident,definition.title,category,description,
                                             scope,name,anchor))
        # A typed parameter output may also supply the input of a newly
        # authored Branch/Loop. The source function must qualify for the exact
        # same standalone placeholder transformation as menu creation.
        flow={(key,tuple(sorted(anchor.items()))) for key,_,anchor in eligible_flow_pass_targets(doc)}
        for scope,name,anchor in pass_targets:
            if (scope,tuple(sorted(anchor.items()))) not in flow:
                continue
            for ident,category,description in (
                    ('python.conditional-return-from-pass.v1','Control / Branch',
                     'Create a comparison Branch consuming this parameter'),
                    ('python.for-range-accumulate.v1','Control / Loop',
                     'Create a For range loop using this parameter'),
                    ('python.while-countdown.v1','Control / Loop',
                     'Create a While countdown using this parameter')):
                definition=available[ident]
                actions.append(CreationAction(ident,definition.title,category,description,
                                             scope,name,anchor))
        for scope,name,anchor in return_targets:
            ident='python.comparison-branch-return.v1'
            definition=available[ident]
            actions.append(CreationAction(ident,definition.title,'Control / Comparison',
                      'Create a comparison Branch from this parameter before Return',
                      scope,name,anchor))
        calls_pass={(scope,tuple(sorted(anchor.items()))) for scope,anchor,_ in eligible_call_pass_targets(doc)}
        calls_return={(scope,tuple(sorted(anchor.items()))) for scope,anchor,_ in eligible_call_return_targets(doc)}
        for scope,name,anchor in pass_targets:
            if (scope,tuple(sorted(anchor.items()))) in calls_pass:
                ident='python.call-return-from-pass.v1'
                actions.append(CreationAction(ident,available[ident].title,'Function / Call',
                    'Call a qualified function with this parameter and connect its result to Return',
                    scope,name,anchor))
        for scope,name,anchor in return_targets:
            if (scope,tuple(sorted(anchor.items()))) in calls_return:
                ident='python.call-before-return.v1'
                actions.append(CreationAction(ident,available[ident].title,'Function / Call',
                    'Insert an explicit effectful function Call before the existing Return',
                    scope,name,anchor))
        for scope,name,anchor in compatible_value_assignment_pin(doc,*pin):
            ident='python.assign-source-local.v1'
            definition=available[ident]
            actions.append(CreationAction(ident,definition.title,'Data / Variables',
                'Store this proven source value in a fresh local variable',scope,name,anchor))
        for scope,name,anchor in compatible_composed_call_pin(doc,*pin):
            ident='python.call-with-values.v1'
            definition=available[ident]
            actions.append(CreationAction(ident,definition.title,'Function / Call',
                'Use this proven value as an input to a stored function Call',scope,name,anchor))
        for scope,name,anchor in compatible_composition_pin(doc,*pin):
            ident='python.compose-binary-local.v1'
            definition=available[ident]
            actions.append(CreationAction(ident,definition.title,'Data / Composition',
                'Compose an operation with this stored input and create a new local',scope,name,anchor))
        return tuple(actions)
    kinds=(('python.rename-parameter.v1','Function / Interface',bool(eligible_parameter_renames(doc))),
           ('python.rename-function.v1','Function / Interface',bool(eligible_rename_functions(doc))),
           ('python.call-with-values.v1','Function / Call',bool(eligible_composed_call_targets(doc))),
           ('python.assign-source-local.v1','Data / Variables',bool(eligible_value_assignment_targets(doc))),
           ('python.compose-binary-local.v1','Data / Composition',bool(eligible_composition_targets(doc))),
           ('python.create-function.v1','Function / Definition',True),
           ('python.create-main-entry.v1','Program / Entry',bool(eligible_entry_functions(doc))),
           ('python.add-optional-keyword-parameter.v1','Function / Interface',bool(eligible_signature_functions(doc))),
           ('python.branch-early-return.v1','Control / Branch',bool(eligible_targets(doc))),
           ('python.local-literal-return.v1','Data / Assignment',bool(eligible_return_targets(doc))),
           ('python.return-from-pass.v1','Function / Return',bool(eligible_pass_targets(doc))),
           ('python.return-parameter-from-pass.v1','Data / Return',bool(eligible_parameter_returns(doc))),
           ('python.arithmetic-return-from-pass.v1','Data / Arithmetic',bool(eligible_parameter_returns(doc))),
           ('python.comparison-branch-return.v1','Control / Comparison',bool(eligible_targets(doc))),
           ('python.call-return-from-pass.v1','Function / Call',bool(eligible_call_pass_targets(doc))),
           ('python.call-before-return.v1','Function / Call',bool(eligible_call_return_targets(doc))),
           ('python.conditional-return-from-pass.v1','Control / Branch',bool(eligible_flow_pass_targets(doc))),
           ('python.for-range-accumulate.v1','Control / Loop',bool(eligible_flow_pass_targets(doc))),
           ('python.while-countdown.v1','Control / Loop',bool(eligible_flow_pass_targets(doc))))
    return tuple(CreationAction(available[ident].id,available[ident].title,category,
                       'Adapter-qualified transformation. Review diff before saving.')
                 for ident,category,ready in kinds if ready)


def search_actions(actions, query: str):
    """Case-insensitive all-token match across real action metadata."""
    terms=str(query).strip().casefold().split()
    if not terms:return tuple(actions)
    return tuple(a for a in actions if all(term in
        f'{a.title} {a.category} {a.description} {a.id}'.casefold() for term in terms))
