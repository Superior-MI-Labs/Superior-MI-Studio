# v2.40: Python-first program construction and function interface migration

## Scope and decisions

Python remains the only qualified source-authoring adapter. v2.39 passed native Qt on WolfCat-Studio (502 headless tests). The next code-authoring capability should be usable on an initially empty Python file, rather than requiring a pre-existing Return/Pass anchor. The three new qualified operation definitions are advertised through the existing Node Library and blank-graph search; pin-drop remains restricted to operations that genuinely consume a proven source pin.

- `python.create-function.v1`: append a module-scope `def name(args): pass` using validated identifiers, no existing-name collision, exact AST preservation of all existing module statements and reviewed diff.
- `python.create-main-entry.v1`: append an explicit `if __name__ == "__main__": print(start())` for a single, zero-argument module function when no previous main guard or print shadow exists. No Python executes during source analysis or proposal generation.
- `python.add-optional-keyword-parameter.v1`: append a primitive-default keyword-only parameter to a single-line, undecorated module function. Local direct-name calls are amended with an explicit matching keyword only if no lexical shadowing, starred arguments, or ambiguous binding exists. Calls outside the analyzed file remain compatible because the parameter has a default. AST structure normalization verifies that only the interface and qualified direct call keywords change.

`File → New Python source file…` creates an empty `.py` via exclusive creation (`xb`); it cannot overwrite an existing file. The original source opening and graph session authority handles its display.

The module presentation now distinguishes qualified module guards as real Branch cards with True/False ports. Unsupported `if` suites remain opaque with no fabricated execution wires. Semantic interfaces still come exclusively from the Python AST parser, not the Qt presentation.

## Verification and known limits

- New regression tests cover program construction from blank file through function Return and module entry, handwritten-vs-generated AST parity, direct/keyword calls, CRLF/Unicode, source-byte preservation, external-edit rejection, lexical name capture, unsupported syntax and effect-safe authoring.
- `scripts/python-first-gate.py` validates bundled examples and constructs a complete small program in a throwaway directory, comparing node/edge projections to the same program written as text. This gate never imports or executes the source.
- Native Qt needs host qualification of the actual empty source graph, new builder buttons, source document ownership, and preview/create controls.
- This is **not** a complete general graph compiler. Arbitrary operation creation, unrestricted control flow rewrites, full Python binding/dominance semantics, automatic cross-file refactoring, generic wired argument constructors, and complete visual editing remain open work.

## Next large patches

1. Complete function Entry/Result editing: parameter removal/reorder, return/interface updates and safe call-site migration with explicit cross-file limitations.
2. General graph connection plans based on producer identity, dominance and effects rather than text expression copying.
3. Build complete Python programs visually with functions, calls, branches, loops and variable writes. Compare source-generated and handwritten graphs, then run user-approved code on the actual host.
4. Consolidate remaining global Qt session state and unify filesystem/source workspaces, preserving isolated camera/history/selection.
5. Run Python language-maturity review across real programs, GUI workflows, source diffs, host runtime behavior, adversarial tests, and round-trip semantic equivalence. **No additional language adapter before this gate and the user-requested features are ready.**
