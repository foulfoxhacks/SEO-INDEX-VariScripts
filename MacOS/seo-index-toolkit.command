#!/bin/zsh
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$SCRIPT_DIR/../Py+Linux/Scripts/seo_index_toolkit.py" "$@"
