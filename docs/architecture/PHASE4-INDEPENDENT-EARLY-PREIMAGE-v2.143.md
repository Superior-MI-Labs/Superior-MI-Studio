# v2.143 — Independent-source early admission validates the original owners

## Observed gap

The existing independent-function pipeline rechecks its ProgramGraph and
SourceDocumentSession (revision, text, saved raw and disk) after full compiler
proof, during failed regional diagnosis and after source-span evidence.
However, two **earlier** stages run the Python preview, keyword-call
admission and transient function normalization. A reentrant callback during
these stages could change the actual source, saved baseline, filesystem, or
graph and still return a stale graph/keyword/function diagnostic, or proceed
to parse a different version before the later proof check.

## Alternatives

A. Reparse and resnapshot source independently in each early stage,
introducing separate parser/reader authority and duplicate proof. Rejected.
B. Reuse the v2.142 `assert_proof_owners` lexical guard immediately after
`preview_python`, and at the success/refusal boundary of existing
`_independent_keyword_parameter_contract` and
`_independent_proof_function`. Selected. All operators continue using
the original ProgramGraph, SourceDocumentSession, and single
`_qualified_source_edit_plan`.

The initial source/disk preimage is checked before the preview; a valid
preimage is checked again immediately after it. If the preview rejects
the graph while an owner concurrently changes, the conflict takes
precedence over stale diagnostic text. A failed keyword or local syntax
normalization is likewise not attributed to an obsolete source revision.
No graph edit, source rewrite, new compiler pass, mutable cache or route
owner is added.

## Evidence

`tests/test_v2143_independent_early_preimage.py` includes eight tests:
normal review/import; editor and external file mutations during preview;
graph mutation accompanying an unqualified preview; source mutation during
keyword failure; saved-byte-only drift during transient local proof;
graph mutation during successful local proof; and unchanged precise
missing-function diagnostics.

The existing compiler proof and downstream v2.139–v2.142 tests remain.
A separate Linux Mint host report remains mandatory after GitHub
headless/native Qt CI. Rollback to v2.142 on regression.
