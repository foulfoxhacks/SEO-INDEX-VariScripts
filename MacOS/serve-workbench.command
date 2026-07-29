#!/bin/sh
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
exec python3 "$ROOT/Py+Linux/Scripts/seo_index_toolkit.py" serve "$@"
