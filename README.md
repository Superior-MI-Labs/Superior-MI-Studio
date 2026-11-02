# Superior MI Studio

**An experimental visual + text IDE for building and understanding software systems.**

Superior MI Studio is an early-stage research and development project by [Superior MI Labs](https://github.com/Superior-MI-Labs). We are developing one workbench where source code, executable node graphs, project files, and relationships between resources can be explored together.

Our two main design references are **Visual Studio Code** (workspace navigation, editing, tools, extensibility) and **Unreal Engine Blueprints** (typed data/flow connections and visual programming interactions). Studio is its own implementation; it is not affiliated with either project.

> **Development status: pre-alpha, v2.120 source candidate.** This is not a finished general-purpose IDE. Python is the first language adapter. The latest documented native-Linux qualified baseline is v2.115; v2.120 passed headless verification but still requires native Qt qualification before promotion. There is no stable product release yet.

## What you can explore today

- A Qt/PyQt6-based desktop workbench with source editor, graph canvas, navigation, tabs, dock panels, minimap and inspector.
- Python **source-to-graph visualization** alongside a native editable `ProgramGraph` for a deliberately limited set of typed operations and structured control flow.
- Verified **graph-to-Python generation** and explicitly reviewed, conservative Python-to-existing-graph reconciliation. Unsupported Python remains source-owned; it is **not** a general arbitrary-Python importer.
- Unified resource presentations, previews for supported assets and evidence-backed relationships between project files.
- Versioned editing, atomic reconciliation, undo/redo, explicit diagnostics, conflict refusal and source-preservation tests.
- Automated headless regressions and native Qt offscreen interaction checks.

The biggest current engineering effort is **architecture consolidation**: eliminating duplicate state, making document and graph ownership unambiguous, and proving that visual editing and source editing cannot silently overwrite each other.

## Interface screenshots

We only publish **actual, reviewed native application captures**, not concept art presented as software screenshots. The current source includes a Qt smoke harness that captures views such as the workbench, embedded Python graphs, function authoring, minimap, resources and navigation. See [screenshot instructions](docs/screenshots/README.md). Approved screenshots will appear here after native v2.120 qualification and privacy review.

## Run locally (Linux / Linux Mint)

Requires Python 3 and PyQt6. On Debian/Ubuntu/Mint, for example:

```bash
sudo apt update && sudo apt install python3-pyqt6
bash ./RUN-ALL.sh --headless   # semantic/unit verification
bash ./RUN-ALL.sh              # headless + native Qt offscreen verification
bash ./launch-linux.sh        # interactive app; explicit launch
```

`RUN-ALL.sh` writes diagnostic logs and a compressed qualification report. It does **not** silently install or replace existing versions. The existing Linux installer (`install_linux.py`) enforces its own versioned archive and native qualification rules. Windows launch support exists in the tree, but parity and release qualification have not been established here; do not assume stable Windows support.

For developers and AI coding agents, start with [AGENTS.md](AGENTS.md), [CODEX-START-HERE.md](CODEX-START-HERE.md), and the [active task queue](docs/agents/NEXT-TASKS.md). Architectural decisions are in [docs/architecture](docs/architecture).

## Where we are going

1. **Reliability first:** qualify the latest native build, consolidate compiler proof and diagnostics, remove legacy duplicate navigation paths only after regression gates pass.
2. **Python authoring maturity:** improve graph/source correspondence, control flow, function calling, source conflict reporting, safe save/build/run behaviors and debugging hooks.
3. **IDE platform:** define stable language adapters, file-type capabilities, tooling/task APIs, project services and extension contracts. No parallel per-language IDEs.
4. **Professional development workflow:** integrated linting, compilers/interpreters, test runners, diagnostics, debugging, dependency inspection, packages, tasks and build pipelines.
5. **Distribution:** tested cross-platform packaging, release channels, extension discovery and a maintainable contributor ecosystem.

These are **goals, not shipping features**. See the [roadmap](docs/PROJECT-ROADMAP.md) and [production / release pipeline](docs/RELEASE-PIPELINE.md).

## Help build Studio

We welcome people who can review Python semantics, Qt interaction bugs, graph compilers, source mapping, test coverage, UI/UX, performance, documentation, accessibility and packaging. Especially valuable: people who can reproduce a problem, propose the smallest correct architectural fix, and add a regression test.

Start with [CONTRIBUTING.md](CONTRIBUTING.md) and the [active engineering queue](docs/agents/NEXT-TASKS.md). Please read the ownership and qualification rules before submitting structural changes.

## Support the project or offer paid work

Studio is a small independent R&D effort seeking **contributors, potential maintainers/community moderators, equipment and financial support, and paid software-development contracts or side gigs** that could help fund continued development. Relevant paid work may include Python development, developer tools, AI integrations, automation and custom applications.

For sponsorship, hardware contributions, contract work, or collaboration proposals, email **superior.mi.labs@gmail.com** or open a GitHub issue for technical collaboration. **No payment processor or crowdfunding campaign is implied or endorsed by this README.** See [SUPPORT.md](SUPPORT.md).

## Responsible development

Our priorities are source preservation, explicit user consent for execution, stable document ownership, tested migration, diagnostics and reproducible release evidence. GUI success is not inferred from unit tests alone. See [release gates](docs/RELEASE-PIPELINE.md) and [security reporting](SECURITY.md).

**License:** A public source repository does not, by itself, grant reuse or redistribution rights. A software license for Studio must be selected and published explicitly before external code contributions are merged. Issue reports, documentation suggestions and design discussion are welcome in the meantime.