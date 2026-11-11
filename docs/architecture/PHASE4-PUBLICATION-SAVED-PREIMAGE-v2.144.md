# v2.144 — Saved ProgramGraph preimage remains valid through Python publication

## Identified gap

`publish_python` obtains a clean, saved ProgramGraph state and exact graph
disk bytes via `saved_snapshot_for_publication`. It then generates Python,
validates that Python and writes a new or explicitly preimage-approved
existing `.py` file. Nothing previously rechecked that the graph/document
revision or disk bytes were still the same **immediately before** the
source writer. A reentrant graph edit/save during preview, or an external
change to saved graph bytes, could publish valid Python derived from an
outdated graph while the receipt identified the earlier graph hash.

## Alternatives

A. Invent another publish coordinator and retained graph snapshot/version
cache, or reverse a completed source write when graph changes. Rejected:
duplicate source/graph ownership, fragile rollback, additional concurrency
and source-file conflict risks.

B. Keep the existing `publish_python` and exactly the same source writers
(`create_source_exclusive` for new files, `apply_proposal` with explicit
target digest for replacement). Add a **lexical read-only gate** verifying
that the original graph revision, state and on-disk bytes still match
the saved preimage. Recheck after preview (including failed previews) and
immediately before each existing writer. Selected.

No source execution or graph save occurs in the publisher. A stale graph
fails closed before new-file creation or overwrite/backup. The final
`PythonPublication` receipt is still stamped from the original qualified
graph state and saved bytes rather than a later graph revision. Existing
source destination preimage checks and atomic/exclusive writer behavior
are untouched.

## Evidence and qualification

`tests/test_v2144_publication_saved_preimage.py` has nine real
saved-graph/source-writer cases: normal exact receipt; graph edit during
preview; graph edit and save during preview; external saved-graph replacement;
invalid/raised preview with concurrent graph advance; protected existing
source replacement and its backup; source target-read callback advancing the
graph; and valid destination replacement.

All prior publish, linked, generated and independent-source tests are
retained. No new graph compiler, parser, source writer, app registry, lock
or ADR. GitHub headless/native Qt and independent Linux Mint host
qualification remain required. Rollback to v2.143 if a supported
publication path regresses.
