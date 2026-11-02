# Verified Studio screenshots

This folder intentionally contains no fabricated UI images. Actual v2.120 Qt screenshots are not available in the repository-ready source snapshot because the review environment lacks PyQt6; the native Linux qualification is pending.

To capture candidate screenshots on a trusted Linux host:

```bash
bash ./RUN-ALL.sh
```

The command prints a qualification report location and stores PNGs such as `qt-smoke.png`, `workspace-navigation.png`, `resource-python-embedded.png`, `program-owned-editor.png` and `independent-graph-tabs.png` inside that report directory. Copy **selected** images here only after the native suite passes, the UI is representative, and each image has been reviewed to remove usernames, absolute machine paths, private code and other identifying information.

Then add the approved images to the README with accurate captions identifying the version and platform. The existing Qt smoke harness is the only screenshot capture path; don't create a second presentation system.
