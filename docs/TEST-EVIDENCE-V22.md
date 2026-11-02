# v2.2 Release Qualification

Build environment: Python 3 (PyQt6 **not available**). This report explicitly separates verified tests from pending GUI-host qualification.

- Baseline copied unmodified from `/mnt/data/Superior-MI-Python-Visual-Programming-Lab-v2.1`; 191/191 headless tests passed.
- After v2.2 changes, `python3 -m unittest discover -s tests -q`: **207/207 passed**.
- `python3 -m compileall -q studio_native tests`: PASS.
- `bash -n ./*.sh`: PASS.
- Bundled code does not execute user Python sources merely by opening a graph. Source changes retain guarded diff/backup behavior.
- `test-qt-offscreen.sh` updated to verify the single visible return dot, normal-completion lane, cross-region return routes, and unchanged scope ownership. **NOT RUN** in this environment: PyQt6 unavailable. Native painting, mouse hit-testing, layout and interaction require host qualification.

## Native host qualification (Linux Mint)

```bash
./doctor.sh
./test-qt-offscreen.sh
./launch-linux.sh
```

Use a disposable copy of `examples/python-v18-boundary-and-layout.py` for editing. Expand `early_exit`, verify the True path reaches its RETURN statement, and verify both its execution exit and returned value terminate at the function boundary. Expand `choose` and check that the outer visible return dot accepts a supported parameter-to-return drag with a reviewed diff. Confirm that the IF composite has True/False, not its own function-return port.

Known limits: nonlocal return exit visualization is not itself an editable semantic flow edge; connecting execution wires to the control facet is not qualified. New conditional/loop syntax lowering, exception propagation and additional language adapters remain future work.
