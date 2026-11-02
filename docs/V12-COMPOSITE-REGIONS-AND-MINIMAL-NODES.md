# v1.2 — Composite source graphs / lean source-node chrome

## The decision

The visual graph is a **projection of source**, not an independent Python runtime. Internal SSA/phi/control bookkeeping must not become visible authored operations. `PythonDocument.scope_graph()` and `readable_scope_graph()` stay authoritative for existing source-backed semantics; `composite_file_graph()` only arranges and attaches existing nodes under their owning definition.

The core visual building block is a **code region**, which may contain statements/expressions and other regions. It is not synonymous with a lexical scope or a brace pair:

* A function definition has a body region and a callable interface.
* An if/else has distinct branch regions with normal/exceptional flow exits, and may or may not introduce a language-specific lexical scope.
* A loop has a body region; the loop construct provides repetition, condition, `break`, `continue`, and optional normal completion. The body is not a separate execution operation.
* A class/namespace has a member region, not necessarily ordinary sequential statements.
* Curly braces may instead introduce a literal/initializer, macro body or other syntax: the adapter must classify them.
* Python uses indentation; for/if/while suites do not ordinarily create local variable scopes.

## Interaction rules

1. Source file stays authoritative. A composite is one function/class **definition**, not a copy plus a duplicate dashed rectangle.
2. A composite's expanded and collapsed states keep the same source IDs and boundary ports.
3. The Qt scene owns a single nested hierarchy: child `NodeItem`s have their containing definition as native Qt parent; there is no nested QGraphicsView or independent scene per graph.
4. Expanded nodes move with their owner; control/data edges use `mapToScene` to connect the existing source ports.
5. Focus view retains its previous standalone scope view for dense code; Whole File uses nested composites.
6. Port labels remain contextual and text-sized; the source header is one line and the inspector retains signature, source span and details.
7. No synthetic return pins are assigned to arbitrary `while`/`for` blocks. A `return` exits a callable; `break` exits a loop; `continue` advances a loop, `throw` propagates/handles according to the language.

## v1.2 implemented boundary

* `composite_file_graph`: derived ownership + local coordinates for source-backed functions/classes; no added/deleted semantic nodes, edges, or execution behavior.
* `GraphCanvas.rebuild`: native Qt parent/child ownership using source-scope keys; no duplicate region rectangles.
* Compact Python source nodes, including definition header, ports, and no redundant source details/status/filter within the node.
* Collapsing and nested scopes retain the already-existing source-scope state.
* Regression tests verify identities, edge integrity, graph containment, nested definitions, source immutability and loop non-scoping.

## Not implemented / next qualification

* Editable boundary-routing from internal `return` values to the expanded function's output port. The definition's external return signature is retained; early returns require explicit exit terminals and validated semantics.
* `if` and loop *body* regions as separately expandable composite regions; they currently remain ordinary flow nodes with real statement children/edges, avoiding imaginary `WHILE BODY` operations.
* Auto-layout optimization, collision avoidance for arbitrary nested regions and graphical interaction qualification on the user's Linux host.
* Multi-language adapters and general bidirectional source editing.

## Evidence and safety

`python3 -m unittest discover -s tests -q`; `python3 -m compileall -q studio_native`; `bash -n *.sh`.

The build container has no PyQt6 installation; no Qt rendering/GUI claim is made. Run `./test-qt-offscreen.sh` on the Linux host, then inspect whole-file expand/collapse and move nested composite nodes, and report the host trace if a test fails. Do not infer source equivalence from geometry alone.
