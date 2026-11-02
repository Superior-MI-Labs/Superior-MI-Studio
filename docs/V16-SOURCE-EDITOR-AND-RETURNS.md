# v1.6 — Source Editing and Boundary Returns

## Ownership / architecture

- `PythonDocument` and its original file bytes are the only source graph authority. The right-hand `QPlainTextEdit` buffer is an **unsaved draft** until committed. Parsing is triggered on open/reload/save, not on every keystroke.
- `source_editor.py` is a Qt-free transaction and source-position boundary. It converts AST UTF-8 byte columns into Qt UTF-16 character offsets (including non-BMP Unicode), validates candidate Python via AST/compile without executing it, retains uniform CRLF/LF convention, and hands validated byte proposals to the pre-existing atomic `apply_proposal` writer.
- The pre-existing writer creates a numbered create-only backup, checks for changes since loading and immediately before replacement, preserves file mode, and commits by atomic replace on the same filesystem. This protects common edits but does not implement multi-process locking.
- The Qt pane has a single syntax-colored monospaced text editor. Node selection highlights the exact original span and scrolls to it. If text is dirty, node locations may be stale, so highlight/rewiring is disabled until a successful save and reparse.
- `View` menu provides Node Inspector on demand, hidden by default. It continues to support prototype authoring. The source-editor dock is the default panel.
- For a simple trailing return, `composite_file_graph` retains the original return node and all semantic edges, but marks its readable card as hidden and stores the owning function scope. The existing `GraphCanvas` maps an eligible value edge to the function's existing inner output-port mirror. Early returns, including nested branches/loops, remain explicit. No synthesized semantic edge or port was added.

## Safety and limitations

- Source editing currently supports regular `.py` files within the existing 1.5 MB analysis bound. Mixed newline styles are refused to avoid unrelated formatting changes. The syntax-coloring pass is only cosmetic and does not replace Python's AST semantics.
- The only text-to-graph sync is **Save**, not live reparsing while typing. After a valid save the graph is reparsed. Visual-to-text rewiring remains limited to the existing guarded operations.
- The Python runner is opt-in and **not sandboxed**. It refuses to run with unsaved text. Reconciliation after concurrent writes is not automatic: save refuses rather than overwrites.
- Return folding applies only to a function with one final direct return and no additional return operations within that function. `return` inside branches and loops retains its own exit semantics. Future support must distinguish exception/yield/async exits.
- No new execution node, language-specific Qt widget family, or alternate graph document was introduced.

## Verification

Run `./doctor.sh` for parser, source transaction, port/graph, nested-region and expression coverage; `./test-qt-offscreen.sh` to qualify actual Qt selection highlighting, default panels, source save/reparse, boundary pin display, and the earlier viewport/renderer regression suite on a machine with PyQt6 installed.
