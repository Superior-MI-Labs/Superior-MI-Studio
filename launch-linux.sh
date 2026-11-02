#!/usr/bin/env bash
# Always execute this launcher, never source it into an interactive shell.
# A failing Python/Qt process produces a persistent log instead of replacing
# the terminal process with exec.
set -uo pipefail
APP="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)" || exit 1
cd "$APP" || exit 1

usage() {
  printf '%s\n' 'Usage: ./launch-linux.sh [--test | --qt-smoke [screenshot.png] | --help]' \
    '  default: launch the interactive Qt editor and retain a failure log' \
    '  --test: run headless unit tests' \
    '  --qt-smoke: exercise the real Qt renderer offscreen'
}

case "${1:-}" in
  --help|-h) usage; exit 0 ;;
  --test)
    shift
    python3 -m unittest discover -s tests -v "$@"
    exit $? ;;
  ''|--qt-smoke) ;;
  *) usage >&2; exit 2 ;;
esac

# Debian/Mint's python3-pyqt6 belongs to /usr/bin/python3; virtualenvs may
# use another interpreter. Only choose one after testing that very interpreter.
QT_PYTHON=''
for candidate in /usr/bin/python3 python3; do
  if "$candidate" -c 'from PyQt6 import QtWidgets' >/dev/null 2>&1; then
    QT_PYTHON="$candidate"
    break
  fi
done
if [[ -z "$QT_PYTHON" ]]; then
  printf '%s\n' 'ERROR: PyQt6 is not available to either Python interpreter.' \
    'Install on Linux Mint: sudo apt update && sudo apt install python3-pyqt6' \
    'Then rerun ./RUN-ALL.sh or ./launch-linux.sh.' >&2
  exit 3
fi

if [[ "${1:-}" == '--qt-smoke' ]]; then
  shift
  SCREENSHOT="${1:-$HOME/Downloads/SMI-Native-NodeLab-Smoke.png}"
  QT_QPA_PLATFORM=offscreen "$QT_PYTHON" -m studio_native.qt_smoke "$SCREENSHOT"
  exit $?
fi

LOG_DIR="${SMI_LOG_DIR:-$HOME/Downloads/SMI-NodeLab-Logs}"
if ! mkdir -p -- "$LOG_DIR"; then
  printf 'ERROR: Cannot create diagnostic directory: %s\n' "$LOG_DIR" >&2
  exit 4
fi
LOG="$LOG_DIR/launch-$(date +%Y%m%d-%H%M%S)-$$.log"
printf 'Launching with %s\nCrash/output log: %s\n' "$QT_PYTHON" "$LOG"
# No exec and no inherited errexit. Qt may abort with a signal; preserve
# its status AND full traceback while keeping a terminal-launched parent alive.
"$QT_PYTHON" -m studio_native 2>&1 | tee "$LOG"
status=${PIPESTATUS[0]}
if (( status != 0 )); then
  printf '\nERROR: Qt editor exited with status %s. Log: %s\n' "$status" "$LOG" >&2
  printf '%s\n' 'If launched from a desktop shortcut, open this log in a terminal or text editor.' >&2
fi
exit "$status"
