# Integration validation — v2.52 baseline

- Input: user-provided `Superior-MI-Python-Visual-Programming-Lab-v2.52.zip`; 216 original ZIP entries; original implementation modules remain byte-for-byte unchanged in the Codex package.
- Local full headless qualification: `bash scripts/agent-verify.sh --headless` **PASS**. `621` Python unittest cases, `OK` (3.966 s in one packaging run); `PYTHON_FIRST_GATE_PASS` and projection checks.
- Handoff structure: `python3 scripts/check_agent_setup.py` **PASS**; `python3 scripts/repo_inventory.py` **PASS**; skill front matter and role TOML parsed.
- Native Qt: **NOT RUN** (PyQt6 unavailable on packaging machine). v2.52 host qualification remains to be performed on the user's Linux setup.
- Codex CLI: **NOT RUN** (Codex binary not available in this packaging environment). Agent discovery/configuration must be smoke-tested after installing/extracting on the user's machine.
- No production `studio_native/` source or original tests changed, and no external agent add-ons installed. Added guidance, scripts and a headless-only CI workflow.
- The architecture decision package is a future-design specification; v3.1 acceptance matrix entries describe *required future tests*, not 88 implemented tests.
