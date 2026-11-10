# v2.139 — One exact source-owner receipt for independent compiler proof

## Root cause

Independent function review captured a source revision and text, then checked
disk currency before/after compiler proof. A normal source document save can
advance `SourceDocumentSession.saved_raw` without advancing the revision or
changing the live editor text. A callback saving the draft during review or
between review planning and graph import could therefore change the saved
baseline while still passing both source-text and disk-current checks. The
successful graph import would be based on the wrong saved source preimage.
A reentrant editor change *inside* the last disk check likewise had no
post-inspection snapshot comparison.

## Decision

**Selected:** retain `SourceDocumentSession` as the only text owner and
`ProgramGraph` as the only graph writer. One small read-only compiler helper,
`_assert_independent_source_snapshot`, accepts transient revision, live text
and exact saved bytes, checks all three before and after the existing disk
inspection, and refuses any change. Both the failed-proof diagnostic branch
and successful review/import use the same check. An independent import keeps
its initial saved-byte snapshot across the entire planner operation, even
when the accepted graph edit batch is empty. A final graph revision check
covers the no-op path. Unencodable UTF-8 import drafts now receive the same
`ProgramGraphError` as independent reviews.

**Rejected:** a second persistent receipt store, rollback of source saves,
extra source parsing, and an importer that trusts a previous review token
without requalification.

## Qualification

`tests/test_v2139_independent_receipt_integrity.py` includes successful
review/import; source commit during a successful or failed proof; source
commit after planning and on a no-op import; source reentrancy *during*
external inspection; and malformed Unicode at the import boundary.
Existing v2.126 source revision/disk and v2.127 linked-source tests remain
required. No new writer, revision mechanism, compiler AST semantics, or ADR.

Host evidence: user-supplied `qualification-20261110-184157-31566.tar.gz`
reports 1,405 tests, `PYTHON_FIRST_GATE_PASS`,
`NATIVE_QT_SMOKE_PASS`, `CHECKS_PASS` for the v2.138 candidate.
GitHub v2.139 native and headless CI and independent v2.139 Linux Mint
qualification remain separate gates.

Rollback the read-only receipt and import gate to v2.138 if any valid,
unchanged source becomes spuriously unqualified.
