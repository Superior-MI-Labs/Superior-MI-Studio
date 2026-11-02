#!/usr/bin/env bash
# Native Linux qualification. Diagnostic logs survive a nonzero exit.
# No set -e: do not allow a failing smoke test to hide the final report.
set -uo pipefail
APP="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)" || exit 1
usage() {
  printf '%s\n' 'Usage: ./RUN-ALL.sh [--launch | --headless | --help]' \
    '  default: headless tests + native Qt offscreen smoke, no interactive launch' \
    '  --launch: open the editor only after both checks pass' \
    '  --headless: run headless doctor only (useful without PyQt6)'
}
case "${1:-}" in
  --help|-h) usage; exit 0 ;;
  ''|--launch|--headless) mode="${1:-}" ;;
  *) usage >&2; exit 2 ;;
esac
ROOT="${SMI_LOG_DIR:-$HOME/Downloads/SMI-NodeLab-Logs}"
REPORT="$ROOT/qualification-$(date +%Y%m%d-%H%M%S)-$$"
if ! mkdir -p -- "$REPORT"; then
  printf 'ERROR: Unable to create report: %s\n' "$REPORT" >&2
  exit 4
fi
printf 'Report directory: %s\n' "$REPORT"
printf '%s\n' 'Running Python doctor and headless regressions...'
# Bound a stalled doctor just as we already bound the native Qt smoke. A
# timeout is a FAILED qualification, never evidence of a passing release.
# SMI_DOCTOR_TIMEOUT may be increased for unusually slow developer machines.
doctor_timeout="${SMI_DOCTOR_TIMEOUT:-240}"
( cd "$APP" && timeout --signal=TERM --kill-after=5s "$doctor_timeout" bash ./doctor.sh ) >"$REPORT/doctor.log" 2>&1
doctor_status=$?
if (( doctor_status == 124 || doctor_status == 137 )); then
  printf 'DOCTOR: TIMEOUT after configured limit (%s seconds). Last doctor output follows.\n' "$doctor_timeout"
fi
if (( doctor_status == 0 )); then
  printf '%s\n' 'DOCTOR: PASS'
else
  printf 'DOCTOR: FAIL (%s), last output:\n' "$doctor_status"
  tail -n 25 "$REPORT/doctor.log"
fi
qt_status=0
if [[ "$mode" != '--headless' ]]; then
  printf '%s\n' 'Running native Qt offscreen smoke (real rendering and event tests)...'
  qt_timeout="${SMI_QT_SMOKE_TIMEOUT:-185}"
  ( cd "$APP" && SMI_QT_PROGRAM_SCREENSHOT="$REPORT/program-owned-editor.png" SMI_QT_VARIABLE_AUTHORING_SCREENSHOT="$REPORT/variable-authoring.png" SMI_QT_COMPOSED_DATAFLOW_SCREENSHOT="$REPORT/composable-dataflow.png" SMI_QT_STORED_CALL_SCREENSHOT="$REPORT/stored-call-connection.png" SMI_QT_EXPRESSION_WIRING_SCREENSHOT="$REPORT/expression-keyword-wiring.png" SMI_QT_CONNECTION_PREVIEW_SCREENSHOT="$REPORT/source-connection-preview.png" SMI_QT_CREATION_CALL_SCREENSHOT="$REPORT/qualified-function-call.png" SMI_QT_CALL_CHAIN_SCREENSHOT="$REPORT/module-nested-calls.png" SMI_QT_RESOURCE_PYTHON_SCREENSHOT="$REPORT/resource-python-embedded.png" SMI_QT_SYMBOL_BROWSER_SCREENSHOT="$REPORT/python-symbol-browser.png" SMI_QT_CATALOG_SCREENSHOT="$REPORT/operation-catalog.png" SMI_QT_UNIVERSAL_TAB_SCREENSHOT="$REPORT/universal-tab-navigation.png" SMI_QT_TAB_SCREENSHOT="$REPORT/independent-graph-tabs.png" SMI_QT_OVERVIEW_SCREENSHOT="$REPORT/graph-overview.png" SMI_QT_DOCK_SCREENSHOT="$REPORT/dock-collapsed.png" SMI_QT_WORKSPACE_SCREENSHOT="$REPORT/workspace-navigation.png" SMI_QT_NAV_SCREENSHOT="$REPORT/breadcrumb-navigation.png" SMI_QT_DRAFT_SCREENSHOT="$REPORT/draft-transaction.png" SMI_QT_FOCUSED_REGION_SCREENSHOT="$REPORT/focused-region.png" SMI_QT_NESTED_SCREENSHOT="$REPORT/nested-boundary.png" SMI_QT_RETURN_SCREENSHOT="$REPORT/return-boundary.png" SMI_QT_EARLY_EXIT_SCREENSHOT="$REPORT/early-exit.png" timeout --signal=TERM --kill-after=5s "$qt_timeout" bash ./test-qt-offscreen.sh "$REPORT/qt-smoke.png" ) 2>&1 | tee "$REPORT/qt.log" | awk '/^QT_STAGE / { print "  " $0; fflush(); }'
  qt_status=${PIPESTATUS[0]}
  # Some PyQt6 signal-slot failures are printed to stderr without causing a
  # nonzero process exit. Fail closed even if the smoke prints its PASS marker.
  if grep -Eq '^Traceback \(most recent call last\):|^Exception in Qt callback:' "$REPORT/qt.log"; then
    qt_status=1
    printf '%s\n' 'QT: Uncaught Python callback traceback detected; see qt.log'
  fi
  if (( qt_status == 124 || qt_status == 137 )); then
    printf 'QT: TIMEOUT after configured smoke limit (%s). Last completed QT_STAGE is in qt.log\n' "$qt_timeout"
  fi
  if (( qt_status == 0 )); then
    printf 'QT: PASS, screenshots: %s, nested-boundary.png, focused-region.png, return-boundary.png, early-exit.png, draft-transaction.png, workspace-navigation.png, breadcrumb-navigation.png, dock-collapsed.png, graph-overview.png, independent-graph-tabs.png, universal-tab-navigation.png, python-symbol-browser.png, variable-authoring.png, operation-catalog.png, module-nested-calls.png, qualified-function-call.png, source-connection-preview.png, expression-keyword-wiring.png, stored-call-connection.png, composable-dataflow.png\n' "$REPORT/qt-smoke.png"
  else
    printf 'QT: FAIL (%s), last output:\n' "$qt_status"
    tail -n 25 "$REPORT/qt.log"
  fi
else
  printf '%s\n' 'QT: SKIPPED by --headless (not a native GUI qualification)'
fi
# Durable, machine-readable verdict is written before archive creation. A
# process supervisor that loses the terminal pipe can still inspect the report
# without inferring success from the last printed unittest line. This file is
# evidence only; the process exit code remains authoritative for installation.
if (( doctor_status == 0 && qt_status == 0 )); then
  verdict="CHECKS_PASS"
else
  verdict="CHECKS_FAILED_OR_UNAVAILABLE_REVIEW_REQUIRED"
fi
printf 'doctor_status=%s\nqt_status=%s\nmode=%s\nverdict=%s\n' \
  "$doctor_status" "$qt_status" "${mode:---native}" "$verdict" > "$REPORT/qualification-verdict.txt"
# A single portable report is easier to submit than a directory of logs.
# Always produce it, including when checks fail or PyQt6 is unavailable.
ARCHIVE="${REPORT}.tar.gz"
if tar -czf "$ARCHIVE" -C "$ROOT" "$(basename "$REPORT")"; then
  printf 'Uploadable report: %s\n' "$ARCHIVE"
else
  printf 'WARNING: Report archive failed; plain logs remain at: %s\n' "$REPORT" >&2
fi
if (( doctor_status != 0 || qt_status != 0 )); then
  printf '\nCHECKS_FAILED_OR_UNAVAILABLE_REVIEW_REQUIRED\nRaw report logs: %s\n' "$REPORT"
  exit 1
fi
printf '\nCHECKS_PASS\nLogs and screenshots: %s\n' "$REPORT"
if [[ "$mode" == '--launch' ]]; then
  bash "$APP/launch-linux.sh"
  exit $?
fi
exit 0
