# v2.5 Release Qualification

Build: `Superior-MI-Python-Visual-Programming-Lab-v2.5`

- 246 headless `unittest` tests passed; zero failures.
- `python3 -m compileall -q studio_native` passed.
- Linux shell scripts passed `bash -n`.
- Bundled Python examples and source projection checks passed through `doctor.sh`.
- Native Qt GUI smoke test was **not executed** here because PyQt6 is unavailable in this container. Use `./test-qt-offscreen.sh` on the Linux Mint host.
- UI state is a separate user config file. No source files or existing installations are modified when browsing or storing presentation preferences.
- External icon atlas remains optional and is not bundled.
- Known limitations: manual positions track the current stable node identity; advanced cross-region obstacle-aware wire routing and semantic identity migration are not implemented.
