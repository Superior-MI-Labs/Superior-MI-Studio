# v2.44: Blueprint Interaction Alignment (research and first corrections)

## Evidence and scope

The v2.43 host qualification on WolfCat-Studio (2026-10-29) passed 551 headless tests and printed `NATIVE_QT_SMOKE_PASS` without application tracebacks. The Qt log still contains Qt's harmless `propagateSizeHints()` warnings. The graphical screenshots demonstrate a usability gap: the Python source graph opens with the unrelated Draft templates selected in Node Library, and whole-file graphs can be so zoomed out that operations are unreadable. This does not establish that all native gestures are usable.

Primary interaction reference, Epic Unreal Engine documentation (accessed 2026-10-29):

- https://dev.epicgames.com/documentation/unreal-engine/blueprint-editor-cheat-sheet-in-unreal-engine
- https://dev.epicgames.com/documentation/unreal-engine/placing-nodes-in-unreal-engine
- https://dev.epicgames.com/documentation/unreal-engine/nodes-in-unreal-engine
- https://dev.epicgames.com/documentation/unreal-engine/connecting-nodes-in-unreal-engine
- https://dev.epicgames.com/documentation/en-us/unreal-engine/my-blueprint-panel-in-the-blueprints-visual-scripting-editor-for-unreal-engine
- https://dev.epicgames.com/documentation/unreal-engine/functions-in-unreal-engine
- https://dev.epicgames.com/documentation/en-us/unreal-engine/collapsing-graphs-in-unreal-engine
- https://dev.epicgames.com/documentation/unreal-engine/blueprint-debugging-example-in-unreal-engine

### Interaction conventions to align

| Blueprint convention | Existing Studio owner / status | Intended next gate |
|---|---|---|
| Graph context search, pin-drag contextual creation | `authoring_actions.py`, `GraphCanvas.open_creation_menu`, existing verified lowering; limited Python subset | Make prominent and keyboard accessible; never show unsupported creators |
| My Blueprint panel: functions, variables, graphs | Node Library currently has Draft and Source modes; Source has observed operations and builders | Context switches to Source when Python graph active; later expose scoped function/variable discovery from parser, not a second symbol database |
| Exec flow white, typed data pins differentiated | `semantic_contract.py`, `python_graph.py`, shared renderer | Preserve unknown effects/typing; don't pretend all Python calls are pure |
| Function Entry, Return, call sites distinct | Already separated in source graph; subset of creation exists | Qualify signature/call-site edits and actual round trip before allowing arbitrary rewiring |
| Branch/loops operations, not nested scopes | Existing migration v2.31 | Preserve Python `for/else`, exception, `break`, `continue` differences |
| Selection / navigation / panning / frame | Shared graph camera, source tabs, mini-map, current left/middle pan | Home frames selected/visible; investigate right-drag pan/left marquee with native event tests before changing current gestures |
| Collapse graph / function / macro have different semantics | Explicit source function regions; no arbitrary source-backed macro system | Do not fake organizational collapsed graphs as executable Python constructs |
| Comment boxes, reroute points, bookmarks | Not a semantic capability yet | Design as presentation-only layer, not generated Python statements |
| Node debugger with breakpoints, watches, exec trace | Not qualified | Defer to IDE debugging/language adapter; do not execute source just to draw graph |

## Decisions

Two implementation approaches considered:

A. Rewrite Qt interactions to clone Unreal in one patch. Rejected: platform-specific event order (right-click menu vs right-drag pan), nested graph ownership and source-edit preflight make this a regression risk. This would make UI event handlers the authority for language semantics.

B. Change the existing presentation surfaces incrementally and use their existing routing and action authorities. Chosen: source graph selects the Source operations tab automatically; graph Home frames selected node or visible nodes; Tab brings up the existing adapter-filtered creation search only for qualified Python views. No additional registry, parser, compiler, or source writer.

## Native qualification and follow-ups

Qt smoke now asserts the relevant Node Library tab for unloaded source, resource and active saved Python views. The adapter must refuse unsupported pins and contexts unchanged. The full headless suite and Python-first program gate remain required. Native keyboard interactions require human Linux host testing; the screenshot smoke alone does not prove ergonomic quality.

Before another broad programming feature: (1) observe Tab search and Home framing; (2) test click vs drag behavior at each graph depth; (3) establish explicit compatibility matrix for right-pan and left-marquee before changing drag gestures; (4) prototype typed function/variable discovery in existing Source mode; (5) test a complete text/visual authoring journey with an unfamiliar user. Record failures, not only pass counts.
