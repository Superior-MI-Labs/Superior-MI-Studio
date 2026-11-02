#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
case "${1:---headless}" in
  --headless) mode="--headless" ;;
  --native) mode="" ;;
  --help|-h) echo "Usage: bash scripts/agent-verify.sh [--headless|--native]"; exit 0 ;;
  *) echo "Unknown option: $1" >&2; exit 2 ;;
esac
python3 scripts/check_agent_setup.py
# Keep logs within ignored repository-local artifacts unless caller explicitly chooses another location.
export SMI_LOG_DIR="${SMI_LOG_DIR:-$ROOT/.agent-artifacts/qualification}"
mkdir -p -- "$SMI_LOG_DIR"
if [[ -n "$mode" ]]; then
  bash ./RUN-ALL.sh "$mode"
else
  bash ./RUN-ALL.sh
fi
