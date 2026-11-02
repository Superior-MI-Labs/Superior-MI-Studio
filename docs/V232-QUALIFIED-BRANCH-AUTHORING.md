# v2.32 · Adapter-qualified Branch authoring, shared source transaction

## Rationale

The read-only Node Library census in v2.31 is a useful observation of *actual* Python syntax. It cannot authorize creation based on node labels, because a Branch's pins and a Python statement's location/scope impose language rules. This release keeps observations read-only and adds one `QualifiedOperation` definition exported by the Python adapter. The UI discovers it through `qualified_operations('python')`, then requests its specific validated lowering.

## Qualified operation

`python.branch-early-return.v1` is one intentional visual-programming transaction consisting of two canonical operations: a `branch` and a `return`. It accepts a current Python function, an exact direct Return source span, one declared parameter, and a primitive literal. It inserts:

```python
if parameter is None:
    return None
```

immediately before the selected existing direct Return. The True path terminates at the new Return, and the False path continues to the original Return. The parsed output uses the ordinary Python analyzer's Branch, Return, value and execution ports. There is no invented backend node, synthetic function/tunnel, or separate visual interpreter.

The `is None` condition is intentionally narrow; it avoids user-defined equality dispatch. Literal values are AST-parsed and accepted only as real primitive constants, never calls, collections or arbitrary expressions. Source creation does not execute the file.

## Single owner of truth

- `python_authoring.py` owns adapter qualification and placement validation.
- `operation_catalog.qualified_operations` merely delegates discovery to each adapter; observed source occurrences remain a separate read-only projection.
- `python_edit._validated_proposal` is now the one validation gate for both existing operand rewrites and new source insertion. `apply_proposal` remains the sole guarded write path; no parallel save implementation exists.
- The builder preserves existing bytes, indentation and CRLF/LF; AST structure verification checks insertion and unchanged prior statements.
- `PythonDocument` reads the saved file again to reconstruct the authoritative graph. Layout, camera and existing node-library prototype state are not edited as substitutes for source changes.

## Known limitations and next gates

This is an explicitly supported **pilot**, not a general-purpose node compiler. It only accepts direct Returns at the top level of a Python function body, on a standalone line with spaces for indentation. Non-constant return expressions on the True path, multi-node creation from general arbitrary edges, function signature edits, loops and variable binding insertion are not qualified yet. Python effects, rich types and dynamic name rebinding need dedicated adapter analysis. Editing still requires an explicit user-approved diff and backup, and it can change generated source-span IDs downstream.

The operation catalog must grow via language-adapter capability definitions with matching lowering and AST/semantic round-trip regressions. Function entry/return boundaries should continue using the verified interface descriptors rather than extra executable compiler nodes.

## Qualification

- Run `./doctor.sh` and Linux Mint `RUN-ALL.sh` / native Qt smoke; note PyQt6 is unavailable in the packaging environment.
- Open Python Source Graph; select **Node Library → Source operations**. On a file containing a supported function, **+ Branch · early return on None** enables. Double-clicking an observed operation still only locates source.
- Build a Branch and review the exact Python diff; reject and verify file unchanged, then apply and check the resulting Branch and two Return sites, execution lanes and backup.
- Confirm stale source and unsaved text edits block creation, and that other file/resource tabs, minimap, selection and cameras remain unaffected.
- Never call this release native-qualified without the host report.
