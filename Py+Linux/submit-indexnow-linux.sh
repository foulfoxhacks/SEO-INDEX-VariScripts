#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
RUNNER="$SCRIPT_DIR/indexnow_runner.py"

if ! command -v python3 >/dev/null 2>&1; then
  printf '%s\n' 'Python 3.9 or newer is required.' >&2
  printf '%s\n' 'Install it with your package manager, for example: sudo apt install python3' >&2
  exit 1
fi

if [ ! -f "$RUNNER" ]; then
  printf 'Missing runner: %s\n' "$RUNNER" >&2
  exit 1
fi

if [ "$#" -eq 0 ]; then
  printf '%s\n\n' 'IndexNow Public Runner for Linux'
  python3 "$RUNNER" --help
  printf '%s\n' 'Example:'
  printf '%s\n' "  ./submit-indexnow-linux.sh --sitemap https://example.com/sitemap.xml --key-location https://example.com/YOUR_KEY.txt --dry-run"
  exit 0
fi

exec python3 "$RUNNER" "$@"
