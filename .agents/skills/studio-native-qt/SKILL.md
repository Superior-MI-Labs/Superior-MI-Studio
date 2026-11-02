---
name: studio-native-qt
description: Qualify or investigate Superior MI Studio's real Linux Qt rendering, node gestures, modal workflows, tab routes, minimap and interaction hangs. Use for PyQt6 UI regressions and release qualification.
---

# Native Qt qualification

1. Inspect `RUN-ALL.sh`, `test-qt-offscreen.sh`, `studio_native/qt_smoke.py` and relevant `docs/V251-INTERACTION-AND-HANG-QUALIFICATION.md` and `docs/V252-FUNCTION-CALL-AUTHORING-CONTRACT.md`.
2. Run `bash scripts/agent-verify.sh --headless` first. A clean headless run is necessary but insufficient for native UI work.
3. On a Linux host where PyQt6 is installed, run `bash scripts/agent-verify.sh --native`. It runs the project's bounded offscreen Qt interaction smoke, no interactive launch. Preserve stage markers, raw tracebacks, screenshots and report location.
4. For failures, identify the **last completed QT_STAGE**, signal-slot callback exceptions, modal supervision, compositor/offscreen platform and actual stack. Never classify timeout or interrupted process as PASS.
5. Add the smallest reproducible failing Qt stage and host event test before changing the implementation. Avoid timers that assume modal widgets are already visible; use the existing supervised pattern.
6. Verify the changed workflow both by focused native stage and the full native check. Return the complete report path, host/PyQt6 versions, passed/skipped tests and a real failure signature when broken.
7. If PyQt6 unavailable, report NATIVE NOT RUN and request host evidence; do not substitute a headless assertion for actual mouse/paint/drag evidence.
