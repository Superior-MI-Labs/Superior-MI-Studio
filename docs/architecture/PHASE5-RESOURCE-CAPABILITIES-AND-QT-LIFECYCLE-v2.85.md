# v2.85 — Resource capabilities, current-revision evidence and Qt lifecycle

Status: headless qualification candidate. Native Linux/Qt confirmation pending. v2.81 remains the latest host-qualified rollback.

## Evidence and root hypothesis

The uploaded v2.84 `qualification-20261102-004458-35583.tar.gz` has passing doctor, recovery, document and program stages. The integration stage reaches `committed-source-history` and then exits 124 (75-second stage limit). At the end of the fixture, `w.close()` is called after earlier scenarios left `SourceDocumentSession` drafts dirty. The production `NativeLab.closeEvent` prompts for confirmation, correctly preventing unapproved data loss. No test handler answers that prompt. This directly explains a blocked nested Qt dialog. The v2.85 smoke explicitly exercises **No** (window and dirty revision retained) and **Yes** (window closes), using the established `exercise_modal` event-loop supervisor with a 5-second deadline. Production close behavior is unchanged. Confirm with the native report before claiming the hypothesis proven.

## Architecture comparison

Rejected: a generic text-editor/parser authority for every asset format, and a recursive filesystem index for relationships. Both duplicate document owners or create unbounded I/O, runtime-resolution ambiguity and a second workspace model.

Chosen: extend the existing `resource_graph.preview_kind` + `expanded_file_preview` capability and `NodeItem` read-only paint path. Plain text preview is explicit on expand, restricted to known text/config extensions, first 4096 bytes and eight sanitized UTF-8 lines (max 58 characters per line). No HTML execution or modification; symlinks, hidden/config-secret file names, invalid binary and oversized files are refused. The source-owning Python editor remains unchanged.

For associations, reuse the existing opt-in static evidence providers. `source_associations._parse_existing_source` consolidates bounded AST reads. The view passes transient open source-session text; this is a read-only snapshot from the sole authority, never a cache or alternative revision owner. Invalid live drafts suppress their saved-file evidence rather than claiming stale links. An expanded folder contributes its visible child file nodes to the same relationship graph, capped at 72 Python source files, without scanning unseen directories. All edges remain candidates with syntax/line provenance, not runtime or execution connections.

## Verification requirements

- Headless: `bash scripts/agent-verify.sh --headless`, validate strict preview bounds, invalid UTF-8 and binary refusal, dirty/invalid revision evidence, expanded-visible siblings and no file writes.
- Native: previous navigation stages, `resource-file-previews-and-verified-links`, `expanded-folder-live-relationship-evidence`, and `integration-shutdown-discard-confirmation`; all four Qt subprocess PASS markers. Verify cancel and confirm behavior, not just absence of hangs.
- Installer may only prune old versions/logs after the complete native gate succeeds. The last qualified v2.81 build is the rollback if v2.85 fails.

## Deferred

Do not build a generic editable file document, recursive dependency index or open-ended cross-folder import resolver yet. Formal provider contracts and explicit relative-path/import rules are needed before those capabilities can claim correctness.
