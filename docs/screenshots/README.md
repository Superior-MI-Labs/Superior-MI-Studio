# Studio README screenshots

**Purpose:** Show visitors what the current running Studio application actually looks like. Screenshot publishing is a presentation task, not a second rendering or testing system.

## Capture from the existing native qualification

On Linux Mint / Ubuntu / Debian, run from the project root:

```bash
bash ./RUN-ALL.sh
```

The default qualification log directory is `~/Downloads/SMI-NodeLab-Logs/`. `RUN-ALL.sh` prints the exact path of the report and its uploadable `.tar.gz`. It captures real Qt widgets to PNGs during the offscreen native smoke test, including:

- `workspace-navigation.png`: candidate for the **large README hero** (overall workbench).
- `program-owned-editor.png` and `resource-python-embedded.png`: source/graph and embedded Python demonstrations.
- `universal-tab-navigation.png`, `independent-graph-tabs.png`, `graph-overview.png`: workspace navigation and graph viewpoints.

These names describe test captures; inspect the actual image before choosing it. If an offscreen image is cluttered or uses artificial smoke-test content, take a **real interactive screenshot** on the same qualified build for a better public presentation. Never composite independent UI states into a fake single screen.

## Promotion checklist

1. Confirm `qualification-verdict.txt` reports passing headless and native stages; a skipped or timed-out Qt run is not success.
2. Select **one** hero screenshot and **two** supporting captures. Prefer a wide, legible composition with visible real code and graph structure.
3. Ensure filenames, paths, private code, test data, user information, credentials, and desktop notifications are absent or redacted. Capture from a clean sample workspace when possible.
4. Crop dead space, keep the same theme and consistent zoom, and optimize PNG losslessly. Keep enough resolution for readable text; avoid huge GIFs.
5. Save approved assets under `docs/screenshots/` and caption each with the **Studio version, OS, and what is genuinely shown**.
6. Only then add Markdown image links to the top of `README.md`, e.g. `![Studio workbench, v2.120 on Linux](docs/screenshots/studio-workbench-v2.120.png)`. Confirm the image renders on GitHub.
7. Replace images as UI changes materially, or explicitly label them historical. Never represent concept artwork as an application screenshot.

Optional: a brief **real screen recording** demonstrating one qualified operation may be included as an optimized GIF or linked video after the same privacy and accuracy review. The static screenshots remain essential for fast-loading README previews.

If sending captures to another maintainer for publication, send the full qualification report archive as well, so its screenshots can be checked against the build evidence.

**Implementation boundary:** Use the existing `studio_native/qt_smoke.py` and `RUN-ALL.sh` capture path. Do not add another screenshot renderer, fake a visual result, or weaken CI qualification to obtain marketing images.
