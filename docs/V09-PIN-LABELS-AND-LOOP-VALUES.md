# v0.9 implementation decisions

## Shared chip layout
- A single `PortItem._label_geometry` owns text assembly, Qt metric measurement, elision, and chip placement.
- `PortItem.paint` and `.shape` consume that same result. Hit testing and drawing cannot diverge.
- `boundingRect` remains a constant conservative envelope: Space/hover do not mutate the scene index.
- Default input text follows the existing connected-state behavior; no saved graph schema changes.

## Loop-carried values
- Existing `loop_value` node is reused as a value-version merge, not a new executable node.
- A **single unconditional name assignment or augmented assignment** is the initially qualified recurrence, and only if a pre-loop binding exists.
- `initial` points to the pre-loop value, `next` points to the qualifying body write; `LOOP VALUE` is the value at the start of each iteration.
- The `WHILE TEST` links to this current value as a static *possible read dependency*, not a new eager step, so repeated tests cannot appear frozen at a pre-loop value.
- A post-loop use may link to the value-version merge only when no `break` or `else` gives an alternative exit-path value. All other writes remain conservatively uncertain.
- Control edges still represent program structure; no arbitrary graph-to-Python code generation or loop rewiring has been enabled.

## Known limitations and gates
- Only simple recurrence shape is supported. Complex conditional joins, aliases, exception effects, nested loop carried dependencies, and static type precision need stronger SSA/effect analysis.
- `ast` expression reading is source-oriented and does not imply every syntactically referenced name evaluates on every short-circuited path.
- Headless tests validate graph/port identities and conservative behavior. The Qt file picker and rendered chip shapes require the separate Linux host smoke test.
