# v2.112 — one synchronous reconciliation preflight, inline installation

## Decision

Keep `ProgramGraph`, `SourceDocumentSession`, and `python_lowering` as the only mutation/semantic authorities. Reuse the caller's just-produced immutable `PythonPreview` and canonical AST inside the private `_qualified_source_edit_plan`, only after checking the expected graph revision and exact base source. No cached snapshots, second importer or source mapping store. Generated-source calls keep their default fresh compilation. The final trial graph is always compiled; explicit import always requalifies source SHA/revision and graph revision.

Capture one defensive deep copy of `ProgramGraph.state` for the entire compiler-plan mapping/trial construction after the revision guard. This avoids repeated deep copies of the same graph and ensures one consistent state is used across all candidate checks. The trial graph is separately constructed and lowered.

Collect candidate assignments, literals, operations, Returns, If/Require and Repeat statements in one read-only AST traversal. Exact line, scope and unique-target rules remain the qualification gates. Input rewires and mutations still go through `ProgramGraph.edit_many`, never a string rewrite.

## Delivery decision

Require one ZIP, not a second downloadable shell script. The user's pasted terminal command extracts the bundled Python installer from the archive, uses `--no-launch`, reports only fresh archives after the run started, and opens Studio only when native qualification succeeded. The existing Python installer remains responsible for safe old-version cleanup and validation. Keep old in-repo shell launchers as compatibility tools, but do not require their separate download.

## Acceptance

The independent preflight's unmodified graph must be previewed once and trial-compiled once for a qualified edit. Generated source still previews its own graph. Source-owned comments stay byte-unchanged, graph import stays atomic and undoable, invalid expressions fail without mutation, and release docs must not require an external `.sh`. The Linux Qt gate remains host-only.
