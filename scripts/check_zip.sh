#!/usr/bin/env bash
# Prüft das ausgelieferte Addon-Zip: addon.xml vorhanden, library_linux zeigt auf eine echte Datei
# im Zip, diese besteht check_elf.sh, und es ist kein Python-Cache enthalten.
set -euo pipefail

zip="${1:?Aufruf: check_zip.sh <addon.zip>}"
id=visualization.partyvideo

if [[ ! -f "$zip" ]]; then
  echo "Zip nicht gefunden: $zip"
  exit 1
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
unzip -q "$zip" -d "$tmp"

xml="$tmp/$id/addon.xml"
if [[ ! -f "$xml" ]]; then
  echo "addon.xml fehlt im Zip"
  exit 1
fi

lib="$(grep -o -m1 'library_linux="[^"]*"' "$xml" | sed 's/^library_linux="//; s/"$//' || true)"
if [[ -z "$lib" ]]; then
  echo "library_linux fehlt in addon.xml"
  exit 1
fi

so="$tmp/$id/$lib"
if [[ -L "$so" || ! -f "$so" ]]; then
  echo "Bibliothek $lib fehlt im Zip oder ist ein Symlink"
  exit 1
fi

if [[ -n "$(find "$tmp" \( -name __pycache__ -o -name '*.pyc' \) -print -quit)" ]]; then
  echo "Python-Cache im Zip"
  exit 1
fi

"$(dirname "$0")/check_elf.sh" "$so"
