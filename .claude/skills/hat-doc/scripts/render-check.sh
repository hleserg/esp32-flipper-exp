#!/usr/bin/env bash
# Render a hat-doc HTML in BOTH themes to C:/bb/ (ASCII path — the Cyrillic
# username breaks Chrome's profile/paths otherwise).
#
# Usage:  render-check.sh <path-to-html> [width] [height]
# Output: C:/bb/<name>_light.png  and  C:/bb/<name>_dark.png
#
# Light is forced with the preferredColorScheme=1 blink setting. Dark is forced
# by injecting data-theme="dark" on <html> before <div class="wrap"> — the
# preferredColorScheme=2 flag does NOT reliably trigger the dark media query,
# but the page's :root[data-theme="dark"] block always wins.

set -euo pipefail

SRC="${1:?usage: render-check.sh <path-to-html> [width] [height]}"
W="${2:-1120}"
H="${3:-4200}"

CHROME="/c/Program Files/Google/Chrome/Application/chrome.exe"
[ -f "$CHROME" ] || CHROME="/c/Program Files (x86)/Google/Chrome/Application/chrome.exe"
[ -f "$CHROME" ] || { echo "Chrome not found" >&2; exit 1; }

mkdir -p /c/bb
NAME="$(basename "$SRC" .html)"
cp "$SRC" "/c/bb/${NAME}.html"

# dark-forced copy: set data-theme before the page wrapper renders
python - "$SRC" "/c/bb/${NAME}_darkforce.html" <<'PY'
import sys
src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8").read()
inj = '<script>document.documentElement.setAttribute("data-theme","dark")</script>\n<div class="wrap">'
s = s.replace('<div class="wrap">', inj, 1)
open(dst, "w", encoding="utf-8").write(s)
PY

common=(--headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 --window-size="${W},${H}")

"$CHROME" "${common[@]}" --blink-settings=preferredColorScheme=1 \
  --screenshot="/c/bb/${NAME}_light.png" "file:///C:/bb/${NAME}.html" 2>/dev/null || true
"$CHROME" "${common[@]}" \
  --screenshot="/c/bb/${NAME}_dark.png" "file:///C:/bb/${NAME}_darkforce.html" 2>/dev/null || true

echo "C:/bb/${NAME}_light.png"
echo "C:/bb/${NAME}_dark.png"
echo "Crop the changed region with PIL and Read the PNG — e.g.:"
echo "  python -c \"from PIL import Image; Image.open('C:/bb/${NAME}_light.png').crop((0,Y0,${W},Y1)).save('C:/bb/${NAME}_crop.png')\""
