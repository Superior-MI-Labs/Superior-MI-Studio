# v2.147 — Selected-document mutation commands and honest linked-import outcomes

## Existing failure paths

1. `NativeLab.save_current_document` selected Python saving by its original
   source root page or global source-editor focus. A *secondary* source view
   without focused editor could fall through to the legacy draft writer.
   Resource view Save and source/resource Save As could also save a
   different, inactive prototype document.
2. `ProgramWorkspace.import_linked_python_source` reported a refused import
   without repainting after a late receipt refresh failed. The compiler
   correctly retains a graph transaction that was already committed; the
   Qt view was not reporting that outcome.

## Alternatives and selection

- Add a global save-command service and mutation-receipt store: rejected
  because existing page/graph owners already hold the necessary facts.
- Undo a committed graph transaction on receipt failure: rejected because
  rollback is another user-owned mutation and could overwrite valid work.
- Selected: dispatch through `_graph_tab_for_page`; read-only views refuse
  unsupported saves. On linked-import failure, compare the original graph
  revision, refresh when it changed, and report that the link was unaccepted.
  Legacy / Dev authoring and saved prototype files remain supported.

## Verification and scope

`QT_STAGE selected-document-save-ownership` covers primary/secondary source
saves, resource refusal, source/resource Save As refusal and explicit legacy
saving. `QT_STAGE linked-postcommit-ui-outcome` injects a compiler failure
after a real graph transaction, checking render revision, unaccepted link,
source retention and explicit graph saving. These run as native Qt
qualification, not as substituted headless tests.

No source compiler/parser, persistent owner, file schema, public plugin API,
or ADR changed. Next: characterize remaining root/legacy compatibility
consumers before any deletion. GitHub CI and Linux Mint host qualification
remain separate. Roll back this v2.147 batch if unqualified.
