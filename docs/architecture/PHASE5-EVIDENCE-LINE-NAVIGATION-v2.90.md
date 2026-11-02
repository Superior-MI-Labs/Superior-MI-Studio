# Phase 5: Exact source-evidence navigation and selected resource framing (v2.90)

## Scope and choice

**Implemented:** Existing `GraphCanvas` and Inspector are the presentation layer; `GraphDescriptor` remains the immutable authority for resource evidence; `SourceDocumentSession` remains the sole source revision owner; the established `Route` / `GraphViewSessions` path owns navigation. A small helper in the existing `source_associations` AST reader verifies an evidence span against the *current* source text before allowing the Inspector to jump to its exact line. Non-Python endpoint actions open the enclosing directory and frame/select the existing file card.

**Rejected:** A new file index, evidence database, editable resource document, second source buffer, fuzzy line search, or fallback to saved source after an unsaved change. Relabeling evidence as a verified runtime dependency is also rejected.

## Contracts

- Inspection revalidates the active canvas's exact edge and endpoint identities before any action. Inactive tabs and changed relationship revisions refuse.
- A source-line jump must resolve the actual current live source owner, require a source-ready revision, and confirm that the same import/call AST statement has the original starting line and exact observed source segment. Wrong, deleted or shifted statements and synthetic declaration text refuse; history and tab selection remain untouched. Existing source owner is registered only after preflight succeeds to avoid duplicate recovery prompts.
- After routing, editor focus is applied only when source owner identity and revision are still identical to the preflight. Text remains editable and unchanged. Source line selection uses Qt's current document (not UTF-8 column guesses).
- Non-Python file endpoint routing does not imply an editor. It selects the already rendered file node in the destination resource graph and frames it. No implicit folder expansion, recursive discovery, source edit or file execution.
- All links are syntactic candidates: dynamic imports, runtime paths and executable relationships are *not* inferred.

## Verification

- New headless tests exercise import/call evidence, shifted lines, edited names, invalid drafts, synthetic annotations, Unicode, multiline syntax, upper size limits and identity mismatch.
- Native smoke stage `resource-evidence-line-and-file-framing` checks a real QPushButton, target-card selection, exact source cursor line, Back navigation, stale-draft refusal without history movement, recovery and no dirty source at shutdown. Native host qualification is required before promotion.

## Known limitation

- Generated declaration-match annotations are inspection-only until they have a qualified concrete source span. Exact-line focusing intentionally refuses them; avoid highlighting an unrelated declaration by inferred name.
