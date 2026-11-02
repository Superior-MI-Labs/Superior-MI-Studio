# v2.75 — Execution-ordered function calls and language-extensible workbench direction

## Source and qualification

Baseline: v2.74 qualified on WolfCat-Studio in `qualification-20261101-184557-16689.tar.gz` (882 headless tests and all four independent native Qt stages passed). v2.75 headless / release evidence belongs to its own test logs; native Qt is NOT qualified until a fresh WolfCat-Studio report.

## Implemented: explicit ordered calls

- `ProgramGraph` remains the sole mutable graph authority. `python.call_exec` is the graph-owned template with fixed `exec` and `then` control pins, dynamic typed parameter inputs and a typed `result` output. The existing Qt creator asks for a verified in-document callee and derives ports from its current signature. It cannot use a parameter named `exec` because that conflicts with the execution pin.
- `python_lowering` remains the only Python semantic/lowering owner. It validates the call's exact signature and return type, non-recursive call graph, connected execution path, argument dependencies, and dataflow availability. Source emission happens at the execution point, not as an optimizable pure producer. The output is mapped to the call graph node exactly once.
- Earlier pure `python.call` still refuses a direct or transitive effectful callee; speculative effect evaluation is never permitted. An incomplete graph is safe to save, but cannot publish Python.
- Ordered calls can appear in a structured Branch or bounded Repeat body, observing path selection and zero-iteration behavior. No arbitrary control joins, general exceptions, async operations, external impure libraries or recursive graphs are admitted.
- Publication is still opt-in through existing `publish_python` and its guarded source writer. No automatic execution, no parallel source model, no new interpreter.

## Architecture review: VS Code workbench, Unreal Blueprint programming

VS Code is the reference for a modular IDE *workbench*, not something to copy wholesale. Unreal Blueprint remains the primary node authoring and gesture reference.

| Existing owner | Preserved responsibility | Later extension boundary (not implemented) |
|---|---|---|
| `SourceDocumentSession`, `ProgramGraph` | One editable revision and guarded persistence per document | Immutable document snapshots and revision-safe commands |
| `GraphDescriptor`, `GraphCanvas`, `NativeLab` | Presentation, navigation, workbench tabs, views, docking | View contributions/commands; no extension-owned graph state |
| `python_graph`, `python_authoring`, `python_lowering` | Python parsing, qualified edits, AST lowering and diagnostics | Language-specific capability implementations with stable versioned inputs |
| Current guarded writer / explicit Run UI | File writes, opt-in process execution | Tasks/test providers; require workspace trust and explicit user action |
| Existing Qt test stages | Real host interaction qualification | Separate fixtures for extension isolation, diagnostics and lifecycle |

**Reference mechanisms to study, not duplicate prematurely:**

- [VS Code language extension architecture](https://code.visualstudio.com/api/language-extensions/overview): language-specific features are contributed rather than hardwired into the workbench.
- [Language Server Protocol guide](https://code.visualstudio.com/api/language-extensions/language-server-extension-guide): language intelligence runs behind a client/server boundary with document synchronization and diagnostics.
- [VS Code contribution points](https://code.visualstudio.com/api/references/contribution-points): declarative commands, menus, views, keybindings and language/tool contributions.
- [VS Code Debug Adapter Protocol guide](https://code.visualstudio.com/api/extension-guides/debugger-extension): debugging UI delegates to independently integrated debugger backends.
- [Workspace Trust](https://code.visualstudio.com/api/extension-guides/workspace-trust): never automatically execute code found in an untrusted workspace.

### Decisions and alternatives

1. **Extend current interpreter-independent `ProgramGraph` persistence + existing Python lowering (chosen)** vs. creating a separate effect-call engine (rejected): one validated authority and consistent undo/save behavior.
2. **One workbench with future language-specific capabilities (chosen)** vs. generalizing all `py:*` types and Python AST rules now (rejected): no second language implementation yet, no evidence to justify a universal compiler or plugin host.
3. **Keep pure Call distinct from execution Call (chosen)** vs. marking all calls effectful (rejected): accurately represents dataflow vs. control flow and preserves qualified pure composition.

## Next architecture gates

1. Host-qualify the new Qt creator and publication path. Trace and fix root causes, never change pass criteria to accommodate failures.
2. Continue bounded While/For/control joins with path-sensitive state and termination diagnostics. Maintain existing Python type/effect contract.
3. Prototype source-to-graph reconciliation on isolated revisioned documents; refuse unsupported Python, never invent dual authority.
4. Consolidate contextual command search, function/variable browsing, diagnostics and workbench UX before writing a plugin host.
5. After a credible Python text/graph vertical slice and native usability review, evaluate a minimal second language adapter against stable document, graph, diagnostic and artifact contracts.
