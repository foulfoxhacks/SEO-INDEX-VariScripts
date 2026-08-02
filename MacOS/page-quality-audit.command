#!/bin/sh
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
if [ "$#" -eq 0 ]; then
  printf 'Page URL: '
  read -r URL
  set -- --url "$URL"
fi
exec python3 "$ROOT/Py+Linux/Scripts/seo_index_toolkit.py" page "$@"
