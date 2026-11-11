# v2.141 — Link attachment binds the exact graph/source/disk admission preimage

## Observed failure boundary

`LinkedPythonSource.attach` associated an existing ProgramGraph with a
SourceDocumentSession when the source text and saved bytes matched a generated
Python preview. It performed the external-file check **before** generating
the preview, but then used later reads of `graph.revision`,
`session.revision`, `session.text` and `session.saved_raw` to record a
link. A reentrant editor, source commit, filesystem write or graph edit during
preview could make the link describe **two different revisions** even though
the displayed proof came from one graph snapshot.

## Approaches

- **A.** Create a detached snapshot/link owner with its own version state,
  then reconcile post hoc. Rejected: second mutable authority, duplicated
  conflict rules and unnecessary rollback machinery.
- **B.** Reuse the existing admission path, capture the source revision/text/
  saved-byte preimage and graph revision/fingerprint once, then verify them
  around the same `preview_python` call and external file inspection.
  Selected. Source writes and graph edits remain exclusively owned by
  SourceDocumentSession and ProgramGraph.

## Guarantees

`attach` still requires clean, byte-exact generated Python before linking.
No source file is executed, imported, rewritten or automatically published.
A source edit, changed saved-byte baseline, external write, graph edit, or
callback during external inspection refuses *before* any link object exists.
The graph fingerprint is taken from the admitted graph revision; the link
receipt is stamped with the original captured revisions, never later reads.
A failed preview concurrent with an owner change reports the ownership
conflict first, not a stale compiler diagnostic.

`tests/test_v2141_link_attach_preimage.py` supplies eight adversarial
cases using the existing ProgramGraph fixture and SourceDocumentSession,
including a clean no-op link, reentrant graph/source/disk edits, normalized
text with changed saved bytes, source inspection callbacks, graph fingerprint
callbacks, and failed preview precedence. The native Qt suite continues
to exercise normal link/UI workflows; no new test-only production interface.

No new parser, graph compiler, writer, tab subsystem, global lock or ADR.
Rollback to v2.140 for this scoped attach-method change if either headless
or native CI fails. GitHub CI is separate from Linux Mint host qualification.
