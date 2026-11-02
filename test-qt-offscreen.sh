#!/usr/bin/env bash
# One interpreter selection authority: run the supported launcher.
# Each interactive fixture has an independent process and a required PASS marker.
set -uo pipefail
APP="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)" || exit 1
if [[ -z "${SMI_RECOVERY_DIR:-}" ]]; then
  test_recovery_dir="$(mktemp -d)" || exit 1
  export SMI_RECOVERY_DIR="$test_recovery_dir"
fi
stage_log="$(mktemp)" || exit 1
cleanup() {
  rm -f -- "$stage_log"
  if [[ -n "${test_recovery_dir:-}" ]]; then rm -rf -- "$test_recovery_dir"; fi
}
trap cleanup EXIT

run_stage() {
  local label="$1" marker="$2" deadline="$3" status
  shift 3
  printf 'QT_STAGE %s\n' "$label"
  : > "$stage_log"
  # Write subprocess output directly to a file. Piping through tee could
  # retain a live reader after the timed-out parent exits when a Qt descendant
  # keeps stdout open. A stage's deadline must bound the supervisor itself.
  timeout --signal=TERM --kill-after=4s "$deadline" "$@" > "$stage_log" 2>&1
  status=$?
  cat "$stage_log"
  if (( status != 0 )); then
    printf 'QT_STAGE_FAILED %s exit=%s\n' "$label" "$status" >&2
    return "$status"
  fi
  if ! grep -Fxq "$marker" "$stage_log"; then
    printf 'QT_STAGE_FAILED %s missing=%s\n' "$label" "$marker" >&2
    return 1
  fi
}

# No recovery, document or integration test may depend on the previous Qt
# application, event loop, tab registry or modal dialog state.
run_stage recovery-subprocess NATIVE_QT_RECOVERY_PASS 25s \
  env SMI_QT_RECOVERY_ONLY=1 bash "$APP/launch-linux.sh" --qt-smoke || exit $?
run_stage document-subprocess NATIVE_QT_DOCUMENT_PASS 35s \
  env SMI_QT_DOCUMENT_ONLY=1 bash "$APP/launch-linux.sh" --qt-smoke || exit $?
run_stage program-subprocess NATIVE_QT_PROGRAM_PASS 35s \
  env SMI_QT_PROGRAM_ONLY=1 bash "$APP/launch-linux.sh" --qt-smoke || exit $?
run_stage integration-subprocess NATIVE_QT_SMOKE_PASS 75s \
  bash "$APP/launch-linux.sh" --qt-smoke "${1:-$HOME/Downloads/SMI-Native-NodeLab-Smoke.png}" || exit $?
