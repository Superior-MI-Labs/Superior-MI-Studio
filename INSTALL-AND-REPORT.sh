#!/usr/bin/env bash
# Superior MI Studio v2.124: install, qualify, collect logs, then launch on native PASS.
set -uo pipefail
VERSION=v2.125
NAME=Superior-MI-Python-Visual-Programming-Lab
ZIP="$HOME/Downloads/$NAME-$VERSION.zip"
if [[ ! -f "$ZIP" ]]; then
    echo "Missing ZIP: $ZIP" >&2
    exit 2
fi
INSTALLER="$(mktemp)" || exit 2
REPORT_MARKER="$(mktemp)" || { rm -f "$INSTALLER"; exit 2; }
trap 'rm -f "$INSTALLER" "$REPORT_MARKER"' EXIT
if ! unzip -p "$ZIP" "$NAME-$VERSION/install_linux.py" > "$INSTALLER"; then
    echo "Unable to extract release installer." >&2
    exit 2
fi
python3 "$INSTALLER" "$ZIP" --no-launch
STATUS=$?
LOGDIR="$HOME/Downloads/SMI-NodeLab-Logs"
if [[ -d "$LOGDIR" ]]; then
    REPORT="$(find "$LOGDIR" -maxdepth 1 -type f -name 'qualification-*.tar.gz' -newer "$REPORT_MARKER" -printf '%T@ %p\n' | sort -nr | head -1 | cut -d' ' -f2-)"
    if [[ -n "$REPORT" ]]; then
        DEST="$HOME/Downloads/SMI-NodeLab-Extracted/$(basename "$REPORT" .tar.gz)"
        mkdir -p "$DEST"
        if tar -xzf "$REPORT" -C "$DEST"; then
            echo "Uploadable report: $REPORT"
            echo "Extracted files: $DEST"
        else
            echo "Could not extract report; original archive preserved: $REPORT" >&2
        fi
    else
        echo "No qualification archive produced by this installation; older reports were not relabeled as new." >&2
    fi
fi
if (( STATUS != 0 )); then
    printf '%s\n' 'Native qualification failed: Studio will not be launched. Reports and older installs preserved.' >&2
    exit "$STATUS"
fi

# The installer performed the native qualification and safe cleanup. Only
# after reports have been surfaced do we open the verified interactive app.
# Running the existing launcher (not another Qt runner) retains crash logs.
APP="$HOME/Projects/$NAME-$VERSION"
if [[ ! -f "$APP/launch-linux.sh" ]]; then
    echo "Qualified app launcher missing: $APP/launch-linux.sh" >&2
    exit 4
fi
printf '%s\n' "Native qualification passed. Opening Superior MI Studio $VERSION..."
bash "$APP/launch-linux.sh"
exit $?
