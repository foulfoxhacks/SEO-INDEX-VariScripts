#!/usr/bin/env sh
set -eu

REPOSITORY=${SEO_INDEX_REPOSITORY:-foulfoxhacks/SEO-INDEX-VariScripts}
REF=${SEO_INDEX_REF:-main}
INSTALL_DIR=${SEO_INDEX_INSTALL_DIR:-"$HOME/.local/share/seo-index-variscripts"}
BIN_DIR=${SEO_INDEX_BIN_DIR:-"$HOME/.local/bin"}
TMP_DIR=$(mktemp -d 2>/dev/null || mktemp -d -t seo-index)
ARCHIVE="$TMP_DIR/repo.tar.gz"
EXTRACT="$TMP_DIR/extract"
URL="https://github.com/$REPOSITORY/archive/refs/heads/$REF.tar.gz"

cleanup() { rm -rf "$TMP_DIR"; }
trap cleanup EXIT INT TERM

command -v curl >/dev/null 2>&1 || { echo 'curl is required.' >&2; exit 1; }
command -v tar >/dev/null 2>&1 || { echo 'tar is required.' >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo 'Python 3 is required.' >&2; exit 1; }

mkdir -p "$EXTRACT" "$BIN_DIR"
echo "Downloading $REPOSITORY ($REF)..."
curl -fsSL "$URL" -o "$ARCHIVE"
tar -xzf "$ARCHIVE" -C "$EXTRACT"
SOURCE=$(find "$EXTRACT" -mindepth 1 -maxdepth 1 -type d | head -n 1)
[ -n "$SOURCE" ] || { echo 'Downloaded archive did not contain a repository directory.' >&2; exit 1; }

rm -rf "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
cp -R "$SOURCE"/. "$INSTALL_DIR"/
for required in   "Py+Linux/Scripts/seo_index_toolkit.py"   "Py+Linux/Scripts/seo_index_extensions.py"   "Py+Linux/Scripts/seo_index_site.py"   "Py+Linux/Scripts/seo_index_quality.py"   "docs/index.html"   "Config/engine_profiles.json"; do
  [ -f "$INSTALL_DIR/$required" ] || { echo "Installation is incomplete; missing $required" >&2; exit 1; }
done
chmod +x "$INSTALL_DIR/Py+Linux/Scripts/"*.sh "$INSTALL_DIR/MacOS/"*.command 2>/dev/null || true

cat > "$BIN_DIR/seo-index" <<EOF
#!/usr/bin/env sh
exec python3 "$INSTALL_DIR/Py+Linux/Scripts/seo_index_toolkit.py" "\$@"
EOF
chmod +x "$BIN_DIR/seo-index"

echo
echo 'SEO-INDEX VariScripts installed.'
echo "Install directory: $INSTALL_DIR"
echo "Command shim:      $BIN_DIR/seo-index"
case ":${PATH}:" in
  *":$BIN_DIR:"*) echo 'Run: seo-index' ;;
  *) echo "Add this to your shell profile, then open a new terminal: export PATH=\"$BIN_DIR:\$PATH\"" ;;
esac
