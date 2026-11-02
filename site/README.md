# Superior MI Studio website

The public showcase is intentionally a static site. `index.html`, `styles.css`, and `main.js` are the only application-facing resources. No package manager, build framework, external fonts, tracking, requests, or client-side router are required. GitHub Pages publishes **this folder only** with `.github/workflows/pages.yml`.

Use `python3 site/check.py` from the repository root to check the local HTML/assets. For a local preview, use `python3 -m http.server --directory site 8080` and open `http://localhost:8080`.

## Data ownership

This site is an **informational presentation**, never the source of truth for the development roadmap, release policy, architecture, or feature qualifications. Link to `../docs/PROJECT-ROADMAP.md`, `../docs/RELEASE-PIPELINE.md`, `../CONTRIBUTING.md`, and `../SUPPORT.md`; update site copy only after those authoritative sources change.

Website screenshots come from the v2.120 Linux Qt native smoke harness and have only had personal paths concealed. The source screenshots remain in privately held qualification evidence; publication-ready optimized copies live in `assets/`. Do not put unredacted machine paths or diagnostic archives into the public repository. Do not use concept renders as software screenshots.

Future site changes should keep accessible navigation, reduced-motion behavior, responsive widths, and small payloads. Avoid dependencies without a demonstrated need. Wiki content, when added, should point back to canonical architecture and task documentation, rather than becoming a conflicting project roadmap.
